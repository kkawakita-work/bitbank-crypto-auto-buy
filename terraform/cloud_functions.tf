# ==========================================
# Bitbank 自動積立Bot — Cloud Functions Gen2
# ==========================================
# Python 3.12 で動作する Cloud Functions Gen2 を定義する。
# Cloud Scheduler から HTTP トリガーで呼び出される。
# ==========================================

# ------------------------------------------
# ソースコードを ZIP 化して GCS にアップロード
# ------------------------------------------
# Cloud Functions Gen2 はソースコードを GCS バケットから読み込む。
# Terraform でデプロイする場合は、ソースを ZIP にしてアップロードする。
# ------------------------------------------

# ソースコード格納用バケット
resource "google_storage_bucket" "functions_source" {
  name     = "${var.project_id}-functions-source"
  location = var.region
  project  = var.project_id

  # ソースコードは一時的なものなので、30日で自動削除
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

# ソースコードを ZIP 化
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "${path.module}/.."
  output_path = "${path.module}/.tmp/function-source.zip"

  # デプロイに不要なファイルを除外
  excludes = [
    "terraform",
    ".github",
    ".git",
    ".gitignore",
    ".gcloudignore",
    ".env",
    ".venv",
    "venv",
    "__pycache__",
    "README.md",
    "INSTRUCTIONS.md",
    ".DS_Store",
  ]
}

# ZIP を GCS にアップロード
resource "google_storage_bucket_object" "function_source" {
  name   = "function-source-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.functions_source.name
  source = data.archive_file.function_source.output_path
}

# ------------------------------------------
# Cloud Functions Gen2 本体
# ------------------------------------------

resource "google_cloudfunctions2_function" "bitbank_bot" {
  name     = "bitbank-auto-buy-bot"
  location = var.region
  project  = var.project_id

  description = "Bitbank BTC 自動積立Bot（1日1回実行）"

  build_config {
    runtime     = "python312"
    entry_point = "bitbank_auto_buy"

    source {
      storage_source {
        bucket = google_storage_bucket.functions_source.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    # 最小スペックで十分（コスト最適化）
    available_memory   = "256M"
    timeout_seconds    = 120
    max_instance_count = 1
    min_instance_count = 0

    # 専用サービスアカウントで実行
    service_account_email = google_service_account.functions_sa.email

    # 環境変数（Bitbank API キー、GCS バケット名）
    environment_variables = {
      BITBANK_API_KEY    = var.bitbank_api_key
      BITBANK_API_SECRET = var.bitbank_api_secret
      GCS_BUCKET         = var.gcs_bucket_name
      DRY_RUN            = "false"
    }
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.functions_sa_roles,
  ]
}

# ------------------------------------------
# Cloud Functions の URL を Cloud Scheduler から呼べるようにする
# ------------------------------------------
# Cloud Scheduler が HTTP で Cloud Functions を呼び出すため、
# Scheduler 用 SA に invoker ロールを付与する。
# ------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloudfunctions2_function.bitbank_bot.name

  role   = "roles/run.invoker"
  member = "serviceAccount:${google_service_account.functions_sa.email}"
}
