# ==========================================
# Bitbank 自動積立Bot — レポート生成
# ==========================================
# Firestore の注文履歴と Bitbank の現在価格をもとに
# 積立状況のサマリーとグラフを出力する。
#
# 出力:
#   1. テキストサマリー（そのまま YouTube 台本の素材として使える）
#   2. 資産推移グラフ（report_chart.png）
#
# 使い方:
#   python report.py               # 全期間サマリー
#   python report.py --weekly      # 今週のサマリー
#   python report.py --monthly     # 今月のサマリー
# ==========================================

import os
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import matplotlib
matplotlib.use('Agg')  # GUI 不要（画像ファイルへの保存のみ）
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

from google.cloud import firestore
from src.bitbank import get_ticker_price
from config import PAIR_CONFIG

JST = timezone(timedelta(hours=9))

# ------------------------------------------
# macOS 日本語フォント設定
# ------------------------------------------
FONT_CANDIDATES = ['Hiragino Sans', 'Hiragino Kaku Gothic Pro', 'Yu Gothic', 'Meiryo']
for font_name in FONT_CANDIDATES:
    try:
        from matplotlib.font_manager import FontProperties
        fp = FontProperties(family=font_name)
        if fp.get_name() != font_name:
            continue
        plt.rcParams['font.family'] = font_name
        break
    except Exception:
        continue


# ==========================================
# データ取得
# ==========================================

def fetch_filled_orders(pair):
    """Firestore から約定済みの注文を全件取得する。

    Args:
        pair: 通貨ペア（例: btc_jpy）

    Returns:
        list: 約定済み注文のリスト（日付昇順）
    """
    db = firestore.Client()
    docs = db.collection('orders') \
        .where('pair', '==', pair) \
        .where('status', '==', 'filled') \
        .stream()

    orders = [doc.to_dict() for doc in docs]
    orders.sort(key=lambda x: x.get('date', ''))
    return orders


# ==========================================
# 集計ロジック
# ==========================================

def calculate_summary(orders, current_price):
    """注文データからサマリーを計算する。

    Returns:
        dict: 以下のキーを持つサマリーデータ
          - total_invested: 総投入額（円）
          - total_btc: 総購入 BTC 数量
          - current_price: 現在の BTC 価格
          - current_value: 現在の評価額（円）
          - profit: 損益額（円）
          - profit_rate: 損益率（%）
          - order_count: 約定回数
          - weekly: 週次集計（dict）
          - monthly: 月次集計（dict）
          - daily_cumulative: 日次累計データ（グラフ用）
    """
    total_invested = 0.0
    total_btc = 0.0
    weekly = defaultdict(lambda: {'invested': 0.0, 'btc': 0.0, 'count': 0})
    monthly = defaultdict(lambda: {'invested': 0.0, 'btc': 0.0, 'count': 0})
    daily_cumulative = []

    for order in orders:
        amount = float(order['amount'])
        price = float(order['price'])
        cost = amount * price
        date_str = order.get('date', '')

        total_invested += cost
        total_btc += amount

        if date_str:
            dt = datetime.strptime(date_str, '%Y-%m-%d')

            # 週次集計（ISO 週番号）
            year, week, _ = dt.isocalendar()
            week_key = f'{year}-W{week:02d}'
            weekly[week_key]['invested'] += cost
            weekly[week_key]['btc'] += amount
            weekly[week_key]['count'] += 1

            # 月次集計
            month_key = date_str[:7]  # YYYY-MM
            monthly[month_key]['invested'] += cost
            monthly[month_key]['btc'] += amount
            monthly[month_key]['count'] += 1

        daily_cumulative.append({
            'date': date_str,
            'cumulative_invested': total_invested,
            'cumulative_btc': total_btc,
        })

    current_value = total_btc * current_price
    profit = current_value - total_invested
    profit_rate = (profit / total_invested * 100) if total_invested > 0 else 0

    return {
        'total_invested': total_invested,
        'total_btc': total_btc,
        'current_price': current_price,
        'current_value': current_value,
        'profit': profit,
        'profit_rate': profit_rate,
        'order_count': len(orders),
        'weekly': dict(sorted(weekly.items())),
        'monthly': dict(sorted(monthly.items())),
        'daily_cumulative': daily_cumulative,
    }


# ==========================================
# テキストレポート出力
# ==========================================

