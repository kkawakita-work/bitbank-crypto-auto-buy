# ==========================================
# Bitbank 自動積立Bot — Firestore
# ==========================================
# 注文履歴を保存する Firestore データベースを定義する。
# Native モードの Firestore を使用する。
# ==========================================

resource "google_firestore_database" "orders" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # 削除保護を有効化（誤削除防止）
  delete_protection_state = "DELETE_PROTECTION_ENABLED"

  depends_on = [google_project_service.apis]
}
