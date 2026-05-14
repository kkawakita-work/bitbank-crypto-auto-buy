# ==========================================
# Bitbank 自動積立Bot — Cloud Storage
# ==========================================
# 仮想残高プールを管理する GCS バケットを定義する。
# balance.json ファイルに仮想残高を JSON で保存する。
# ==========================================

resource "google_storage_bucket" "balance" {
  name     = var.gcs_bucket_name
  location = var.region
  project  = var.project_id

  # バージョニングを有効化（残高データの誤上書き対策）
  versioning {
    enabled = true
  }

  # 均一なバケットレベルアクセス制御を使用（推奨設定）
  uniform_bucket_level_access = true

  # 古いバージョンは30日後に自動削除（ストレージ節約）
  lifecycle_rule {
    condition {
      num_newer_versions = 5
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}
