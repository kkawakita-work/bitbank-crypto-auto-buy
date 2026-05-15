# ==========================================
# Bitbank 自動積立Bot — GCS / Firestore ストア
# ==========================================
# データの永続化を担当するモジュール:
#   - GCS: 仮想残高プール（balance.json）の読み書き
#   - Firestore: 注文履歴の保存・取得・更新
# ==========================================

import json
from datetime import datetime, timezone, timedelta
# pyrefly: ignore [missing-import]
from google.cloud import storage, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

JST = timezone(timedelta(hours=9))


# ==========================================
# GCS — 仮想残高管理
# ==========================================
# balance.json の構造:
#   {"btc_jpy": 1500.0}
#
# 仮想残高は毎日加算され、注文が約定したら差し引かれる。
# GCS のバージョニングが有効なので、誤上書きしても復旧可能。
# ==========================================

def load_balance(bucket_name):
    """GCS から仮想残高を読み込む。

    Args:
        bucket_name: GCS バケット名

    Returns:
        dict: 残高データ（例: {"btc_jpy": 1500.0}）
              ファイルが存在しない場合は空の dict
    """
    client = storage.Client()
    blob = client.bucket(bucket_name).blob('balance.json')

    if blob.exists():
        data = json.loads(blob.download_as_text())
        print(f'  残高読み込み: {json.dumps(data, ensure_ascii=False)}')
        return data

    print('  残高ファイルなし（初回実行）')
    return {}


def save_balance(bucket_name, balance):
    """GCS に仮想残高を保存する。

    Args:
        bucket_name: GCS バケット名
        balance: 残高データ（dict）
    """
    client = storage.Client()
    blob = client.bucket(bucket_name).blob('balance.json')
    blob.upload_from_string(
        json.dumps(balance, indent=2, ensure_ascii=False),
        content_type='application/json',
    )
    print(f'  残高保存: {json.dumps(balance, ensure_ascii=False)}')


# ==========================================
# Firestore — 注文履歴管理
# ==========================================
# orders コレクションの構造:
#   {
#     "pair": "btc_jpy",
#     "orderId": "12345",
#     "amount": "0.0001",
#     "price": "15000000",
#     "status": "pending" | "filled" | "canceled",
#     "date": "2026-05-14",
#     "createdAt": Timestamp,
#   }
#
# インデックス不要: Python 側で createdAt ソートして最新1件を取得
# ==========================================

def save_order(pair, order_id, amount_str, price_str):
    """新規注文を Firestore に保存する。

    Args:
        pair: 通貨ペア（例: btc_jpy）
        order_id: Bitbank の注文ID
        amount_str: 注文数量（文字列）
        price_str: 注文価格（文字列）
    """
    today = datetime.now(JST).strftime('%Y-%m-%d')
    db = firestore.Client()
    db.collection('orders').add({
        'pair': pair,
        'orderId': order_id,
        'amount': amount_str,
        'price': price_str,
        'status': 'pending',
        'date': today,
        'createdAt': datetime.now(JST),
    })


def get_latest_order(pair):
    """指定した通貨ペアの最新の注文を1件取得する。

    Firestore の複合インデックスを避けるため、
    Python 側で createdAt の降順ソートを行う。

    Args:
        pair: 通貨ペア（例: btc_jpy）

    Returns:
        tuple: (doc_id, order_dict) または None
    """
    db = firestore.Client()
    # 絞り込みのみを行い、並び替えは Python 側で行う（インデックス不要）
    docs = db.collection('orders') \
        .where(filter=FieldFilter('pair', '==', pair)) \
        .stream()

    results = [(doc.id, doc.to_dict()) for doc in docs]
    if not results:
        return None

    # 作成日時（createdAt）で降順にソートして先頭を返す
    results.sort(
        key=lambda x: x[1].get('createdAt') or datetime.min.replace(tzinfo=JST),
        reverse=True,
    )
    return results[0]


def update_order(doc_id, updates):
    """注文のステータスを更新する。

    Args:
        doc_id: Firestore ドキュメント ID
        updates: 更新するフィールド（dict）
    """
    db = firestore.Client()
    db.collection('orders').document(doc_id).update(updates)
