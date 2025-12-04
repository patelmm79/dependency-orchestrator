# Terraform Configuration for Dependency Orchestrator

This directory contains Terraform configuration to set up the complete GCP infrastructure for the Dependency Orchestrator service.

## What This Terraform Configuration Does

- **Enables GCP APIs**: Cloud Build, Cloud Run, Secret Manager, Cloud Resource Manager
- **Creates Secret Manager Secrets**: For Anthropic API key, GitHub token, and webhook URL
- **Configures IAM**: Grants Cloud Run service account access to secrets
- **Deploys Cloud Run Service**: Creates the service with proper configuration
- **Optional**: Sets up Cloud Build trigger for automatic deployments on git push

## Prerequisites

1. **Terraform** (>= 1.0): https://developer.hashicorp.com/terraform/downloads
2. **gcloud CLI**: https://cloud.google.com/sdk/docs/install
3. **GCP Project** with billing enabled
4. **Secrets**:
   - Anthropic API key (`sk-ant-xxxxx`)
   - GitHub personal access token (`ghp_xxxxx`)
   - Discord/Slack webhook URL (optional)

## Quick Start

### 1. Authenticate with GCP

```bash
gcloud auth login
gcloud auth application-default login
```

### 2. Configure Terraform

```bash
cd terraform

# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
# Required: project_id, anthropic_api_key, github_token
# Optional: webhook_url, region, resource sizes
```

### 3. Deploy Infrastructure

```bash
# Initialize Terraform (downloads providers)
terraform init

# Review what will be created
terraform plan

# Create the infrastructure
terraform apply
```

### 4. Deploy Application Code

After Terraform creates the infrastructure, deploy your application:

```bash
# Option A: Local Docker build
cd ..
./deploy-gcp.sh

# Option B: Cloud Build
cd ..
./deploy-gcp-cloudbuild.sh
```

## File Structure

- **`main.tf`**: Main Terraform configuration
  - GCP provider setup
  - API enablement
  - Secret Manager resources
  - IAM bindings
  - Cloud Run service
  - Optional Cloud Build trigger

- **`variables.tf`**: Input variable definitions
  - Project configuration
  - Secrets
  - Resource sizing
  - Feature flags

- **`outputs.tf`**: Output values after deployment
  - Service URL
  - Secret IDs
  - Service account email
  - Next steps

- **`terraform.tfvars.example`**: Template for your configuration
  - Copy to `terraform.tfvars` and fill in values
  - **DO NOT** commit `terraform.tfvars` (contains secrets)

## Important Variables

### Required

```hcl
project_id        = "your-gcp-project-id"
anthropic_api_key = "sk-ant-xxxxx"
github_token      = "ghp_xxxxx"
```

### Optional (with defaults)

```hcl
region                     = "us-central1"
service_name               = "architecture-kb-orchestrator"
webhook_url                = ""
memory                     = "512Mi"
cpu                        = "1"
timeout_seconds            = 300
max_instances              = "10"
min_instances              = "0"
allow_unauthenticated      = true
enable_cloud_build_trigger = false
```

## State Management

By default, Terraform stores state locally in `terraform.tfstate`. For team environments, use a GCS backend:

1. Create a GCS bucket for state:
```bash
gsutil mb gs://your-terraform-state-bucket
```

2. Uncomment and configure the backend in `main.tf`:
```hcl
backend "gcs" {
  bucket = "your-terraform-state-bucket"
  prefix = "dependency-orchestrator"
}
```

3. Initialize with the backend:
```bash
terraform init -migrate-state
```

## Updating Secrets

### Option 1: Via Terraform

Update `terraform.tfvars` and run:
```bash
terraform apply
```

### Option 2: Via gcloud

```bash
echo -n "new-value" | gcloud secrets versions add anthropic-api-key --data-file=-
echo -n "new-value" | gcloud secrets versions add github-token --data-file=-
echo -n "new-value" | gcloud secrets versions add webhook-url --data-file=-
```

**Note:** If you update secrets via gcloud, Terraform will show a diff on next apply due to `ignore_changes` lifecycle rule. This is expected behavior.

## Updating the Application

Terraform manages infrastructure, not application code. To update your application:

1. **Update code** in your repository
2. **Deploy** using deployment scripts:
   ```bash
   ./deploy-gcp.sh           # Local build
   # OR
   ./deploy-gcp-cloudbuild.sh # Cloud Build
   ```

Terraform will **not** change the container image once deployed (see `lifecycle.ignore_changes` in `main.tf`).

## Cloud Build Trigger (Optional)

Enable automatic deployments on git push:

1. In `terraform.tfvars`:
```hcl
enable_cloud_build_trigger = true
github_repo_owner          = "your-github-username"
github_repo_name           = "dependency-orchestrator"
github_repo_branch         = "main"
```

2. **Connect GitHub** to Cloud Build (one-time setup):
   - Go to: https://console.cloud.google.com/cloud-build/triggers
   - Click "Connect Repository"
   - Follow prompts to connect your GitHub account

3. Apply Terraform:
```bash
terraform apply
```

Now, pushing to the specified branch will automatically trigger a build and deployment.

## Viewing Resources

```bash
# Show current outputs
terraform output

# Show full state
terraform show

# View service URL
terraform output service_url

# List all resources
terraform state list
```

## Destroying Resources

To remove all created resources:

```bash
terraform destroy
```

**Warning:** This will delete the Cloud Run service, secrets, and all associated resources.

## Troubleshooting

### "Error 403: Permission denied"

Ensure your account has the required roles:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/editor"
```

### "API not enabled"

Terraform should enable APIs automatically. If it fails, enable manually:
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### "Secret already exists"

If secrets exist from previous setup, either:
- Import them: `terraform import google_secret_manager_secret.anthropic_api_key projects/PROJECT_ID/secrets/anthropic-api-key`
- Delete and recreate: `gcloud secrets delete anthropic-api-key`

### Container image not updating

This is expected. Terraform manages infrastructure, not application code. Use deployment scripts to update the image.

## Best Practices

1. **Use remote state** (GCS backend) for team environments
2. **Don't commit** `terraform.tfvars` or `*.tfstate` files
3. **Run `terraform plan`** before `apply` to review changes
4. **Use workspaces** for multiple environments (dev/staging/prod):
   ```bash
   terraform workspace new dev
   terraform workspace new prod
   terraform workspace select dev
   ```
5. **Tag releases** and track which Terraform version deployed what
6. **Use Secret Manager** (via Terraform) instead of environment variables

## Integration with Deployment Scripts

The deployment scripts (`deploy-gcp.sh` and `deploy-gcp-cloudbuild.sh`) complement Terraform:

- **Terraform**: Sets up infrastructure (secrets, IAM, service skeleton)
- **Deployment scripts**: Build and deploy application code

**Typical workflow:**
1. Run Terraform once to set up infrastructure
2. Use deployment scripts for subsequent code updates
3. Run Terraform again only when infrastructure changes (scaling, new secrets, etc.)
