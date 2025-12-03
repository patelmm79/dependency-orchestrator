#!/bin/bash
# Deploy orchestrator service to GCP Cloud Run

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
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
  --max-instances 10

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
