variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run service"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  default     = "architecture-kb-orchestrator"
}

variable "container_image" {
  description = "Container image to deploy (will be updated by deployment scripts)"
  type        = string
  default     = "gcr.io/cloudrun/hello" # Placeholder, updated during deployment
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude AI"
  type        = string
  sensitive   = true
}

variable "github_token" {
  description = "GitHub personal access token"
  type        = string
  sensitive   = true
}

variable "webhook_url" {
  description = "Discord/Slack webhook URL for notifications"
  type        = string
  sensitive   = true
  default     = ""
}

variable "memory" {
  description = "Memory limit for Cloud Run service"
  type        = string
  default     = "512Mi"
}

variable "cpu" {
  description = "CPU allocation for Cloud Run service"
  type        = string
  default     = "1"
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = string
  default     = "10"
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = string
  default     = "0"
}

variable "container_concurrency" {
  description = "Maximum number of concurrent requests per container"
  type        = number
  default     = 80
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access to the service"
  type        = bool
  default     = true
}

# Cloud Build trigger variables (optional)
variable "enable_cloud_build_trigger" {
  description = "Enable automatic Cloud Build trigger on GitHub push"
  type        = bool
  default     = false
}

variable "github_repo_owner" {
  description = "GitHub repository owner (for Cloud Build trigger)"
  type        = string
  default     = ""
}

variable "github_repo_name" {
  description = "GitHub repository name (for Cloud Build trigger)"
  type        = string
  default     = ""
}

variable "github_repo_branch" {
  description = "GitHub repository branch to trigger builds (for Cloud Build trigger)"
  type        = string
  default     = "main"
}
