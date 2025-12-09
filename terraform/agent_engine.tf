# Agent Engine Configuration for Memory Bank and Sessions
# Note: Agent Engine instances (ReasoningEngine) are created via the SDK/API
# This file configures the necessary IAM permissions for the agent-service
# to interact with Agent Engine services.

# The Agent Engine ID will be created at runtime via the agent-service
# and stored in an environment variable: AGENT_ENGINE_ID

# Grant Agent Engine Admin role to agent service account
# This allows the service to create/manage Agent Engine instances
resource "google_project_iam_member" "agent_engine_admin" {
  project = var.project_id
  role    = "roles/aiplatform.admin"
  member  = "serviceAccount:${google_service_account.agent_service.email}"
}

# Note: The aiplatform.user role (already granted in iam.tf) provides access to:
# - Vertex AI models (for Gemini)
# - Agent Engine Sessions and Memory Bank services
# The aiplatform.admin role adds ability to create/delete Agent Engine instances

# Output variable for documentation
output "agent_engine_setup_instructions" {
  value = <<-EOT
    Agent Engine Setup Instructions:
    ================================
    
    1. The Agent Engine instance will be created automatically on first run
       of the agent-service if AGENT_ENGINE_ID is not set.
    
    2. Once created, set the AGENT_ENGINE_ID environment variable in Cloud Run:
       - Go to Cloud Run console
       - Edit the agent-service
       - Add environment variable: AGENT_ENGINE_ID=<your-engine-id>
    
    3. The Agent Engine ID format is:
       projects/${var.project_id}/locations/${var.region}/reasoningEngines/<id>
    
    Memory Bank Scoping Strategy:
    ============================
    - Shared Persona Memory: scope = {app_name: "<persona_name>"}
    - Per-User Memory: scope = {app_name: "<persona_name>", user_id: "<discord_user_id>"}
  EOT
}
