#!/bin/bash
# Deploy orchestrator service to GCP Cloud Run using Cloud Build
# This script uses Cloud Build to build and deploy (not local Docker)

set -e

# Try to get project ID from Terraform first, then environment variable, then gcloud config
if [ -f "terraform/terraform.tfstate" ] && command -v terraform &> /dev/null; then
  PROJECT_ID=$(cd terraform && terraform output -raw project_id 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID="${GCP_PROJECT_ID}"
fi

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "your-project-id" ]; then
  echo "❌ Error: Could not determine GCP project ID"
  echo ""
  echo "Please set it using one of these methods:"
  echo "  1. Run terraform apply first (recommended)"
  echo "  2. Set environment variable: export GCP_PROJECT_ID=\"your-project-id\""
  echo "  3. Set gcloud config: gcloud config set project your-project-id"
  exit 1
fi

# Configuration
SERVICE_NAME="architecture-kb-orchestrator"
REGION="${GCP_REGION:-us-central1}"

echo "🚀 Deploying Dependency Orchestrator to GCP Cloud Run (via Cloud Build)"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo ""

# Authenticate with GCP (if needed)
echo "📋 Checking GCP authentication..."
gcloud config set project $PROJECT_ID

# Check if required secrets exist in Secret Manager
echo "🔐 Checking Secret Manager for required secrets..."
SECRETS_MISSING=false

for SECRET_NAME in anthropic-api-key github-token webhook-url; do
  if ! gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID &>/dev/null; then
    echo "❌ Secret '$SECRET_NAME' not found in Secret Manager"
    SECRETS_MISSING=true
  else
    echo "✅ Secret '$SECRET_NAME' exists"
  fi
done

if [ "$SECRETS_MISSING" = true ]; then
  echo ""
  echo "⚠️  Missing secrets detected. Create them with:"
  echo ""
  echo "  # Create secrets (if they don't exist)"
  echo "  echo -n \"\$ANTHROPIC_API_KEY\" | gcloud secrets create anthropic-api-key --data-file=-"
  echo "  echo -n \"\$GITHUB_TOKEN\" | gcloud secrets create github-token --data-file=-"
  echo "  echo -n \"\$WEBHOOK_URL\" | gcloud secrets create webhook-url --data-file=-"
  echo ""
  echo "  # Or update existing secrets"
  echo "  echo -n \"\$ANTHROPIC_API_KEY\" | gcloud secrets versions add anthropic-api-key --data-file=-"
  echo "  echo -n \"\$GITHUB_TOKEN\" | gcloud secrets versions add github-token --data-file=-"
  echo "  echo -n \"\$WEBHOOK_URL\" | gcloud secrets versions add webhook-url --data-file=-"
  echo ""
  read -p "Do you want to continue anyway? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Enable required APIs
echo "🔧 Ensuring required APIs are enabled..."
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable run.googleapis.com --project=$PROJECT_ID
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID
gcloud services enable redis.googleapis.com --project=$PROJECT_ID
gcloud services enable vpcaccess.googleapis.com --project=$PROJECT_ID
gcloud services enable compute.googleapis.com --project=$PROJECT_ID

# Grant Cloud Run access to secrets
echo "🔑 Granting Cloud Run service account access to secrets..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET_NAME in anthropic-api-key github-token webhook-url; do
  gcloud secrets add-iam-policy-binding $SECRET_NAME \
    --member="serviceAccount:$CLOUD_RUN_SA" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID 2>/dev/null || true
done

# Submit build to Cloud Build
echo "☁️  Submitting build to Cloud Build..."
# Generate a build tag using timestamp (since COMMIT_SHA is only available in triggered builds)
BUILD_TAG=$(date +%Y%m%d-%H%M%S)
echo "   Build tag: $BUILD_TAG"

gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_REGION=$REGION,COMMIT_SHA=$BUILD_TAG \
  --project=$PROJECT_ID

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)

echo ""
echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "⚠️  IMPORTANT: A2A async features require Redis Memorystore"
echo ""
echo "To set up Redis for async task processing:"
echo "  ./setup-redis-memorystore.sh"
echo ""
echo "After Redis is set up, redeploy the service with REDIS_URL:"
echo "  Update cloudbuild.yaml to include Redis connection details"
echo ""
echo "Next steps:"
echo "1. Test the service: curl $SERVICE_URL"
echo "2. Test A2A agent card: curl $SERVICE_URL/.well-known/agent.json"
echo "3. Add ORCHESTRATOR_URL secret to your monitored repos: $SERVICE_URL"
echo "4. Make a commit to trigger the flow!"
echo ""
echo "To view build logs:"
echo "  gcloud builds list --limit=5 --project=$PROJECT_ID"
echo ""
echo "To view Cloud Run logs:"
echo "  gcloud logging tail \"resource.labels.service_name=$SERVICE_NAME\" --project=$PROJECT_ID"
