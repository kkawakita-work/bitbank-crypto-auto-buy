# Bitbank 自動積立Bot — 実装指示書

> **この文書の目的**: 新しいAntigravityセッションで、Bitbank自動積立botプロジェクトの初期セットアップを行うための全コンテキストと指示。

---

## 1. プロジェクト概要

Bitbank取引所のAPIを使い、BTCを毎日自動で積み立てるシステムをGCP上に構築する。
YouTube（エンジニア向け）およびNote（IaC・コード販売）で公開する前提の商品パッケージとして作成する。

既存のGMOコイン自動積立bot（別リポ・別GCPプロジェクト）を参考にしつつ、完全に独立したリポジトリとして構築する。

---

## 2. 確定済みの設計方針

| 項目 | 決定事項 |
|------|---------|
| リポジトリ名 | `bitbank-crypto-auto-buy` |
| GitHub | 新規Organization配下にpublicリポとして作成 |
| GCPプロジェクト | 既存GMOとは別の新規プロジェクト（同一Billing Account） |
| インフラ管理 | **Terraform**（IaCとして公開・販売する前提） |
| tfstate管理 | **ローカル管理**（`.gitignore`対象）。Note購入者の初期ハードルを下げるため |
| 取引所 | Bitbank |
| 対象銘柄 | BTC（btc_jpy ペア） |
| 購入頻度 | 1日1回（Cloud Scheduler） |
| 最小注文数量 | 0.0001 BTC |
| 注文方式 | Maker指値注文（`post_only: true`） |
| 積立ロジック | **仮想残高プール方式（GCS管理）を採用** |
| Secret管理 | Secret Managerは不使用。Cloud Functions環境変数で管理 |
| CI/CD | GitHub Actions + Workload Identity Federation |
| コード共有 | GMOリポとの共有なし。完全独立 |

---

## 3. 積立ロジック設計（詳細）

### なぜ仮想残高プール方式か
- Bitbankの最小注文額は0.0001 BTC ≒ 約1,500円（BTC=1,500万円時）
- ユーザーの月間予算が3万円の場合、1日あたり約1,000円で最小注文額に届かない日がある
- したがって予算を仮想的に蓄積し、閾値を超えたら発注する方式が必要

### 実行フロー（1日1回）

```
1. 前回注文の決着確認
   - Firestoreから最新注文を取得
   - Bitbank APIで注文状態を確認
   - 約定済み → 残高から費用を差し引き
   - 未約定 → キャンセル → 残高は維持

2. 予算蓄積
   - monthly_budget / 30 円を仮想残高に加算（1日1回なので30分割）

3. 新規注文判定
   - 現在価格を取得
   - 残高 ≥ price × 0.0001（最小注文金額）なら発注
   - post_only: true の指値注文（Maker専用）
```

---

## 4. Bitbank API 仕様

### 基本情報
- **ベースURL**: `https://api.bitbank.cc/v1`
- **認証**: HMAC-SHA256
- **ヘッダー**: `ACCESS-KEY`, `ACCESS-NONCE`, `ACCESS-SIGNATURE`

### 認証方式

```python
import hmac, hashlib, time, json

api_key = "YOUR_API_KEY"
api_secret = "YOUR_API_SECRET"
nonce = str(int(time.time() * 1000))

# GETリクエストの場合
message = nonce + "/v1/user/assets"
signature = hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

# POSTリクエストの場合
body = json.dumps({"pair": "btc_jpy", "amount": "0.0001", "price": "15000000", "side": "buy", "type": "limit", "post_only": True})
message = nonce + body
signature = hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

headers = {
    "ACCESS-KEY": api_key,
    "ACCESS-NONCE": nonce,
    "ACCESS-SIGNATURE": signature,
    "Content-Type": "application/json",
}
```

### 主要エンドポイント

| 用途 | メソッド | パス |
|------|---------|------|
| 価格取得 | GET | `https://public.bitbank.cc/{pair}/ticker`（公開API） |
| 注文作成 | POST | `/user/spot/order` |
| 注文確認 | GET | `/user/spot/order?pair=btc_jpy&order_id={id}` |
| 注文キャンセル | POST | `/user/spot/cancel_order` |
| アクティブ注文 | GET | `/user/spot/active_orders?pair=btc_jpy` |
| 取引履歴 | GET | `/user/spot/trade_history?pair=btc_jpy` |
| 資産情報 | GET | `/user/assets` |

### 注文パラメータ（POST /user/spot/order）

