# Terraform A2A Updates Summary

## Overview

Terraform configuration has been fully updated to support A2A v2.0 deployment with Redis Memorystore, VPC connector, and multi-process Cloud Run setup.

## What Was Updated

### main.tf
✅ **Added A2A APIs**:
- `redis.googleapis.com` - Redis Memorystore
- `vpcaccess.googleapis.com` - VPC connector
- `compute.googleapis.com` - Compute Engine for VPC

✅ **Added VPC Connector Resource**:
- Creates VPC connector for Cloud Run → Redis connectivity
- Default name: `orchestrator-redis-connector`
- Default CIDR: `10.8.0.0/28`
- Min/max instances: 2-3

✅ **Added Redis Memorystore Resource**:
- Redis 7.0 instance for task queue
- Default name: `orchestrator-task-queue`
- Default tier: BASIC (1GB)
- Authorized on default VPC network
- Labels for cost tracking

✅ **Updated Cloud Run Service**:
- Added VPC connector annotation
- Added `REDIS_URL` environment variable (auto-configured from Redis instance)
- Added `DEV_NEXUS_URL` environment variable
- Increased memory: 512Mi → 1Gi
- Increased CPU: 1 → 2

### variables.tf
✅ **Updated Resource Defaults**:
- `memory`: "512Mi" → "1Gi" (required for multi-process)
- `cpu`: "1" → "2" (required for web + workers)

✅ **Added A2A Variables**:
- `vpc_network` - VPC network name (default: "default")
- `vpc_connector_name` - VPC connector name
- `vpc_connector_cidr` - CIDR range for connector
- `redis_instance_name` - Redis instance name
- `redis_tier` - BASIC or STANDARD_HA
- `redis_memory_gb` - Redis memory size
- `dev_nexus_url` - Dev-nexus integration URL

### outputs.tf
✅ **Added A2A Outputs**:
- `redis_host` - Redis IP address
- `redis_port` - Redis port
- `redis_url` - Full Redis connection URL
- `vpc_connector` - VPC connector ID
- `agent_card_url` - A2A AgentCard discovery URL
- `a2a_endpoints` - Map of all A2A endpoints

✅ **Updated Next Steps Output**:
- Shows A2A resources created
- Includes Redis connection details
- Lists A2A testing endpoints
- Shows estimated monthly cost (~$95)

### terraform.tfvars.example
✅ **Updated Example Configuration**:
- Increased default resources (1Gi, 2 CPU)
- Added all A2A variables with descriptions
- Added cost estimates for Redis tiers
- Added dev-nexus integration example

## Deployment Process

### 1. Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:
- **Required**: `project_id`, `anthropic_api_key`, `github_token`
- **Optional**: `webhook_url`, `dev_nexus_url`
- **A2A defaults are already optimized**

### 2. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Review changes
terraform plan

# Deploy
terraform apply
```

**Note**: Terraform will create:
- Secret Manager secrets
- Redis Memorystore instance (~5 minutes)
- VPC connector (~3 minutes)
- Cloud Run service skeleton
- IAM bindings

**Total deployment time**: ~8-10 minutes

### 3. Review Outputs

After `terraform apply`, you'll see:
```
Outputs:

redis_url = "redis://10.x.x.x:6379/0"
vpc_connector = "projects/.../locations/.../connectors/orchestrator-redis-connector"
agent_card_url = "https://.../.well-known/agent.json"
service_url = "https://architecture-kb-orchestrator-xxxxx-uc.a.run.app"

next_steps = <<EOT
✅ A2A Infrastructure deployed successfully!

🔧 A2A Resources Created:
- Redis Memorystore: orchestrator-task-queue (1GB)
- VPC Connector: orchestrator-redis-connector
- Redis URL: redis://10.x.x.x:6379/0

📋 Next steps:
1. Build and deploy your container:
   ./deploy-gcp-cloudbuild.sh
