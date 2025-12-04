#!/bin/bash
# Deploy orchestrator service to GCP Cloud Run

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
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying Architecture KB Orchestrator to GCP Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo ""

# Authenticate with GCP (if needed)
echo "📋 Checking GCP authentication..."
gcloud config set project $PROJECT_ID

# Build and push Docker image
echo "🐋 Building Docker image..."
docker build -t $IMAGE_NAME .

echo "📤 Pushing image to Google Container Registry..."
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" \
  --set-env-vars "GITHUB_TOKEN=${GITHUB_TOKEN}" \
  --set-env-vars "WEBHOOK_URL=${WEBHOOK_URL:-}" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --labels application=dependency-orchestrator,environment=production,managed-by=gcloud-cli,component=orchestration

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Test the service: curl $SERVICE_URL"
echo "2. Add ORCHESTRATOR_URL secret to your monitored repos:"
echo "   Value: $SERVICE_URL"
echo "3. Make a commit to vllm-container-ngc to trigger the flow!"
