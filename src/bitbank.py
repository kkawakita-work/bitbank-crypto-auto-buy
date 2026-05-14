# ==========================================
# Bitbank 自動積立Bot — Bitbank API クライアント
# ==========================================
# Bitbank REST API を使って以下の操作を行うモジュール:
#   - 現在価格の取得（公開API）
#   - 指値注文の作成（プライベートAPI）
#   - 注文状態の確認（プライベートAPI）
#   - 注文のキャンセル（プライベートAPI）
#
# 認証方式: HMAC-SHA256
# ヘッダー: ACCESS-KEY, ACCESS-NONCE, ACCESS-SIGNATURE
#
# 参考: https://github.com/bitbankinc/bitbank-api-docs
# ==========================================

import os
import time
import json
import hmac
import hashlib
import requests

# Bitbank API エンドポイント
PUBLIC_BASE_URL = 'https://public.bitbank.cc'
PRIVATE_BASE_URL = 'https://api.bitbank.cc/v1'


def _auth_headers(path, body=None):
    """プライベート API 用の認証ヘッダーを生成する。

    Bitbank の認証方式:
      - ACCESS-KEY: API キー
      - ACCESS-NONCE: ミリ秒単位のタイムスタンプ（リプレイ攻撃対策）
      - ACCESS-SIGNATURE: HMAC-SHA256 で署名

    GET の場合: signature = HMAC(nonce + path)
    POST の場合: signature = HMAC(nonce + json_body)

    Args:
        path: API パス（GET の場合はクエリパラメータ含む）
        body: POST リクエストのボディ（dict）。GET の場合は None。

    Returns:
        tuple: (headers_dict, body_json_str or None)
    """
    api_key = os.environ['BITBANK_API_KEY']
    api_secret = os.environ['BITBANK_API_SECRET']
    nonce = str(int(time.time() * 1000))

    if body is not None:
        # POST リクエスト: nonce + JSON ボディ で署名
        body_str = json.dumps(body)
        message = nonce + body_str
    else:
        # GET リクエスト: nonce + パス（クエリパラメータ含む）で署名
        message = nonce + path
        body_str = None

    signature = hmac.new(
        api_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        'ACCESS-KEY': api_key,
        'ACCESS-NONCE': nonce,
        'ACCESS-SIGNATURE': signature,
        'Content-Type': 'application/json',
    }

    return headers, body_str


def get_ticker_price(pair='btc_jpy'):
    """現在の最終取引価格を取得する（公開API・認証不要）。

    公開 API: GET https://public.bitbank.cc/{pair}/ticker
    レスポンス例:
      {"success": 1, "data": {"sell": "...", "buy": "...", "last": "15000000", ...}}

    Args:
        pair: 通貨ペア（デフォルト: btc_jpy）

    Returns:
        float: 最終取引価格（円）

    Raises:
        RuntimeError: API エラー時
    """
    url = f'{PUBLIC_BASE_URL}/{pair}/ticker'
    res = requests.get(url).json()

    if res.get('success') != 1:
        raise RuntimeError(f'価格取得失敗: {json.dumps(res, ensure_ascii=False)}')

    last_price = float(res['data']['last'])
    print(f'  現在価格: {last_price:,.0f}円')
    return last_price


def get_order(pair, order_id):
    """注文情報を取得する。

    GET /v1/user/spot/order?pair={pair}&order_id={order_id}

    Bitbank の注文ステータス:
      - UNFILLED: 未約定
      - PARTIALLY_FILLED: 一部約定
      - FULLY_FILLED: 全約定
      - CANCELED_UNFILLED: キャンセル（未約定）
      - CANCELED_PARTIALLY_FILLED: キャンセル（一部約定）

    Args:
        pair: 通貨ペア
        order_id: 注文ID

    Returns:
        dict: 注文情報。API エラー時は RuntimeError を投げる。
        None: 注文が見つからない場合
    """
    path = f'/v1/user/spot/order?pair={pair}&order_id={order_id}'
    headers, _ = _auth_headers(path)

    res = requests.get(
        PRIVATE_BASE_URL + f'/user/spot/order',
        headers=headers,
        params={'pair': pair, 'order_id': order_id},
    ).json()

    if res.get('success') != 1:
        error_code = res.get('data', {}).get('code')
        # 50009: 注文が見つからない
        if error_code == 50009:
            print(f'  注文が見つかりません (order_id={order_id})')
            return None
        raise RuntimeError(f'注文取得APIエラー: {json.dumps(res, ensure_ascii=False)}')

    order = res['data']
    print(f'  注文状態: {order.get("status")} (order_id={order_id})')
    return order


def cancel_order(pair, order_id, dry_run=False):
    """注文をキャンセルする。

    POST /v1/user/spot/cancel_order
    ボディ: {"pair": "btc_jpy", "order_id": 12345}

    Args:
        pair: 通貨ペア
        order_id: 注文ID
        dry_run: True の場合は実際のキャンセルを行わない

    Returns:
        bool: キャンセル成功時 True
    """
    if dry_run:
        print(f'[DRY RUN] キャンセル: order_id={order_id}')
        return True

    path = '/v1/user/spot/cancel_order'
    body = {'pair': pair, 'order_id': int(order_id)}
    headers, body_str = _auth_headers(path, body)

    res = requests.post(
        PRIVATE_BASE_URL + '/user/spot/cancel_order',
        headers=headers,
        data=body_str.encode('utf-8'),
    ).json()

    success = res.get('success') == 1
    if not success:
        print(f'  キャンセルAPIレスポンス: {json.dumps(res, ensure_ascii=False)}')
    return success


def place_limit_order(pair, amount_str, price_str, dry_run=False):
    """Maker 指値注文を発注する（post_only: true）。

    POST /v1/user/spot/order
    ボディ: {"pair": "btc_jpy", "amount": "0.0001", "price": "15000000",
             "side": "buy", "type": "limit", "post_only": true}

    post_only: true を指定することで:
      - 即時約定する価格の場合は自動キャンセルされる
      - 確実に Maker（手数料 0%）として約定する

    Args:
        pair: 通貨ペア（例: btc_jpy）
        amount_str: 注文数量（文字列）
        price_str: 注文価格（文字列）
        dry_run: True の場合は実際の発注を行わない

    Returns:
        str: 注文ID（成功時）
        None: 失敗時
    """
    path = '/v1/user/spot/order'
    body = {
        'pair': pair,
        'amount': amount_str,
        'price': price_str,
        'side': 'buy',
        'type': 'limit',
        'post_only': True,
    }

    if dry_run:
        print(f'[DRY RUN] 発注: {json.dumps(body, ensure_ascii=False)}')
        return None

    headers, body_str = _auth_headers(path, body)

    res = requests.post(
        PRIVATE_BASE_URL + '/user/spot/order',
        headers=headers,
        data=body_str.encode('utf-8'),
    ).json()

    print(f'  発注APIレスポンス: {json.dumps(res, ensure_ascii=False)}')

    if res.get('success') == 1:
        return str(res['data']['order_id'])
    return None