def print_report(summary, pair, mode='all'):
    """レポートをテキスト出力する。

    YouTube の台本素材として使えるフォーマットで出力。
    """
    now = datetime.now(JST)
    profit_sign = '+' if summary['profit'] >= 0 else ''

    print()
    print('━' * 55)
    print(f'📊 Bitbank BTC 自動積立レポート')
    print(f'   生成日時: {now.strftime("%Y年%m月%d日 %H:%M")}')
    print('━' * 55)

    # --- 全体サマリー ---
    print()
    print('【累計サマリー】')
    print(f'  総投入額:     {summary["total_invested"]:>10,.0f} 円')
    print(f'  購入BTC:      {summary["total_btc"]:>14.8f} BTC')
    print(f'  約定回数:     {summary["order_count"]:>10} 回')
    print(f'  現在BTC価格:  {summary["current_price"]:>10,.0f} 円')
    print(f'  現在評価額:   {summary["current_value"]:>10,.0f} 円')
    print(f'  損益:         {profit_sign}{summary["profit"]:>9,.0f} 円'
          f'（{profit_sign}{summary["profit_rate"]:.1f}%）')

    # --- 週次ブレークダウン ---
    if summary['weekly']:
        print()
        print('【週次ブレークダウン】')
        print(f'  {"週":>10}  {"投入額":>10}  {"購入BTC":>14}  {"回数":>4}')
        print(f'  {"─" * 10}  {"─" * 10}  {"─" * 14}  {"─" * 4}')
        for week, data in summary['weekly'].items():
            print(f'  {week:>10}  {data["invested"]:>10,.0f}  '
                  f'{data["btc"]:>14.8f}  {data["count"]:>4}')

    # --- 月次ブレークダウン ---
    if summary['monthly']:
        print()
        print('【月次ブレークダウン】')
        print(f'  {"月":>10}  {"投入額":>10}  {"購入BTC":>14}  {"回数":>4}')
        print(f'  {"─" * 10}  {"─" * 10}  {"─" * 14}  {"─" * 4}')
        for month, data in summary['monthly'].items():
            print(f'  {month:>10}  {data["invested"]:>10,.0f}  '
                  f'{data["btc"]:>14.8f}  {data["count"]:>4}')

    print()
    print('━' * 55)


# ==========================================
# グラフ生成
# ==========================================

def generate_chart(summary, output_path='report_chart.png'):
    """資産推移の棒グラフを生成する。

    X軸: 約定日
    Y軸: 金額（円）
    青い棒: 累計投入額
    オレンジ破線: 現在の評価額ライン

    Args:
        summary: calculate_summary() の戻り値
        output_path: 出力ファイルパス

    Returns:
        str: 出力ファイルパス。データなしの場合は None。
    """
    cumulative = summary['daily_cumulative']
    if not cumulative:
        print('チャート生成: データなし（スキップ）')
        return None

    # ダークテーマ（仮想通貨・金融系の雰囲気）
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')

    # データ準備
    dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in cumulative]
    invested = [d['cumulative_invested'] for d in cumulative]

    # 累計投入額（棒グラフ）
    bar_color = '#0f3460'
    edge_color = '#53a8b6'
    ax.bar(dates, invested, width=0.8, color=bar_color, edgecolor=edge_color,
           linewidth=0.5, label='累計投入額', zorder=2)

    # 現在の評価額ライン（水平破線）
    current_value = summary['current_value']
    ax.axhline(y=current_value, color='#e94560', linestyle='--', linewidth=2,
               label=f'現在評価額: {current_value:,.0f}円', zorder=3)

    # 最終投入額のラベル
    if invested:
        ax.annotate(f'{invested[-1]:,.0f}円',
                    xy=(dates[-1], invested[-1]),
                    xytext=(0, 10), textcoords='offset points',
                    ha='center', color='#53a8b6', fontsize=10, fontweight='bold')

    # 軸設定
    ax.set_xlabel('日付', color='#a0a0a0', fontsize=11)
    ax.set_ylabel('金額（円）', color='#a0a0a0', fontsize=11)
    ax.set_title('BTC 自動積立 資産推移', color='white', fontsize=14, fontweight='bold',
                 pad=15)

    # 日付フォーマット
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, color='#a0a0a0')
    plt.yticks(color='#a0a0a0')

    # Y軸を通貨フォーマット
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:,.0f}'))

    # グリッド
    ax.grid(axis='y', alpha=0.15, color='#a0a0a0')
    ax.legend(loc='upper left', fontsize=10, framealpha=0.3)

    # 損益表示（右下）
    profit = summary['profit']
    profit_rate = summary['profit_rate']
    profit_sign = '+' if profit >= 0 else ''
    profit_color = '#4ecca3' if profit >= 0 else '#e94560'
    ax.text(0.98, 0.05,
            f'損益: {profit_sign}{profit:,.0f}円（{profit_sign}{profit_rate:.1f}%）',
            transform=ax.transAxes, ha='right', va='bottom',
            fontsize=12, fontweight='bold', color=profit_color,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a2e', alpha=0.8))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    print(f'📈 チャート保存: {output_path}')
    return output_path


# ==========================================
# メイン
# ==========================================

def main():
    pair = PAIR_CONFIG['pair']
    mode = 'all'

    # コマンドライン引数の解析
    if '--weekly' in sys.argv:
        mode = 'weekly'
    elif '--monthly' in sys.argv:
        mode = 'monthly'

    print('データ取得中...')
    current_price = get_ticker_price(pair)
    orders = fetch_filled_orders(pair)

    if not orders:
        print('約定済みの注文がありません。')
        print('（Bot が稼働して注文が約定すると、ここにレポートが表示されます）')
        return

    summary = calculate_summary(orders, current_price)
    print_report(summary, pair, mode)
    generate_chart(summary)

    # YouTube パイプライン用の JSON 出力（将来用）
    print()
    print('💡 YouTube パイプラインへの連携:')
    print(f'   チャート画像: report_chart.png')
    print(f'   テキストデータ: 上記サマリーをそのまま台本素材として利用可能')


if __name__ == '__main__':
    main()
