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

# ============================================================================
# A2A Infrastructure Outputs
# ============================================================================

output "backend_type" {
  description = "Active backend type (postgresql or redis)"
  value       = var.use_postgresql ? "postgresql" : "redis"
}

output "postgres_host" {
  description = "PostgreSQL host IP (if using PostgreSQL)"
  value       = var.use_postgresql ? var.postgres_host : null
}

output "postgres_connection_string" {
  description = "PostgreSQL connection details (if using PostgreSQL)"
  value       = var.use_postgresql ? "postgresql://orchestrator:****@${var.postgres_host}:5432/orchestrator" : null
}

output "postgres_generated_password" {
  description = "Auto-generated PostgreSQL password (only shown if not provided)"
  value       = var.use_postgresql && var.postgres_password == "" ? nonsensitive(random_password.postgres_password.result) : "*****(provided by user)*****"
  sensitive   = false
}

output "redis_host" {
  description = "Redis Memorystore host IP (if using Redis)"
  value       = var.use_postgresql ? null : (length(google_redis_instance.task_queue) > 0 ? google_redis_instance.task_queue[0].host : null)
}

output "redis_port" {
  description = "Redis Memorystore port (if using Redis)"
  value       = var.use_postgresql ? null : (length(google_redis_instance.task_queue) > 0 ? google_redis_instance.task_queue[0].port : null)
}

output "redis_url" {
  description = "Redis connection URL for task queue (if using Redis)"
  value       = var.use_postgresql ? null : (length(google_redis_instance.task_queue) > 0 ? "redis://${google_redis_instance.task_queue[0].host}:${google_redis_instance.task_queue[0].port}/0" : null)
}

output "vpc_connector" {
  description = "VPC connector for Cloud Run to PostgreSQL/Redis"
  value       = google_vpc_access_connector.backend_connector.id
}

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

output "next_steps" {
  description = "Next steps after Terraform apply"
  value       = var.use_postgresql ? <<-EOT
✅ A2A Infrastructure deployed successfully with PostgreSQL!

🔧 A2A Resources Created:
- Backend: PostgreSQL (primary - recommended)
- PostgreSQL VM: orchestrator-postgres-vm (${var.postgres_vm_machine_type})
- VPC Connector: ${google_vpc_access_connector.backend_connector.name}
- Internal IP: ${var.postgres_host}

📝 PostgreSQL Connection:
POSTGRES_HOST=${var.postgres_host}
POSTGRES_PORT=5432
POSTGRES_DB=orchestrator
POSTGRES_USER=orchestrator
POSTGRES_PASSWORD=${var.postgres_password != "" ? "*****(set)" : random_password.postgres_password.result}

⚠️  Initialize database schema:
1. Copy schema to VM:
   gcloud compute scp orchestrator/a2a/postgres_schema.sql orchestrator-postgres-vm:/tmp/ --zone=${var.region}-a

2. Initialize schema:
   gcloud compute ssh orchestrator-postgres-vm --zone=${var.region}-a --command="PGPASSWORD='${var.postgres_password != "" ? var.postgres_password : random_password.postgres_password.result}' psql -h localhost -U orchestrator -d orchestrator -f /tmp/postgres_schema.sql"

📋 Next steps:
1. Build and deploy your container:
   ./deploy-gcp-cloudbuild.sh

2. Test the service:
   curl ${google_cloud_run_service.orchestrator.status[0].url}

3. View logs:
   gcloud logging tail "resource.labels.service_name=${google_cloud_run_service.orchestrator.name}"
EOT
  : <<-EOT
✅ A2A Infrastructure deployed successfully with Redis!

🔧 A2A Resources Created:
- Backend: Redis Memorystore (secondary fallback)
- Redis Instance: ${google_redis_instance.task_queue[0].name} (${var.redis_memory_gb}GB)
- VPC Connector: ${google_vpc_access_connector.backend_connector.name}
- Redis URL: redis://${google_redis_instance.task_queue[0].host}:${google_redis_instance.task_queue[0].port}/0

📋 Next steps:
1. Build and deploy your container:
   ./deploy-gcp-cloudbuild.sh

2. Test the service:
   curl ${google_cloud_run_service.orchestrator.status[0].url}

3. Test A2A AgentCard:
   curl ${google_cloud_run_service.orchestrator.status[0].url}/.well-known/agent.json

4. List A2A skills:
   curl ${google_cloud_run_service.orchestrator.status[0].url}/a2a/skills

5. Add this URL to your monitored repos as ORCHESTRATOR_URL:
   ${google_cloud_run_service.orchestrator.status[0].url}

6. View logs:
   gcloud logging tail "resource.labels.service_name=${google_cloud_run_service.orchestrator.name}"

💰 Estimated Monthly Cost:
- Cloud Run: ~$50/month
- Redis Memorystore: ~$45/month
- Total: ~$95/month

📚 Documentation:
- A2A Features: docs/A2A_README.md
- Migration Guide: docs/A2A_MIGRATION_GUIDE.md
- PostgreSQL Setup: docs/POSTGRESQL_SETUP.md
EOT
}
