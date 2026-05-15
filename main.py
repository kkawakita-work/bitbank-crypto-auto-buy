# ==========================================
# Bitbank 自動積立Bot — エントリーポイント
# ==========================================
# Cloud Functions のエントリーポイント。
# Cloud Scheduler から HTTP トリガーで1日1回呼び出される。
#
# 実行フロー:
#   1. 前回注文の決着確認（約定 → 残高減算 / 未約定 → キャンセル）
#   2. 予算蓄積（monthly_budget / 30 円を仮想残高に加算）
#   3. 新規注文判定（残高 ≥ 最小注文金額なら Maker 指値注文）
#
# 仮想残高プール方式:
#   - Bitbank の BTC 最小注文数量は 0.0001 BTC（≒ 約1,500円）
#   - 月間予算 10,000円 → 日割り約333円では最小注文額に届かない
#   - そのため予算を仮想的に蓄積し、閾値を超えたら発注する
# ==========================================

import os
import math
from datetime import datetime, timezone, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import PAIR_CONFIG
from src.bitbank import get_ticker_price, place_limit_order, get_order, cancel_order
from src.store import load_balance, save_balance, save_order, get_latest_order, update_order

JST = timezone(timedelta(hours=9))

# 指値注文の価格オフセット（現在価格 × このレートで発注）
# 1.0 = 現在価格と同値。少し高めに設定すると約定しやすい。
LIMIT_ORDER_OFFSET = 1.0


def bitbank_auto_buy(request):
    """Cloud Functions エントリーポイント（HTTP トリガー）"""
    try:
        dry_run = os.environ.get('DRY_RUN', 'true').lower() != 'false'
        bucket_name = os.environ['GCS_BUCKET']
        pair = PAIR_CONFIG['pair']

        print(f'=== Bitbank 自動積立 開始 {"[DRY RUN]" if dry_run else "[本番]"} ===')
        print(f'時刻(JST): {datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")}')

        # DRY RUN 時は GCS/Firestore を使わず、空の残高で動作確認
        if dry_run:
            balance = {}
            print('  [DRY RUN] GCS/Firestore をスキップ（空の残高で実行）')
        else:
            balance = load_balance(bucket_name)

        # Step 1: 前回注文の決着確認（DRY RUN 時はスキップ）
        if dry_run:
            resolved = True
        else:
            resolved = _sync_previous_order(pair, balance, dry_run)

        # Step 2: 予算蓄積（1日1回 × 30日 = monthly_budget を30分割）
        _accumulate_budget(pair, balance)

        # Step 3: 新規注文判定
        #         前回注文が未決着（キャンセル失敗等）の場合は二重注文を防ぐためスキップ
        if resolved:
            _try_new_order(pair, balance, dry_run)
        else:
            print(f'[{pair}] 前回注文が未決着のため新規注文をスキップ')

        # Step 4: 残高保存（DRY RUN 時はスキップ）
        if not dry_run:
            save_balance(bucket_name, balance)

        print('=== 完了 ===')
        return 'OK', 200

    except Exception as e:
        # メンテナンス中やネットワークエラー時は、エラーを記録して終了
        # 次回の実行時に、今回の予算分も含めて処理される
        print(f'エラーが発生しました（メンテナンス等の可能性があります）: {e}')
        return f'Error: {e}', 200  # Cloud Functions 側では正常終了扱いにしてリトライを避ける


