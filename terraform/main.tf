terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
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

# Enable required APIs
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

# Create secrets in Secret Manager
resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "anthropic-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret" "github_token" {
  secret_id = "github-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret" "webhook_url" {
  count     = var.webhook_url != "" ? 1 : 0
  secret_id = "webhook-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

# Add secret versions (initial values)
resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret      = google_secret_manager_secret.anthropic_api_key.id
  secret_data = var.anthropic_api_key

  # Prevent secret from being stored in state if empty
  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "github_token" {
  secret      = google_secret_manager_secret.github_token.id
  secret_data = var.github_token

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_version" "webhook_url" {
  count       = var.webhook_url != "" ? 1 : 0
  secret      = google_secret_manager_secret.webhook_url[0].id
  secret_data = var.webhook_url

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
  secret_id = google_secret_manager_secret.anthropic_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "github_token_access" {
  secret_id = google_secret_manager_secret.github_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "webhook_url_access" {
  count     = var.webhook_url != "" ? 1 : 0
  secret_id = google_secret_manager_secret.webhook_url[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Cloud Run service
resource "google_cloud_run_service" "orchestrator" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      service_account_name = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"

      containers {
        image = var.container_image

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
              name = google_secret_manager_secret.anthropic_api_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "GITHUB_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.github_token.secret_id
              key  = "latest"
            }
          }
        }

        dynamic "env" {
          for_each = var.webhook_url != "" ? [1] : []
          content {
            name = "WEBHOOK_URL"
            value_from {
              secret_key_ref {
                name = google_secret_manager_secret.webhook_url[0].secret_id
                key  = "latest"
              }
            }
          }
        }
      }

      container_concurrency = var.container_concurrency
      timeout_seconds       = var.timeout_seconds
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = var.max_instances
        "autoscaling.knative.dev/minScale" = var.min_instances
      }
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
  ]

  lifecycle {
    ignore_changes = [
      template[0].spec[0].containers[0].image,
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

  depends_on = [google_project_service.required_apis]
}
