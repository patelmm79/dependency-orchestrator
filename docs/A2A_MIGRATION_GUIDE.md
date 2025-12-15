# A2A Migration Guide

This guide helps you migrate from v1.0 (webhook-only) to v2.0 (A2A-enabled) Dependency Orchestrator.

## Overview of Changes

### What's New in v2.0

1. **A2A Protocol Support**: Full Agent-to-Agent protocol implementation with 7 standardized skills
2. **Async Task Processing**: Redis-backed task queue for long-running triage operations
3. **Multi-Process Architecture**: Web server + worker processes managed by Supervisor
4. **AgentCard Discovery**: Published at `/.well-known/agent.json` for automatic discovery
5. **Bidirectional Agent Communication**: Can call other A2A agents (e.g., dev-nexus)

### What's Unchanged

- **Legacy webhook endpoints** remain fully functional (`/api/webhook/*`, `/api/test/*`)
- **Triage agents** (consumer and template) logic unchanged
- **Configuration format** (relationships.json) unchanged
- **GitHub Actions integration** unchanged

## Migration Checklist

### For Existing Deployments

- [ ] Review new architecture and cost implications (~$45/month added for Redis)
- [ ] Set up Redis Memorystore for async task processing
- [ ] Update Cloud Run deployment with VPC connector
- [ ] Update environment variables to include `REDIS_URL`
- [ ] Deploy new multi-process container image
- [ ] Test legacy webhook endpoints (should work unchanged)
- [ ] Test new A2A endpoints (AgentCard, skills, execute)
- [ ] Update monitoring/alerting for multi-process setup
- [ ] Update documentation with new service URL structure

### For New Deployments

- [ ] Follow updated deployment guide in CLAUDE.md
- [ ] Run `./setup-redis-memorystore.sh` before deploying
- [ ] Update `cloudbuild.yaml` with Redis connection details
- [ ] Deploy using `./deploy-gcp-cloudbuild.sh`
- [ ] Verify A2A endpoints are accessible
- [ ] Configure GitHub Actions in source repositories

## Breaking Changes

**None!** The migration is fully backward compatible. All v1.0 endpoints and functionality remain unchanged.

## New Environment Variables

```bash
# Required for A2A async features
export REDIS_URL="redis://10.x.x.x:6379/0"

# All other environment variables remain the same
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
export DEV_NEXUS_URL="https://dev-nexus-url"  # optional
```

## Architecture Changes

### v1.0 Architecture (Legacy)
```
GitHub Actions → Cloud Run (single process)
                    ↓
              Triage Agents → Claude API
                    ↓
              GitHub Issues + Notifications
```

### v2.0 Architecture (A2A)
```
GitHub Actions or A2A Agents → Cloud Run (web process)
                                    ↓
                              Redis Task Queue
                                    ↓
                              RQ Workers (2 processes)
                                    ↓
                              Triage Agents → Claude API
                                    ↓
                              GitHub Issues + Notifications

Supervisor manages: [web process] + [2 worker processes]
```

## File Structure Changes

### New Files
```
orchestrator/
├── a2a/                           # NEW: A2A protocol implementation
│   ├── __init__.py
│   ├── base.py                    # Base skill classes
│   ├── registry.py                # Skills registry
│   ├── server.py                  # A2A FastAPI server
│   ├── client.py                  # A2A client for other agents
│   ├── task_queue.py              # Redis Queue management
│   ├── tasks.py                   # Background task functions
│   └── skills/                    # A2A skills
│       ├── __init__.py
│       ├── receive_change_notification.py
│       ├── get_impact_analysis.py
│       ├── get_dependencies.py
│       ├── get_orchestration_status.py
│       ├── trigger_consumer_triage.py
│       ├── trigger_template_triage.py
│       └── add_dependency_relationship.py
├── app_unified.py                 # NEW: Unified A2A + legacy server
└── worker.py                      # NEW: RQ worker entry point

supervisord.conf                   # NEW: Process manager config
setup-redis-memorystore.sh         # NEW: Redis setup script
docs/A2A_MIGRATION_GUIDE.md       # NEW: This document
```

### Modified Files
```
requirements.txt                   # Added redis, rq, supervisor
Dockerfile                         # Multi-process setup with Supervisor
cloudbuild.yaml                    # Added VPC connector and Redis URL
deploy-gcp-cloudbuild.sh          # Added Redis API enablement
CLAUDE.md                          # Added A2A documentation
```

