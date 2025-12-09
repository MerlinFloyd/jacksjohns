# Firestore database for persona persistence
# Using Native mode for better real-time capabilities and newer features

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Ensure required APIs are enabled first
  depends_on = [google_project_service.required_apis]
}

# Note: Firestore security rules should be configured via Firebase console
# or using google_firebaserules_ruleset resource if needed.
# For Cloud Run services using service accounts, IAM roles provide access control.
