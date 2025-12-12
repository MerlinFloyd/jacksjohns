# Terraform Variables

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "jacks-johns"
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

variable "discord_bot_token" {
  description = "Discord Bot Token (sensitive)"
  type        = string
  sensitive   = true
}

variable "discord_application_id" {
  description = "Discord Application ID"
  type        = string
  default     = "1447797969423175742"
}

variable "gemini_model" {
  description = "Gemini model for chat"
  type        = string
  default     = "gemini-3-pro-preview"
}

variable "gemini_image_model" {
  description = "Gemini model for image generation"
  type        = string
  default     = "gemini-3-pro-image-preview"
}

variable "agent_service_image" {
  description = "Docker image for agent service"
  type        = string
  default     = ""
}

variable "discord_bot_image" {
  description = "Docker image for discord bot"
  type        = string
  default     = ""
}

variable "github_repository" {
  description = "GitHub repository in format owner/repo"
  type        = string
  default     = ""
}