### Unchanged Files
```
orchestrator/
├── agents/                        # Triage agents unchanged
│   ├── consumer_triage.py
│   └── template_triage.py
├── clients/                       # Dev-nexus client unchanged
│   └── dev_nexus_client.py
└── app.py                         # Legacy app (deprecated, use app_unified.py)

config/relationships.json          # Configuration unchanged
```

## Deployment Changes

### Old Deployment (v1.0)
```bash
# Two steps: infrastructure + app
./deploy-gcp-cloudbuild.sh
```

### New Deployment (v2.0)
```bash
# Three steps: infrastructure + redis + app

# 1. Infrastructure (Terraform or deployment script)
terraform apply
# or
./deploy-gcp-cloudbuild.sh

# 2. Redis Memorystore (one-time)
./setup-redis-memorystore.sh

# 3. Update cloudbuild.yaml with Redis URL, then redeploy
./deploy-gcp-cloudbuild.sh
```

## Testing the Migration

### 1. Verify Legacy Endpoints Still Work
```bash
# Health check
curl https://your-service-url/

# Legacy webhook (should work unchanged)
curl -X POST https://your-service-url/api/webhook/change-notification \
  -H "Content-Type: application/json" \
  -d @test/sample_event.json

# Legacy test endpoints
curl -X POST https://your-service-url/api/test/consumer-triage \
  -H "Content-Type: application/json" \
  -d @test/consumer_test.json
```

### 2. Verify A2A Endpoints Work
```bash
# AgentCard discovery
curl https://your-service-url/.well-known/agent.json

# List skills
curl https://your-service-url/a2a/skills

# A2A health check
curl https://your-service-url/a2a/health

# Execute a skill (get dependencies)
curl -X POST https://your-service-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "get_dependencies",
    "input_data": {"repo": "owner/repo"}
  }'
```

### 3. Verify Async Task Processing
```bash
# Trigger async triage
RESPONSE=$(curl -X POST https://your-service-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "trigger_consumer_triage",
    "input_data": {
      "source_repo": "owner/source",
      "consumer_repo": "owner/consumer",
      "change_event": {...}
    }
  }')

# Extract task_id from response
TASK_ID=$(echo $RESPONSE | jq -r '.data.task_id')

# Poll task status
curl -X POST https://your-service-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d "{
    \"skill_name\": \"get_orchestration_status\",
    \"input_data\": {\"task_id\": \"$TASK_ID\"}
  }"
```

## Rollback Plan

If you need to rollback to v1.0:

1. **Keep the old deployment tagged in GCR**:
   ```bash
   # Before deploying v2.0, tag current version
   docker tag gcr.io/$PROJECT_ID/architecture-kb-orchestrator:latest \
              gcr.io/$PROJECT_ID/architecture-kb-orchestrator:v1.0-stable
   docker push gcr.io/$PROJECT_ID/architecture-kb-orchestrator:v1.0-stable
   ```

2. **Rollback deployment**:
   ```bash
   gcloud run deploy architecture-kb-orchestrator \
     --image gcr.io/$PROJECT_ID/architecture-kb-orchestrator:v1.0-stable \
     --region us-central1 \
     --remove-vpc-connector \
     --remove-env-vars REDIS_URL
   ```

3. **Redis Memorystore** can be left running or deleted:
   ```bash
   # Delete if no longer needed (will stop billing)
   gcloud redis instances delete orchestrator-task-queue \
     --region us-central1
   ```

## Cost Impact

### v1.0 Costs
- Cloud Run: ~$50/month (estimated, varies with usage)

### v2.0 Costs
- Cloud Run: ~$50/month (same, slightly more CPU/RAM but similar usage)
- Redis Memorystore: ~$45/month (Basic tier, 1GB)
- VPC Connector: ~$0 (no additional cost)
- **Total: ~$95/month**

## Support

For issues or questions about the A2A migration:
- Check the updated CLAUDE.md documentation
- Review the conversion plan: https://github.com/patelmm79/dev-nexus/blob/main/docs/DEPENDENCY_ORCHESTRATOR_A2A_CONVERSION_PLAN.md
- Review A2A protocol docs: https://a2a-protocol.org/latest/

## Timeline

- **v1.0**: Legacy webhook-only version (deprecated)
- **v2.0**: A2A-enabled version (current)
- **Deprecation**: v1.0 endpoints will be maintained indefinitely for backward compatibility
- **Recommended**: All new deployments should use v2.0
