# ==========================================
# Bitbank 自動積立Bot — Terraform 出力値
# ==========================================
# terraform apply 後に表示される値。
# GitHub Actions の Secrets に設定する値もここで確認できる。
# ==========================================

# ------------------------------------------
# Cloud Functions
# ------------------------------------------

output "function_url" {
  description = "Cloud Functions の URL（Cloud Scheduler から呼び出される）"
  value       = google_cloudfunctions2_function.bitbank_bot.url
}

output "function_name" {
  description = "Cloud Functions の名前"
  value       = google_cloudfunctions2_function.bitbank_bot.name
}

# ------------------------------------------
# サービスアカウント
# ------------------------------------------

output "service_account_email" {
  description = "Cloud Functions 実行用サービスアカウントのメールアドレス（GitHub Secrets に設定）"
  value       = google_service_account.functions_sa.email
}

# ------------------------------------------
# Workload Identity Federation
# ------------------------------------------
# GitHub Actions の Secrets に設定する値:
#   WORKLOAD_IDENTITY_PROVIDER → workload_identity_provider
#   SERVICE_ACCOUNT_EMAIL      → service_account_email
# ------------------------------------------

output "workload_identity_provider" {
  description = "WIF プロバイダの完全修飾名（GitHub Secrets に設定）"
  value       = google_iam_workload_identity_pool_provider.github.name
}

# ------------------------------------------
# GCS
# ------------------------------------------

output "balance_bucket_name" {
  description = "仮想残高管理用 GCS バケット名"
  value       = google_storage_bucket.balance.name
}

# ------------------------------------------
# Cloud Scheduler
# ------------------------------------------

output "scheduler_job_name" {
  description = "Cloud Scheduler ジョブ名"
  value       = google_cloud_scheduler_job.daily_buy.name
}
