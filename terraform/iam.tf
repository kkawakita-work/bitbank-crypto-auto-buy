# ==========================================
# Bitbank 自動積立Bot — IAM 設定
# ==========================================
# Cloud Functions 実行用のサービスアカウントと、
# 必要な IAM ロールのバインディングを定義する。
# ==========================================

# ------------------------------------------
# Cloud Functions 実行用サービスアカウント
# ------------------------------------------
# Cloud Functions がこの SA として実行され、
# GCS / Firestore / Logging にアクセスする。
# ------------------------------------------

resource "google_service_account" "functions_sa" {
  account_id   = "bitbank-bot-sa"
  display_name = "Bitbank Auto Buy Bot Service Account"
  description  = "Cloud Functions で実行される Bitbank 自動積立Bot 用の SA"
  project      = var.project_id
}

# ------------------------------------------
# IAM ロールバインディング
# ------------------------------------------
# SA に必要最小限のロールを付与する（最小権限の原則）。
# ------------------------------------------

locals {
  sa_roles = [
    # GCS の読み書き（仮想残高 balance.json の管理）
    "roles/storage.objectUser",

    # Firestore の読み書き（注文履歴の管理）
    "roles/datastore.user",

    # Cloud Logging への書き込み（ログ出力）
    "roles/logging.logWriter",
  ]
}

resource "google_project_iam_member" "functions_sa_roles" {
  for_each = toset(local.sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.functions_sa.email}"
}
