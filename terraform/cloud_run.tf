# Cloud Run Services

# Agent Service - Python FastAPI with Vertex AI
resource "google_cloud_run_v2_service" "agent_service" {
  count = var.agent_service_image != "" ? 1 : 0

  name     = "agent-service"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.agent_service.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = var.agent_service_image

      ports {
        container_port = 8000
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }

      env {
        name  = "GEMINI_IMAGE_MODEL"
        value = var.gemini_image_model
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 5
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 30
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_project_service.required_apis]
}

# Discord Bot Service
resource "google_cloud_run_v2_service" "discord_bot" {
  count = var.discord_bot_image != "" ? 1 : 0

  name     = "discord-bot"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.discord_bot.email

    scaling {
      # Discord bot should always be running
      min_instance_count = 1
      max_instance_count = 1
    }

    containers {
      image = var.discord_bot_image

      env {
        name  = "DISCORD_APPLICATION_ID"
        value = var.discord_application_id
      }

      env {
        name = "DISCORD_BOT_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.discord_bot_token[0].secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "AGENT_SERVICE_URL"
        value = google_cloud_run_v2_service.agent_service[0].uri
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "256Mi"
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_v2_service.agent_service
  ]
}

# Secret Manager for Discord Bot Token
resource "google_secret_manager_secret" "discord_bot_token" {
  count = var.discord_bot_image != "" ? 1 : 0

  secret_id = "discord-bot-token"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "discord_bot_token" {
  count = var.discord_bot_image != "" ? 1 : 0

  secret      = google_secret_manager_secret.discord_bot_token[0].id
  secret_data = var.discord_bot_token
}

# Grant Discord Bot service account access to the secret
resource "google_secret_manager_secret_iam_member" "discord_bot_token_access" {
  count = var.discord_bot_image != "" ? 1 : 0

  secret_id = google_secret_manager_secret.discord_bot_token[0].secret_id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.discord_bot.email}"
}
