# ==========================================
# Bitbank 自動積立Bot — Workload Identity Federation
# ==========================================
# GitHub Actions から GCP にキーレス認証するための設定。
# GitHub の OIDC トークンを GCP の SA にマッピングする。
#
# 仕組み:
#   GitHub Actions → OIDC トークン発行
#   → GCP WIF Pool/Provider がトークンを検証
#   → 指定した SA の権限で GCP リソースにアクセス
# ==========================================

# ------------------------------------------
# Workload Identity Pool
# ------------------------------------------
# GitHub Actions 用の ID プールを作成する。
# 1つの GCP プロジェクトに複数のプールを作成可能。
# ------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
  description               = "GitHub Actions からの OIDC 認証用プール"
}

# ------------------------------------------
# Workload Identity Provider
# ------------------------------------------
# GitHub の OIDC プロバイダを登録する。
# issuer_uri で GitHub の OIDC エンドポイントを指定。
# ------------------------------------------

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC Provider"

  # GitHub の OIDC 設定
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  # GitHub のトークン属性をマッピング
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # 指定リポジトリからのトークンのみ許可（セキュリティ対策）
  attribute_condition = "assertion.repository == '${var.github_owner}/${var.github_repo_name}'"
}

# ------------------------------------------
# SA ↔ WIF バインディング
# ------------------------------------------
# WIF で認証された GitHub Actions が、
# Cloud Functions デプロイ用の SA として振る舞えるようにする。
# ------------------------------------------

resource "google_service_account_iam_member" "wif_sa_binding" {
  service_account_id = google_service_account.functions_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_repo_name}"
}

# ------------------------------------------
# デプロイ用の追加 IAM ロール
# ------------------------------------------
# GitHub Actions から Cloud Functions をデプロイするために、
# SA に追加のロールが必要。
# ------------------------------------------

locals {
  deploy_roles = [
    # Cloud Functions の作成・更新
    "roles/cloudfunctions.developer",

    # Cloud Run サービスの管理（Gen2 の基盤）
    "roles/run.developer",

    # GCS へのソースコードアップロード
    "roles/storage.objectAdmin",

    # SA としての実行権限の付与
    "roles/iam.serviceAccountUser",
  ]
}

resource "google_project_iam_member" "deploy_roles" {
  for_each = toset(local.deploy_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.functions_sa.email}"
}
