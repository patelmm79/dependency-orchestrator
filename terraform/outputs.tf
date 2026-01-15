output "service_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_service.orchestrator.status[0].url
}

output "service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_service.orchestrator.name
}

output "service_location" {
  description = "Location of the Cloud Run service"
  value       = google_cloud_run_service.orchestrator.location
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "project_number" {
  description = "GCP Project Number"
  value       = data.google_project.project.number
}

output "cloud_run_service_account" {
  description = "Service account used by Cloud Run"
  value       = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

output "secret_ids" {
  description = "Secret Manager secret IDs"
  value = {
    anthropic_api_key    = local.anthropic_api_key_secret.secret_id
    github_token         = local.github_token_secret.secret_id
    webhook_url          = local.webhook_url_secret.secret_id
    orchestrator_api_key = local.orchestrator_api_key_secret.secret_id
  }
}

output "generated_api_key" {
  description = "Auto-generated API key (only shown if not provided in variables)"
  value       = var.orchestrator_api_key == "" ? nonsensitive(random_password.api_key.result) : "*****(provided by user)*****"
  sensitive   = false
}

output "authentication_enabled" {
  description = "Whether API key authentication is required"
  value       = var.require_authentication
}

output "container_image" {
  description = "Current container image"
  value       = google_cloud_run_service.orchestrator.template[0].spec[0].containers[0].image
}

output "auto_build_enabled" {
  description = "Whether automatic Docker build is enabled"
  value       = var.auto_build
}

# ============================================================================
# A2A Protocol Endpoints (Stateless Architecture)
# ============================================================================

output "agent_card_url" {
  description = "A2A AgentCard discovery URL"
  value       = "${google_cloud_run_service.orchestrator.status[0].url}/.well-known/agent.json"
}

output "a2a_endpoints" {
  description = "A2A protocol endpoints"
  value = {
    agent_card = "${google_cloud_run_service.orchestrator.status[0].url}/.well-known/agent.json"
    health     = "${google_cloud_run_service.orchestrator.status[0].url}/a2a/health"
    skills     = "${google_cloud_run_service.orchestrator.status[0].url}/a2a/skills"
    execute    = "${google_cloud_run_service.orchestrator.status[0].url}/a2a/execute"
  }
}

locals {
  next_steps = <<-EOT
    ✅ Dependency Orchestrator deployed successfully (Stateless v2.0)!

    🎯 Service Details:
    - URL: ${google_cloud_run_service.orchestrator.status[0].url}
    - Location: ${google_cloud_run_service.orchestrator.location}
    - Memory: 512Mi
    - CPU: 1 core
    - Auto-scaling: 0-10 instances

    📡 A2A Protocol Endpoints:
    - AgentCard: ${google_cloud_run_service.orchestrator.status[0].url}/.well-known/agent.json
    - Health: ${google_cloud_run_service.orchestrator.status[0].url}/a2a/health
    - Skills: ${google_cloud_run_service.orchestrator.status[0].url}/a2a/skills
    - Execute: ${google_cloud_run_service.orchestrator.status[0].url}/a2a/execute

    🔐 Authentication:
    - Required: ${var.require_authentication}
    - API Key Secret: ${local.orchestrator_api_key_secret.secret_id}

    📋 Next Steps:

    1. Test the service:
       curl ${google_cloud_run_service.orchestrator.status[0].url}

    2. View A2A capabilities:
       curl ${google_cloud_run_service.orchestrator.status[0].url}/.well-known/agent.json

    3. Configure GitHub webhooks in your source repos to:
       POST ${google_cloud_run_service.orchestrator.status[0].url}/api/webhook/change-notification

    4. View logs:
       gcloud logging tail "resource.labels.service_name=${google_cloud_run_service.orchestrator.name}"

    💰 Estimated Monthly Cost:
    - Cloud Run: ~$1-5/month (auto-scales to 0 when idle)
    - No database, Redis, or VPC infrastructure costs!

    📚 Documentation:
    - CLAUDE.md: Full deployment and development guide
    - Local testing: uvicorn orchestrator.app_unified:app --reload
  EOT
}

output "next_steps" {
  description = "Next steps after Terraform apply"
  value       = local.next_steps
}
