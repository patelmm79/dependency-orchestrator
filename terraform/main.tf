terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Uncomment to use GCS backend for state management
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "dependency-orchestrator"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs (stateless architecture - minimal dependencies)
resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# ============================================================================
# Secret Manager - Conditional Creation
# ============================================================================

# Fetch existing secrets if create_secrets = false
data "google_secret_manager_secret" "anthropic_api_key" {
  count     = var.create_secrets ? 0 : 1
  secret_id = "anthropic-api-key"
  project   = var.project_id

  depends_on = [google_project_service.required_apis]
}

data "google_secret_manager_secret" "github_token" {
  count     = var.create_secrets ? 0 : 1
  secret_id = "github-token"
  project   = var.project_id

  depends_on = [google_project_service.required_apis]
}

data "google_secret_manager_secret" "webhook_url" {
  count     = var.create_secrets ? 0 : 1
  secret_id = "webhook-url"
  project   = var.project_id

  depends_on = [google_project_service.required_apis]
}

data "google_secret_manager_secret" "orchestrator_api_key" {
  count     = var.create_secrets ? 0 : 1
  secret_id = "orchestrator-api-key"
  project   = var.project_id

  depends_on = [google_project_service.required_apis]
}

# Create new secrets if create_secrets = true
resource "google_secret_manager_secret" "anthropic_api_key" {
  count     = var.create_secrets ? 1 : 0
  secret_id = "anthropic-api-key"
  labels    = merge(var.labels, { secret-type = "api-key" })

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret" "github_token" {
  count     = var.create_secrets ? 1 : 0
  secret_id = "github-token"
  labels    = merge(var.labels, { secret-type = "access-token" })

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret" "webhook_url" {
  count     = var.create_secrets ? 1 : 0
  secret_id = "webhook-url"
  labels    = merge(var.labels, { secret-type = "webhook" })

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret" "orchestrator_api_key" {
  count     = var.create_secrets ? 1 : 0
  secret_id = "orchestrator-api-key"
  labels    = merge(var.labels, { secret-type = "api-key" })

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

# Unified secret references
locals {
  anthropic_api_key_secret    = var.create_secrets ? google_secret_manager_secret.anthropic_api_key[0] : data.google_secret_manager_secret.anthropic_api_key[0]
  github_token_secret         = var.create_secrets ? google_secret_manager_secret.github_token[0] : data.google_secret_manager_secret.github_token[0]
  webhook_url_secret          = var.create_secrets ? google_secret_manager_secret.webhook_url[0] : data.google_secret_manager_secret.webhook_url[0]
  orchestrator_api_key_secret = var.create_secrets ? google_secret_manager_secret.orchestrator_api_key[0] : data.google_secret_manager_secret.orchestrator_api_key[0]
}

# Add secret versions (initial values) - only if creating new secrets
resource "google_secret_manager_secret_version" "anthropic_api_key" {
  count       = var.create_secrets ? 1 : 0
  secret      = local.anthropic_api_key_secret.id
  secret_data = var.anthropic_api_key

  # Prevent secret from being stored in state if empty
  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "github_token" {
  count       = var.create_secrets ? 1 : 0
  secret      = local.github_token_secret.id
  secret_data = var.github_token

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "webhook_url" {
  count       = var.create_secrets ? 1 : 0
  secret      = local.webhook_url_secret.id
  secret_data = var.webhook_url != "" ? var.webhook_url : "not-configured"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Generate random API key if not provided
resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret_version" "orchestrator_api_key" {
  count       = var.create_secrets ? 1 : 0
  secret      = local.orchestrator_api_key_secret.id
  secret_data = var.orchestrator_api_key != "" ? var.orchestrator_api_key : random_password.api_key.result

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Get project number for service account email
data "google_project" "project" {
  depends_on = [google_project_service.required_apis]
}

# Grant Cloud Run service account access to secrets
resource "google_secret_manager_secret_iam_member" "anthropic_api_key_access" {
  secret_id = local.anthropic_api_key_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "github_token_access" {
  secret_id = local.github_token_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "webhook_url_access" {
  secret_id = local.webhook_url_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "orchestrator_api_key_access" {
  secret_id = local.orchestrator_api_key_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# ============================================================================
# STATELESS ARCHITECTURE - NO EXTERNAL INFRASTRUCTURE REQUIRED
# ============================================================================
# The orchestrator is now fully stateless and uses FastAPI BackgroundTasks
# for async processing. No PostgreSQL, Redis, or VPC connectors needed.
#
# Previous: v1.0 had Redis + PostgreSQL + VPC infrastructure (~$95/month)
# Current:  v2.0 stateless with only Cloud Run (~$1-5/month)

# ============================================================================
# Docker Image Build (Automatic)
# ============================================================================

# Build Docker image using Cloud Build
resource "null_resource" "build_image" {
  count = var.auto_build ? 1 : 0

  triggers = {
    # Rebuild when this file changes (add more source files if needed)
    build_script = filemd5("${path.module}/../cloudbuild-terraform.yaml")
    dockerfile   = filemd5("${path.module}/../Dockerfile")
    # Force rebuild on each apply - remove if you want to build only on code changes
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Building Docker image with Cloud Build..."
      cd ${path.module}/..
      COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
      gcloud builds submit \
        --config=cloudbuild-terraform.yaml \
        --substitutions=_COMMIT_SHA=$COMMIT_SHA \
        --project=${var.project_id} \
        .
    EOT
  }

  depends_on = [
    google_project_service.required_apis,
    google_secret_manager_secret_iam_member.anthropic_api_key_access,
    google_secret_manager_secret_iam_member.github_token_access
  ]
}

# Local variable for image name
locals {
  image_name = "gcr.io/${var.project_id}/${var.service_name}:latest"
}

# ============================================================================
# Workload Identity (for A2A protected skills in dev-nexus)
# ============================================================================
# Enables Cloud Run to authenticate to dev-nexus protected A2A skills
# using Google-signed ID tokens (Workload Identity)

resource "google_service_account" "orchestrator_identity" {
  account_id   = "${var.service_name}-identity"
  display_name = "Orchestrator A2A Identity (Workload Identity)"
  description  = "Service account for Cloud Run to authenticate to dev-nexus A2A skills"
}

resource "google_cloud_run_service_iam_member" "workload_identity" {
  service  = google_cloud_run_service.orchestrator.name
  location = google_cloud_run_service.orchestrator.location
  role     = "roles/iam.workloadIdentityUser"
  member   = "serviceAccount:${google_service_account.orchestrator_identity.email}"
}

# Cloud Run service
resource "google_cloud_run_service" "orchestrator" {
  name     = var.service_name
  location = var.region

  metadata {
    labels = var.labels
  }

  template {
    metadata {
      labels = var.labels
      annotations = {
        "autoscaling.knative.dev/maxScale" = var.max_instances
        "autoscaling.knative.dev/minScale" = var.min_instances
      }
    }

    spec {
      # Use Workload Identity service account for A2A protected skills
      service_account_name = google_service_account.orchestrator_identity.email

      containers {
        image = var.auto_build ? local.image_name : var.container_image

        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
        }

        env {
          name = "ANTHROPIC_API_KEY"
          value_from {
            secret_key_ref {
              name = local.anthropic_api_key_secret.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "GITHUB_TOKEN"
          value_from {
            secret_key_ref {
              name = local.github_token_secret.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "WEBHOOK_URL"
          value_from {
            secret_key_ref {
              name = local.webhook_url_secret.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "ORCHESTRATOR_API_KEY"
          value_from {
            secret_key_ref {
              name = local.orchestrator_api_key_secret.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name  = "REQUIRE_AUTH"
          value = var.require_authentication ? "true" : "false"
        }

        env {
          name  = "DEV_NEXUS_URL"
          value = var.dev_nexus_url
        }
      }

      container_concurrency = var.container_concurrency
      timeout_seconds       = var.timeout_seconds
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_service.required_apis,
    google_secret_manager_secret_iam_member.anthropic_api_key_access,
    google_secret_manager_secret_iam_member.github_token_access,
    google_secret_manager_secret_iam_member.webhook_url_access,
    google_cloud_run_service_iam_member.workload_identity,
    null_resource.build_image,
  ]

  lifecycle {
    ignore_changes = [
      # Only ignore image changes if NOT auto-building
      # template[0].spec[0].containers[0].image,
      template[0].metadata[0].annotations["client.knative.dev/user-image"],
      template[0].metadata[0].annotations["run.googleapis.com/client-name"],
      template[0].metadata[0].annotations["run.googleapis.com/client-version"],
    ]
  }
}

# Make the service publicly accessible
resource "google_cloud_run_service_iam_member" "public_access" {
  count = var.allow_unauthenticated ? 1 : 0

  service  = google_cloud_run_service.orchestrator.name
  location = google_cloud_run_service.orchestrator.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Optional: Create Cloud Build trigger for automated deployments
resource "google_cloudbuild_trigger" "deploy_trigger" {
  count = var.enable_cloud_build_trigger ? 1 : 0

  name        = "${var.service_name}-deploy"
  description = "Deploy ${var.service_name} on push to ${var.github_repo_branch}"

  github {
    owner = var.github_repo_owner
    name  = var.github_repo_name
    push {
      branch = var.github_repo_branch
    }
  }

  filename = "cloudbuild.yaml"

  substitutions = {
    _REGION = var.region
  }

  tags = ["terraform-managed", "dependency-orchestrator"]

  depends_on = [google_project_service.required_apis]
}
