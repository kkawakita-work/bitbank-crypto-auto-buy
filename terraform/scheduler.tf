# ==========================================
# Bitbank 自動積立Bot — Cloud Scheduler
# ==========================================
# 1日1回、Cloud Functions を HTTP で呼び出すジョブを定義する。
# デフォルトでは毎日 9:00 JST に実行される。
# ==========================================

resource "google_cloud_scheduler_job" "daily_buy" {
  name        = "bitbank-daily-buy"
  description = "毎日1回 Bitbank 自動積立Bot を実行する"
  project     = var.project_id
  region      = var.region

  # cron 式（デフォルト: 毎日 9:00 JST）
  schedule  = var.scheduler_schedule
  time_zone = var.scheduler_timezone

  # Cloud Functions Gen2 を HTTP で呼び出す
  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.bitbank_bot.url

    # サービスアカウントの OIDC トークンで認証
    oidc_token {
      service_account_email = google_service_account.functions_sa.email
    }
  }

  # リトライ設定
  retry_config {
    retry_count = 1  # 失敗時に1回だけリトライ（二重注文を避けるため最小限）
  }

  depends_on = [google_project_service.apis]
}