...
EOT
```

### 4. Deploy Application Code

```bash
cd ..
./deploy-gcp-cloudbuild.sh
```

This will:
- Build Docker image with Cloud Build
- Deploy to Cloud Run
- Connect to Redis via VPC connector
- Enable A2A endpoints

### 5. Verify Deployment

```bash
# Get service URL
export SERVICE_URL=$(terraform -chdir=terraform output -raw service_url)

# Test service
curl $SERVICE_URL/

# Test A2A AgentCard
curl $SERVICE_URL/.well-known/agent.json

# Test A2A skills
curl $SERVICE_URL/a2a/skills
```

## Cost Breakdown

**Infrastructure Managed by Terraform:**

| Resource | Configuration | Monthly Cost |
|----------|--------------|--------------|
| Cloud Run | 1Gi RAM, 2 CPU | ~$50 |
| Redis Memorystore | BASIC, 1GB | ~$45 |
| VPC Connector | 2-3 instances | $0 (included) |
| Secret Manager | 4 secrets | ~$0.06 |
| **Total** | | **~$95/month** |

**Cost Optimization Tips:**
- Use `STANDARD_HA` only for production (adds redundancy but costs ~$200/mo)
- Set `min_instances = 1` to reduce cold starts (adds ~$10/mo)
- Use preemptible VPC connector instances (not available yet)

## Infrastructure as Code Benefits

✅ **Reproducible**: Same configuration every time
✅ **Version Controlled**: Track infrastructure changes in git
✅ **Team Collaboration**: Share tfvars, everyone deploys consistently
✅ **State Management**: Terraform tracks all resources
✅ **Easy Updates**: Change variables, run `terraform apply`
✅ **Safe Destruction**: `terraform destroy` removes everything cleanly

## Differences from Manual Setup

### Terraform Approach
- Declares desired state
- Creates all resources in one command
- Manages dependencies automatically
- Tracks resource state
- Handles IAM bindings
- Provides outputs for next steps

### Manual Script Approach (`setup-redis-memorystore.sh`)
- Imperative step-by-step commands
- Checks for existing resources
- Outputs connection details
- Requires manual tracking
- Good for one-off setups

**Recommendation**: Use Terraform for production, scripts for dev/testing.

## Troubleshooting

**Error: VPC connector CIDR conflicts**
```
Solution: Change vpc_connector_cidr in terraform.tfvars
Example: "10.9.0.0/28" or "10.10.0.0/28"
```

**Error: Redis creation timeout**
```
Solution: Redis takes 5-8 minutes to create. This is normal.
If it fails, check quota: gcloud redis operations list
```

**Error: Cloud Run can't connect to Redis**
```
Solution: Verify VPC connector is attached:
gcloud run services describe architecture-kb-orchestrator --format="value(spec.template.metadata.annotations)"
```

**Error: Secrets not accessible**
```
Solution: Check IAM bindings were created:
gcloud secrets get-iam-policy anthropic-api-key
```

## Rollback / Cleanup

### Destroy All Resources
```bash
cd terraform
terraform destroy
```

This removes:
- Cloud Run service
- Redis Memorystore instance
- VPC connector
- Secret Manager secrets
- IAM bindings

**Warning**: This is irreversible. All data in Redis will be lost.

### Preserve Secrets, Destroy Infrastructure
```bash
# Remove resources but keep secrets
terraform destroy -target=google_redis_instance.task_queue
terraform destroy -target=google_vpc_access_connector.redis_connector
terraform destroy -target=google_cloud_run_service.orchestrator
```

## Next Steps

1. ✅ Terraform is fully configured for A2A
2. ✅ Run `terraform apply` to deploy infrastructure
3. ✅ Run `./deploy-gcp-cloudbuild.sh` to deploy application
4. ✅ Test A2A endpoints
5. ✅ Update GitHub Actions in source repos

## References

- **Main Terraform Config**: `terraform/main.tf`
- **Variables**: `terraform/variables.tf`
- **Outputs**: `terraform/outputs.tf`
- **Example Config**: `terraform/terraform.tfvars.example`
- **A2A Migration Guide**: `docs/A2A_MIGRATION_GUIDE.md`
- **A2A Features**: `docs/A2A_README.md`