```json
{
  "pair": "btc_jpy",
  "amount": "0.0001",
  "price": "15000000",
  "side": "buy",
  "type": "limit",
  "post_only": true
}
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| pair | string | ○ | 通貨ペア（例: `btc_jpy`） |
| amount | string | ○ | 注文数量 |
| price | string | △ | 注文価格（limit時必須） |
| side | string | ○ | `buy` or `sell` |
| type | string | ○ | `limit`, `market` 等 |
| post_only | boolean | × | `true`でMaker専用（即時約定なら自動キャンセル） |

### 手数料（2026年2月改定後）

| 通貨ペア | Maker | Taker |
|---------|-------|-------|
| BTC/JPY | 0.00% | 0.10% |
| その他 | -0.02% | 0.12% |

---

## 5. ディレクトリ構成（目標）

```
bitbank-crypto-auto-buy/
├── main.py                    # エントリーポイント + 積立ロジック
├── config.py                  # 積立設定（月間予算、最小注文単位）
├── requirements.txt           # Python依存パッケージ
├── src/
│   ├── __init__.py
│   ├── bitbank.py             # Bitbank API クライアント
│   └── store.py               # GCS/Firestore 読み書き
├── terraform/
│   ├── main.tf                # プロバイダ設定、API有効化
│   ├── variables.tf           # 変数定義（プロジェクトID、GitHubリポ名等）
│   ├── cloud_functions.tf     # Cloud Functions Gen2
│   ├── scheduler.tf           # Cloud Scheduler（1日1回）
│   ├── storage.tf             # GCS バケット（残高プール用）
│   ├── firestore.tf           # Firestore（注文履歴）
│   ├── iam.tf                 # サービスアカウント + IAMロール
│   ├── wif.tf                 # Workload Identity Federation
│   ├── outputs.tf             # 出力値
│   └── terraform.tfvars.example  # Note購入者向けサンプル
├── .github/workflows/
│   └── deploy.yml             # CI/CD パイプライン
├── .gitignore
├── .gcloudignore
└── README.md                  # 視聴者・購入者向けドキュメント
```

---

## 6. Terraformで管理するGCPリソース

| リソース | Terraform リソース | 備考 |
|---------|-------------------|------|
| API有効化 | `google_project_service` | cloudfunctions, cloudscheduler, firestore, storage, iam, cloudbuild, run, artifactregistry |
| サービスアカウント | `google_service_account` | Cloud Functions実行用 |
| IAMバインディング | `google_project_iam_member` | SA → 各サービスへのロール |
| GCSバケット | `google_storage_bucket` | 残高管理用 |
| Firestoreデータベース | `google_firestore_database` | 注文履歴 |
| Cloud Functions Gen2 | `google_cloudfunctions2_function` | Python 3.12 |
| Cloud Scheduler | `google_cloud_scheduler_job` | 1日1回トリガー |
| WIF Pool | `google_iam_workload_identity_pool` | GitHub Actions認証 |
| WIF Provider | `google_iam_workload_identity_pool_provider` | GitHub OIDC |
| SA ↔ WIF バインディング | `google_service_account_iam_member` | WIF → SA 紐付け |

### 重要: variables.tfの設計

Note購入者が書き換えやすいよう、以下を変数として切り出す：

```hcl
variable "project_id" {}           # GCPプロジェクトID
variable "region" { default = "asia-northeast1" }
variable "github_owner" {}          # GitHub Organization名
variable "github_repo_name" { default = "bitbank-crypto-auto-buy" }
variable "bitbank_api_key" { sensitive = true }
variable "bitbank_api_secret" { sensitive = true }
variable "gcs_bucket_name" {}       # 残高管理用バケット名
variable "scheduler_schedule" { default = "0 9 * * *" }  # 毎日9時JST
```

---

## 7. 既存GMOプロジェクトの参考コード

### GMO API認証（参考: src/gmo.py の認証部分）

```python
def _headers(path, method, body=None):
    api_key = os.environ['GMO_API_KEY']
    api_secret = os.environ['GMO_API_SECRET']
    timestamp = str(int(time.time() * 1000))
    body_str = json.dumps(body, separators=(',', ':')) if body is not None else ''
    text = timestamp + method + path + body_str
    sign = hmac.new(api_secret.encode('ascii'), text.encode('ascii'), hashlib.sha256).hexdigest()
    return {
        'API-KEY': api_key,
        'API-TIMESTAMP': timestamp,
        'API-SIGN': sign,
        'Content-Type': 'application/json',
        '_body_str': body_str,
    }
