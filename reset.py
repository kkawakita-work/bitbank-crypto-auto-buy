# ==========================================
# Bitbank 自動積立Bot — データリセットスクリプト
# ==========================================
# テスト期間中のデータを全て削除し、本番開始に備える。
#
# 削除対象:
#   1. GCS: balance.json（仮想残高）
#   2. Firestore: orders コレクション（注文履歴）
#
# 使い方:
#   python reset.py
# ==========================================

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google.cloud import storage, firestore


def reset_balance(bucket_name):
    """GCS の balance.json を削除する。"""
    client = storage.Client()
    blob = client.bucket(bucket_name).blob('balance.json')

    if blob.exists():
        blob.delete()
        print('✅ GCS: balance.json を削除しました')
    else:
        print('⏭️  GCS: balance.json は存在しません（スキップ）')


def reset_orders():
    """Firestore の orders コレクションを全件削除する。"""
    db = firestore.Client()
    docs = db.collection('orders').stream()

    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1

    if count > 0:
        print(f'✅ Firestore: orders コレクションから {count} 件を削除しました')
    else:
        print('⏭️  Firestore: orders コレクションは空です（スキップ）')


def main():
    bucket_name = os.environ['GCS_BUCKET']

    print('=' * 50)
    print('⚠️  データリセットスクリプト')
    print('=' * 50)
    print(f'  GCS バケット: {bucket_name}')
    print(f'  削除対象: balance.json + Firestore orders 全件')
    print('=' * 50)

    confirm = input('\n本当に全データを削除しますか？ (yes/no): ')
    if confirm.strip().lower() != 'yes':
        print('キャンセルしました。')
        return

    print()
    reset_balance(bucket_name)
    reset_orders()
    print('\n🎉 リセット完了！6/1 からクリーンな状態で積立を開始できます。')


if __name__ == '__main__':
    main()
