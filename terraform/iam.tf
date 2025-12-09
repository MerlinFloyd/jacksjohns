# IAM Configuration for Cloud Run services

# Service Account for Agent Service (Vertex AI access)
resource "google_service_account" "agent_service" {
  account_id   = "agent-service-sa"
  display_name = "Agent Service Account"
  description  = "Service account for the AI Agent service to access Vertex AI"
  project      = var.project_id
}

# Grant Vertex AI User role to agent service account
resource "google_project_iam_member" "agent_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_service.email}"
}

# Service Account for Discord Bot
resource "google_service_account" "discord_bot" {
  account_id   = "discord-bot-sa"
  display_name = "Discord Bot Service Account"
  description  = "Service account for the Discord bot"
  project      = var.project_id
}

# Allow Discord Bot to invoke Agent Service
resource "google_cloud_run_service_iam_member" "discord_bot_invoker" {
  count = var.agent_service_image != "" ? 1 : 0

  location = var.region
  project  = var.project_id
  service  = google_cloud_run_v2_service.agent_service[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.discord_bot.email}"
}
