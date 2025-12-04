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
    anthropic_api_key    = google_secret_manager_secret.anthropic_api_key.secret_id
    github_token         = google_secret_manager_secret.github_token.secret_id
    webhook_url          = google_secret_manager_secret.webhook_url.secret_id
    orchestrator_api_key = google_secret_manager_secret.orchestrator_api_key.secret_id
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

output "next_steps" {
  description = "Next steps after Terraform apply"
  value = <<-EOT
    ✅ Infrastructure deployed successfully!

    Next steps:
    1. Build and deploy your container:
       ./deploy-gcp-cloudbuild.sh

    2. Test the service:
       curl ${google_cloud_run_service.orchestrator.status[0].url}

    3. Add this URL to your monitored repos as ORCHESTRATOR_URL:
       ${google_cloud_run_service.orchestrator.status[0].url}

    4. View logs:
       gcloud logging tail "resource.labels.service_name=${google_cloud_run_service.orchestrator.name}"

    5. Update secrets (if needed):
       echo -n "new-value" | gcloud secrets versions add anthropic-api-key --data-file=-
       echo -n "new-value" | gcloud secrets versions add github-token --data-file=-
       echo -n "new-value" | gcloud secrets versions add webhook-url --data-file=-
  EOT
}
