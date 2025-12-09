# Artifact Registry for Docker images

resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "discord-bot-repo"
  description   = "Docker repository for Discord Bot and Agent Service"
  format        = "DOCKER"
  project       = var.project_id

  depends_on = [google_project_service.required_apis]
}

# Output the repository URL for use in CI/CD
output "docker_repository_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
  description = "Docker repository URL for pushing images"
}
