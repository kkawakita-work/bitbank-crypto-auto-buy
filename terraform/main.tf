# ==========================================
# Bitbank 自動積立Bot — Terraform メイン設定
# ==========================================
# このファイルでは以下を定義:
#   1. Terraform の基本設定（required_providers）
#   2. Google Cloud プロバイダの設定
#   3. 必要な GCP API の有効化
# ==========================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # ==========================================
  # tfstate はローカル管理（デフォルト）
  # Note購入者が GCS バックエンドを設定する手間を省くため、
  # あえてリモートバックエンドは使わない。
  # .gitignore で terraform.tfstate* を除外すること。
  # ==========================================
}

# ==========================================
# Google Cloud プロバイダ設定
# ==========================================
provider "google" {
  project = var.project_id
  region  = var.region
}

# ==========================================
# 必要な GCP API を有効化
# ==========================================
# Cloud Functions Gen2 のデプロイに必要な API を一括で有効化する。
# 初回の terraform apply 時に自動で有効になる。
# ==========================================

locals {
  required_apis = [
    "cloudfunctions.googleapis.com",    # Cloud Functions
    "cloudscheduler.googleapis.com",    # Cloud Scheduler
    "firestore.googleapis.com",         # Firestore
    "storage.googleapis.com",           # Cloud Storage
    "iam.googleapis.com",               # IAM
    "cloudbuild.googleapis.com",        # Cloud Build（Functions デプロイに必要）
    "run.googleapis.com",               # Cloud Run（Functions Gen2 の基盤）
    "artifactregistry.googleapis.com",  # Artifact Registry（Functions Gen2 の基盤）
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project = var.project_id
  service = each.value

  # API を無効化しても依存リソースは削除しない（安全策）
  disable_dependent_services = false
  disable_on_destroy         = false
}
