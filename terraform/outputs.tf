# Terraform Outputs

output "agent_service_url" {
  value       = var.agent_service_image != "" ? google_cloud_run_v2_service.agent_service[0].uri : "Not deployed - set agent_service_image variable"
  description = "URL of the Agent Service"
}

output "discord_bot_url" {
  value       = var.discord_bot_image != "" ? google_cloud_run_v2_service.discord_bot[0].uri : "Not deployed - set discord_bot_image variable"
  description = "URL of the Discord Bot Service"
}

output "agent_service_account_email" {
  value       = google_service_account.agent_service.email
  description = "Email of the Agent Service service account"
}

output "discord_bot_service_account_email" {
  value       = google_service_account.discord_bot.email
  description = "Email of the Discord Bot service account"
}

output "project_id" {
  value       = var.project_id
  description = "Google Cloud Project ID"
}

output "region" {
  value       = var.region
  description = "Google Cloud Region"
}