```

### GMO 積立メインロジック（参考: main.py の構造）

```python
def gmo_auto_buy(request):
    balance = load_balance(bucket_name)
    for symbol, cfg in SYMBOLS.items():
        # Step 1: 前回注文の決着（約定→残高減算、未約定→キャンセル）
        resolved = _sync_previous_order(symbol, balance, dry_run)
        # Step 2: 予算蓄積（monthly_budget / 360）
        _accumulate_budget(balance, symbol, cfg)
        # Step 3: 残高が最小購入額を超えたら新規注文
        if resolved:
            _try_new_order(symbol, cfg, balance, dry_run)
    save_balance(bucket_name, balance)
```

### GMO Firestore保存（参考: src/store.py）

```python
def save_order(symbol, order_id, size_str, price_str):
    db = firestore.Client()
    db.collection('orders').add({
        'symbol': symbol, 'orderId': order_id,
        'size': size_str, 'price': price_str,
        'status': 'pending', 'date': today, 'createdAt': datetime.now(JST),
    })

def get_latest_order(symbol):
    db = firestore.Client()
    docs = db.collection('orders').where('symbol', '==', symbol).stream()
    results = [(doc.id, doc.to_dict()) for doc in docs]
    results.sort(key=lambda x: x[1].get('createdAt', datetime.min), reverse=True)
    return results[0] if results else None
```

### GMO CI/CD（参考: .github/workflows/deploy.yml）

```yaml
name: Deploy to Cloud Functions
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.SERVICE_ACCOUNT_EMAIL }}
      - uses: google-github-actions/deploy-cloud-functions@v3
        with:
          name: gmo-auto-buy-bot
          runtime: python312
          region: asia-northeast1
          entry_point: gmo_auto_buy
          environment: GEN_2
          environment_variables: |-
            GMO_API_KEY=${{ secrets.GMO_API_KEY }}
            GMO_API_SECRET=${{ secrets.GMO_API_SECRET }}
            GCS_BUCKET=${{ secrets.GCS_BUCKET }}
            DRY_RUN=false
```

---

## 8. 今回のタスク（Step 1）

上記の要件に基づき、以下の初期セットアップを行ってほしい：

### 8.1 ディレクトリ構成の作成
セクション5の構成に従い、雛形を作成する。

### 8.2 Terraform ファイル一式の作成
`terraform/` 配下に以下のファイルをドラフト作成：
- `main.tf` — プロバイダ設定、API有効化
- `variables.tf` — GCPプロジェクトID、GitHubリポジトリ名などの変数（セクション6参照）
- `iam.tf` — サービスアカウント + IAMロール
- `cloud_functions.tf` — Cloud Functions Gen2
- `scheduler.tf` — Cloud Scheduler（1日1回）
- `storage.tf` — GCS バケット（残高プール用）
- `firestore.tf` — Firestore（注文履歴）
- `wif.tf` — Workload Identity Federation（GitHub Actions認証）
- `outputs.tf` — 出力値
- `terraform.tfvars.example` — Note購入者向けサンプル

### 8.3 Pythonアプリ側のプレースホルダー
- `main.py` — エントリーポイント（プレースホルダー）
- `config.py` — 積立設定（プレースホルダー）
- `requirements.txt` — 依存パッケージ
- `src/__init__.py`
- `src/bitbank.py` — Bitbank APIクライアント（プレースホルダー）
- `src/store.py` — GCS/Firestore読み書き（プレースホルダー）

### 8.4 その他
- `.gitignore` — `.env`, `terraform.tfstate*`, `terraform.tfvars`, `.venv/`, `__pycache__/` 等
- `.gcloudignore`
- `README.md` — プロジェクト概要（簡易版でOK）

### 注意事項
- まずはTerraformとディレクトリ構成のドラフトを出力し、問題ないか確認させてほしい。
- Pythonのロジック実装はStep 2以降で行う。
- Terraform変数は Note購入者が `terraform.tfvars` を書き換えるだけで使えるように設計する。
- すべてのファイルにコメントを充実させる（YouTube/Note向けの教材として）。

---

## 9. GCPコスト見積もり

全て無料枠内に収まる見込み：

| リソース | 無料枠 | 使用量 |
|---------|-------|-------|
| Cloud Functions | 200万回/月 | 30回/月 |
| Cloud Scheduler | 3ジョブ | 1ジョブ |
| Firestore | 1GiB / 5万読取 / 2万書込 | 微量 |
| Cloud Storage | 5GB | 数KB |

---

## 10. 既存GMOプロジェクトの学び（避けるべき落とし穴）

1. **cancel_orderの失敗** → キャンセル失敗時に二重注文を防ぐロジックが必要
2. **実行頻度と予算加算のズレ** → 1日1回なら `monthly_budget / 30` で単純
3. **Firestoreインデックス問題** → Python側ソートで回避（インデックス不要な設計）
4. **プロジェクト名が汎用的すぎた** → 今回は `bitbank-crypto-auto-buy` で明確に
