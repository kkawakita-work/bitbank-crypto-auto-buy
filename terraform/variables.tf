# ==========================================
# Bitbank 自動積立Bot — Terraform 変数定義
# ==========================================
# Note購入者は terraform.tfvars を作成し、
# ここで定義された変数に値を設定してください。
# terraform.tfvars.example を参考にしてください。
# ==========================================

# ------------------------------------------
# GCP プロジェクト設定
# ------------------------------------------

variable "project_id" {
  description = "GCP プロジェクト ID"
  type        = string
}

variable "region" {
  description = "GCP リージョン（デフォルト: 東京）"
  type        = string
  default     = "asia-northeast1"
}

# ------------------------------------------
# GitHub 設定（Workload Identity Federation 用）
# ------------------------------------------

variable "github_owner" {
  description = "GitHub のオーナー名（Organization名 または ユーザー名）"
  type        = string
}

variable "github_repo_name" {
  description = "GitHub リポジトリ名"
  type        = string
  default     = "bitbank-crypto-auto-buy"
}

# ------------------------------------------
# Bitbank API 設定
# ------------------------------------------
# ⚠️ sensitive = true により、terraform plan/apply の出力には表示されません。
# terraform.tfvars に記載し、.gitignore で除外してください。
# ------------------------------------------

variable "bitbank_api_key" {
  description = "Bitbank API キー"
  type        = string
  sensitive   = true
}

variable "bitbank_api_secret" {
  description = "Bitbank API シークレット"
  type        = string
  sensitive   = true
}

# ------------------------------------------
# GCS 設定
# ------------------------------------------

variable "gcs_bucket_name" {
  description = "仮想残高管理用の GCS バケット名（グローバルで一意である必要あり）"
  type        = string
}

# ------------------------------------------
# Cloud Scheduler 設定
# ------------------------------------------

variable "scheduler_schedule" {
  description = "Cloud Scheduler の cron 式（デフォルト: 毎日9時 JST）"
  type        = string
  default     = "0 9 * * *"
}

variable "scheduler_timezone" {
  description = "Cloud Scheduler のタイムゾーン"
  type        = string
  default     = "Asia/Tokyo"
}
