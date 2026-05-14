# Bitbank 自動積立Bot 🤖

Bitbank 取引所の API を使い、**BTC を毎日自動で積み立てる**システムです。  
GCP（Google Cloud Platform）上に構築し、完全自動で運用できます。

## 🏗️ アーキテクチャ

```
Cloud Scheduler (1日1回)
    ↓ HTTP トリガー
Cloud Functions Gen2 (Python 3.12)
    ├── Bitbank API → 価格取得・指値注文
    ├── GCS → 仮想残高の読み書き
    └── Firestore → 注文履歴の保存
```

## ✨ 特徴

- **仮想残高プール方式**: 最小注文額（0.0001 BTC ≒ 約1,500円）に届かない日も予算を蓄積
- **Maker 指値注文**: `post_only: true` で手数料 0%（Taker 手数料 0.10% を回避）
- **Terraform IaC**: インフラ構成をコードで管理（1コマンドで環境構築）
- **キーレスCI/CD**: Workload Identity Federation で安全なデプロイ
- **GCP 無料枠内**: 月額 $0 で運用可能

## 📁 ディレクトリ構成

```
bitbank-crypto-auto-buy/
├── main.py                    # エントリーポイント + 積立ロジック
├── config.py                  # 積立設定（月間予算、最小注文単位）
├── requirements.txt           # Python 依存パッケージ
├── src/
│   ├── __init__.py
│   ├── bitbank.py             # Bitbank API クライアント
│   └── store.py               # GCS / Firestore 読み書き
├── terraform/
│   ├── main.tf                # プロバイダ設定、API 有効化
│   ├── variables.tf           # 変数定義
│   ├── cloud_functions.tf     # Cloud Functions Gen2
│   ├── scheduler.tf           # Cloud Scheduler
│   ├── storage.tf             # GCS バケット
│   ├── firestore.tf           # Firestore
│   ├── iam.tf                 # サービスアカウント + IAM
│   ├── wif.tf                 # Workload Identity Federation
│   ├── outputs.tf             # 出力値
│   └── terraform.tfvars.example
├── .github/workflows/
│   └── deploy.yml             # CI/CD パイプライン
├── .gitignore
└── .gcloudignore
```

## 🚀 セットアップ手順

### 1. 事前準備

- [Bitbank](https://bitbank.cc/) アカウントと API キーを発行
- [GCP](https://console.cloud.google.com/) プロジェクトを作成
- Terraform CLI をインストール（[公式ガイド](https://developer.hashicorp.com/terraform/install)）

### 2. Terraform で GCP リソースを構築

```bash
cd terraform

# terraform.tfvars を作成（API キー等を記入）
cp terraform.tfvars.example terraform.tfvars
vi terraform.tfvars

# インフラ構築
terraform init
terraform plan
terraform apply
```

### 3. GitHub Secrets を設定

`terraform output` で表示される値を GitHub リポジトリの Secrets に設定：

| Secret 名 | 値 |
|-----------|-----|
| `WORKLOAD_IDENTITY_PROVIDER` | `terraform output workload_identity_provider` |
| `SERVICE_ACCOUNT_EMAIL` | `terraform output service_account_email` |
| `BITBANK_API_KEY` | Bitbank API キー |
| `BITBANK_API_SECRET` | Bitbank API シークレット |
| `GCS_BUCKET` | `terraform output balance_bucket_name` |

### 4. デプロイ

`main` ブランチに push すると自動デプロイされます。

```bash
git push origin main
```

## 💰 コスト

すべて GCP 無料枠内で運用可能です：

| リソース | 無料枠 | 使用量 |
|---------|-------|-------|
| Cloud Functions | 200万回/月 | 30回/月 |
| Cloud Scheduler | 3ジョブ | 1ジョブ |
| Firestore | 1GiB / 5万読取 | 微量 |
| Cloud Storage | 5GB | 数KB |

## ⚠️ 注意事項

- このBotは投資助言ではありません。暗号資産の取引はご自身の判断と責任で行ってください。
- API キーには必要最小限の権限（現物取引のみ）を設定してください。
- `DRY_RUN=true` で動作確認してから本番運用を開始してください。

## 📝 ライセンス

MIT License