def _sync_previous_order(pair, balance, dry_run):
    """最新の注文を取得し、未約定ならキャンセル、約定なら残高を減算する。

    戻り値: True=決着済み（新規注文可）, False=未決着（新規注文不可）

    Bitbank の注文ステータス:
      - UNFILLED: 未約定 → キャンセルを試みる
      - PARTIALLY_FILLED: 一部約定 → キャンセルを試みる（約定分は残る）
      - FULLY_FILLED: 全約定 → 残高から費用を差し引く
      - CANCELED_UNFILLED: キャンセル済み → 決着済み
      - CANCELED_PARTIALLY_FILLED: 一部約定後キャンセル → 決着済み
    """
    latest = get_latest_order(pair)
    if not latest:
        return True  # 前回注文なし → 新規注文可

    doc_id, order = latest
    if order['status'] == 'filled':
        return True  # すでに処理済み

    order_id = order['orderId']
    print(f'[{pair}] 前回の注文(ID:{order_id}) を確認中...')

    order_info = get_order(pair, order_id)
    if not order_info:
        return True  # 注文情報取得不可 → 消失扱い

    status = order_info.get('status')

    if status == 'FULLY_FILLED':
        # 全約定していた場合 → 残高から費用を差し引く
        cost = float(order['amount']) * float(order['price'])
        balance[pair] = max(0.0, balance.get(pair, 0.0) - cost)
        update_order(doc_id, {'status': 'filled', 'filledAt': datetime.now(JST)})
        print(f'[{pair}] 約定確定。残高を差し引きました (-{cost:.0f}円)')
        return True

    elif status in ('UNFILLED', 'PARTIALLY_FILLED'):
        # 未約定 or 一部約定 → キャンセルを試みる
        if cancel_order(pair, order_id, dry_run):
            update_order(doc_id, {'status': 'canceled', 'canceledAt': datetime.now(JST)})
            print(f'[{pair}] 未約定のためリセットしました。')
            return True
        else:
            # キャンセル失敗 → 前回注文がまだ生きている可能性が高い
            print(f'[{pair}] キャンセル失敗。前回の注文が残っています。')
            return False  # 新規注文をブロック

    else:
        # すでにキャンセル済みや失効済みの場合
        update_order(doc_id, {'status': 'canceled', 'canceledAt': datetime.now(JST)})
        print(f'[{pair}] 前回の注文は失効またはキャンセル済みでした。')
        return True


def _accumulate_budget(pair, balance):
    """仮想残高に日割り予算を加算する。

    monthly_budget / 30 円を毎日加算する。
    （1日1回の実行なので、30日で monthly_budget 分が蓄積される）
    """
    daily_budget = PAIR_CONFIG['monthly_budget'] / 30
    balance[pair] = balance.get(pair, 0.0) + daily_budget
    print(f'[{pair}] 予算蓄積: +{daily_budget:.1f}円 | 累計: {balance[pair]:.0f}円')


def _try_new_order(pair, balance, dry_run):
    """予算が足りていれば新規指値注文を出す。

    判定: 残高 ≥ 現在価格 × 最小注文数量（0.0001 BTC）
    注文: post_only=true の Maker 指値（手数料 0%）
    """
    price = get_ticker_price(pair)
    min_amount = PAIR_CONFIG['min_amount']
    min_order_jpy = price * min_amount

    # min_amount から小数桁数を動的に計算（0.0001 → 4桁）
    decimals = abs(int(round(math.log10(min_amount))))

    current_balance = balance.get(pair, 0)
    print(f'[{pair}] 残高: {current_balance:.0f}円 | '
          f'最小購入額: {min_order_jpy:.0f}円 | 価格: {price:,.0f}円')

    if current_balance < min_order_jpy:
        print(f'[{pair}] 残高不足のためスキップ')
        return

    # 購入可能な最大数量を計算（小数点以下 decimals 桁で切り捨て）
    amount = math.floor(current_balance / price * (10 ** decimals)) / (10 ** decimals)
    amount_str = f'{amount:.{decimals}f}'

    # 指値価格を計算（現在価格 × オフセット、整数に切り捨て）
    order_price = math.floor(price * LIMIT_ORDER_OFFSET)
    price_str = str(order_price)

    if dry_run:
        print(f'[{pair}] [DRY RUN] 指値: {price_str}円 | {amount_str} BTC')
        return

    order_id = place_limit_order(pair, amount_str, price_str, dry_run)
    if order_id:
        save_order(pair, order_id, amount_str, price_str)
        print(f'[{pair}] 発注成功: order_id={order_id} | {amount_str} BTC @ {price_str}円')
    else:
        print(f'[{pair}] 発注失敗のため残高を保持')


if __name__ == '__main__':
    bitbank_auto_buy(None)
