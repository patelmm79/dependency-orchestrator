# A2A Migration Guide - DEPRECATED ⚠️

## This guide is no longer applicable (v2.0+)

This document describes the migration path for v1.0 (webhook-only) to v2.0 with A2A protocol support **as originally designed with Redis/PostgreSQL task queues**.

However, **v2.0 has been refactored to a fully stateless architecture** that eliminates the need for external databases and task queues entirely.

## Current v2.0 Architecture

**v2.0 is now fully stateless** and uses FastAPI BackgroundTasks for async processing instead of Redis/PostgreSQL. This provides:

- ✅ **Single Cloud Run container** (no multi-process setup)
- ✅ **No external database required** (no PostgreSQL VM)
- ✅ **No Redis Memorystore** needed (~$45/month savings)
- ✅ **No VPC Connector** overhead
- ✅ **~$1-5/month cost** vs $95/month for v1.0

## See Also

For current migration guidance:
- **[A2A_MIGRATION_SUMMARY.md](../A2A_MIGRATION_SUMMARY.md)** - Documents the stateless refactor from v1.0 to v2.0
- **[docs/SETUP.md](./SETUP.md)** - Current deployment guide for stateless v2.0
- **[CLAUDE.md](../CLAUDE.md)** - Complete architecture & development guide

## ARCHIVED CONTENT BELOW (for historical reference only)

---

# A2A Migration Guide (Historical - v2.0 with Redis/PostgreSQL)

This guide helps you migrate from v1.0 (webhook-only) to v2.0 (A2A-enabled with task queues).

## Overview of Changes (Historical)

### What Was New in v2.0 (with Redis)

1. **A2A Protocol Support**: Full Agent-to-Agent protocol implementation with 7 standardized skills
2. **Async Task Processing**: Redis-backed task queue for long-running triage operations
3. **Multi-Process Architecture**: Web server + worker processes managed by Supervisor
4. **AgentCard Discovery**: Published at `/.well-known/agent.json` for automatic discovery
5. **Bidirectional Agent Communication**: Could call other A2A agents (e.g., dev-nexus)

### What Was Unchanged

- **Legacy webhook endpoints** remained fully functional (`/api/webhook/*`, `/api/test/*`)
- **Triage agents** (consumer and template) logic unchanged
- **Configuration format** (relationships.json) unchanged
- **GitHub Actions integration** unchanged

## Migration Checklist (Historical)

### For Existing Deployments

- [ ] Review architecture and cost implications (~$45/month added for Redis)
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

## Breaking Changes (Historical)

**None!** The migration was fully backward compatible. All v1.0 endpoints and functionality remained unchanged.

## New Environment Variables (Historical)

```bash
# Required for A2A async features (no longer needed in v2.0)
export REDIS_URL="redis://10.x.x.x:6379/0"

# All other environment variables remained the same
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
export DEV_NEXUS_URL="https://dev-nexus-url"  # optional
```

## Architecture Changes (Historical)

### v1.0 Architecture (Legacy)
```
GitHub Actions → Cloud Run (single process)
                    ↓
              Triage Agents → Claude API
                    ↓
              GitHub Issues + Notifications
```

### v2.0 Architecture (A2A with Redis - Historical)
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

### v2.0 Architecture (Stateless - Current)
```
GitHub Actions or A2A Agents → Cloud Run (single process)
                                    ↓
                              BackgroundTasks (in-process)
                                    ↓
                              Triage Agents → Claude API
                                    ↓
                              GitHub Issues + Notifications
```

## File Structure Changes (Historical)

### New Files (no longer in v2.0 stateless)
```
orchestrator/
├── a2a/                           # A2A protocol implementation (reduced in v2.0)
│   ├── __init__.py
│   ├── base.py                    # Base skill classes
│   ├── registry.py                # Skills registry
│   ├── server.py                  # A2A FastAPI server
│   ├── client.py                  # A2A client for other agents
│   ├── task_queue.py              # [REMOVED] Redis Queue management
│   ├── tasks.py                   # [REMOVED] Background task functions
│   └── skills/                    # A2A skills (4 synchronous in v2.0)
│       ├── __init__.py
│       ├── receive_change_notification.py
│       ├── get_impact_analysis.py
│       ├── get_dependencies.py
│       ├── get_orchestration_status.py      # [REMOVED]
│       ├── trigger_consumer_triage.py       # [REMOVED]
│       ├── trigger_template_triage.py       # [REMOVED]
│       └── add_dependency_relationship.py
├── app_unified.py                 # Unified A2A + legacy server
└── worker.py                      # [REMOVED] RQ worker entry point

supervisord.conf                   # [REMOVED] Process manager config
setup-redis-memorystore.sh         # [REMOVED] Redis setup script
docs/A2A_MIGRATION_GUIDE.md       # This document
```

### Modified Files (Historical)
```
requirements.txt                   # Added redis, rq, supervisor (now removed)
Dockerfile                         # Multi-process setup with Supervisor (now simplified)
cloudbuild.yaml                    # Added VPC connector and Redis URL (now removed)
deploy-gcp-cloudbuild.sh          # Added Redis API enablement (now removed)
CLAUDE.md                          # Added A2A documentation (now updated)
```

## Deployment Changes (Historical)

### Old Deployment (v1.0)
```bash
# Two steps: infrastructure + app
./deploy-gcp-cloudbuild.sh
```

### New Deployment (v2.0 with Redis - Historical)
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

### Current Deployment (v2.0 Stateless)
```bash
# Single step: deploy with Cloud Build or local Docker
./deploy-gcp-cloudbuild.sh
# or
./deploy-gcp.sh
```

## Testing the Migration (Historical)

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

### 3. Verify Async Task Processing (Historical - no longer applicable)
```bash
# This feature has been removed in the stateless v2.0 refactor
# Background tasks are now processed in-process without task_id tracking
```

## Rollback Plan (Historical)

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

## Cost Impact (Historical)

### v1.0 Costs
- Cloud Run: ~$50/month

### v2.0 Costs with Redis (Historical)
- Cloud Run: ~$50/month
- Redis Memorystore: ~$45/month (Basic tier, 1GB)
- VPC Connector: ~$0
- **Total: ~$95/month**

### v2.0 Costs Stateless (Current)
- Cloud Run: ~$1-5/month (auto-scales to 0)
- **Total: ~$1-5/month** ✅

## References

- **Current Stateless Guide**: [A2A_MIGRATION_SUMMARY.md](../A2A_MIGRATION_SUMMARY.md)
- **Current Setup Guide**: [docs/SETUP.md](./SETUP.md)
- **Architecture & Development**: [CLAUDE.md](../CLAUDE.md)
- **A2A Protocol Docs**: [docs/A2A_README.md](./A2A_README.md)
