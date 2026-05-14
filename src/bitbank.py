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

    Args:
        pair: 通貨ペア（デフォルト: btc_jpy）

    Returns:
        float: 最終取引価格（円）

    Raises:
        RuntimeError: API エラー時
    """
    # TODO: Step 2 で実装
    pass


def get_order(pair, order_id):
    """注文情報を取得する。

    Args:
        pair: 通貨ペア
        order_id: 注文ID

    Returns:
        dict: 注文情報（status, side, type, price, amount 等）
        None: 注文が見つからない場合
    """
    # TODO: Step 2 で実装
    pass


def cancel_order(pair, order_id, dry_run=False):
    """注文をキャンセルする。

    Args:
        pair: 通貨ペア
        order_id: 注文ID
        dry_run: True の場合は実際のキャンセルを行わない

    Returns:
        bool: キャンセル成功時 True
    """
    # TODO: Step 2 で実装
    pass


def place_limit_order(pair, amount_str, price_str, dry_run=False):
    """Maker 指値注文を発注する（post_only: true）。

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
    # TODO: Step 2 で実装
    pass
