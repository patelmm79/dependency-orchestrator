#!/bin/bash
# Setup Redis Memorystore for A2A async task processing

set -e

# Get project ID
if [ -f "terraform/terraform.tfstate" ] && command -v terraform &> /dev/null; then
  PROJECT_ID=$(cd terraform && terraform output -raw project_id 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID="${GCP_PROJECT_ID}"
fi

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: Could not determine GCP project ID"
  exit 1
fi

# Configuration
REGION="${GCP_REGION:-us-central1}"
REDIS_INSTANCE_NAME="orchestrator-task-queue"
REDIS_TIER="basic"
REDIS_SIZE_GB="1"
NETWORK="default"

echo "🔧 Setting up Redis Memorystore for task queue"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Instance: $REDIS_INSTANCE_NAME"
echo "   Tier: $REDIS_TIER (1GB)"
echo ""

# Enable required APIs
echo "📋 Enabling required APIs..."
gcloud services enable redis.googleapis.com --project=$PROJECT_ID
gcloud services enable vpcaccess.googleapis.com --project=$PROJECT_ID
gcloud services enable compute.googleapis.com --project=$PROJECT_ID

# Check if Redis instance already exists
if gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID &>/dev/null; then
  echo "✅ Redis instance '$REDIS_INSTANCE_NAME' already exists"
  REDIS_HOST=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID --format='value(host)')
  REDIS_PORT=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID --format='value(port)')
  echo "   Host: $REDIS_HOST"
  echo "   Port: $REDIS_PORT"
  echo ""
  echo "Redis URL: redis://$REDIS_HOST:$REDIS_PORT/0"
  exit 0
fi

# Create VPC connector for Cloud Run to access Redis
CONNECTOR_NAME="orchestrator-redis-connector"
echo "🔌 Creating VPC connector for Cloud Run..."

if ! gcloud compute networks vpc-access connectors describe $CONNECTOR_NAME --region=$REGION --project=$PROJECT_ID &>/dev/null; then
  gcloud compute networks vpc-access connectors create $CONNECTOR_NAME \
    --region=$REGION \
    --network=$NETWORK \
    --range=10.8.0.0/28 \
    --project=$PROJECT_ID

  echo "✅ VPC connector created: $CONNECTOR_NAME"
else
  echo "✅ VPC connector already exists: $CONNECTOR_NAME"
fi

# Create Redis instance
echo "⏳ Creating Redis Memorystore instance (this may take 3-5 minutes)..."
gcloud redis instances create $REDIS_INSTANCE_NAME \
  --region=$REGION \
  --tier=$REDIS_TIER \
  --size=$REDIS_SIZE_GB \
  --network=$NETWORK \
  --project=$PROJECT_ID

echo ""
echo "✅ Redis Memorystore instance created!"

# Get Redis connection details
REDIS_HOST=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID --format='value(host)')
REDIS_PORT=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID --format='value(port)')

echo ""
echo "📝 Redis connection details:"
echo "   Host: $REDIS_HOST"
echo "   Port: $REDIS_PORT"
echo "   URL: redis://$REDIS_HOST:$REDIS_PORT/0"
echo ""
echo "💡 Set this as REDIS_URL environment variable in Cloud Run deployment"
echo ""
echo "Estimated monthly cost: ~\$45 (Basic tier, 1GB)"
