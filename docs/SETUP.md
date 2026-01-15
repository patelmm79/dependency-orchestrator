# Orchestrator Service Documentation - v2.0 (Stateless)

The Dependency Orchestrator is a stateless AI-powered service that coordinates automated triage agents to assess the impact of changes across related repositories. It uses FastAPI BackgroundTasks for asynchronous processing without requiring external databases.

## Overview

When you make a change to one repository, the orchestrator automatically:
1. Receives notification via webhook or A2A protocol
2. Identifies dependent repositories (consumers or template derivatives)
3. Spawns AI triage agents asynchronously (using BackgroundTasks)
4. Creates GitHub issues in affected repositories
5. Sends notifications for critical changes
6. Posts lessons learned to dev-nexus (if configured)

## Use Cases

### Use Case 1: API Consumer Relationships
**Scenario**: Service provider changes → API consumers need to adapt

**Example**: `vllm-container-ngc` changes its health check endpoint
- Orchestrator detects the API change
- Spawns consumer triage agent for `resume-customizer`
- Agent analyzes if the change breaks the consumer
- Creates urgent issue if action required

### Use Case 2: Template Fork Relationships
**Scenario**: Template improvements → Derivatives should consider syncing

**Example**: `vllm-container-ngc` improves GPU memory allocation
- Orchestrator detects infrastructure improvement
- Spawns template triage agent for `vllm-container-coder`
- Agent determines if change benefits derivative
- Creates enhancement issue with backport recommendation

## Architecture

### Stateless Design (v2.0)

```
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions (Monitored Repo)             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Pattern Analyzer                                    │   │
│  │  - Detects changes                                   │   │
│  │  - Extracts patterns                                 │   │
│  │  - Notifies orchestrator                             │   │
│  └────────────────┬─────────────────────────────────────┘   │
└───────────────────┼─────────────────────────────────────────┘
                    │ HTTP POST
                    ▼
┌─────────────────────────────────────────────────────────────┐
│        Orchestrator Service (GCP Cloud Run - Stateless)      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Webhook      │  │ Relationship │  │ Triage Agent │      │
│  │ Receiver     │─▶│ Registry     │─▶│ Dispatcher   │      │
│  └──────────────┘  └──────────────┘  └──────┬───────┘      │
│                                              │              │
│                                   ┌──────────▼────────┐     │
│                                   │ BackgroundTasks   │     │
│                                   │ (In-Process)      │     │
│                                   └────────┬─────────┘     │
│                                            │               │
│         ┌──────────────┐  ┌────────────────▼────────────┐  │
│         │ConsumerTriage│  │ TemplateTriage  │ Dev-Nexus │  │
│         │Agent         │  │ Agent           │ Integration│  │
│         └──────────────┘  └─────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub API                                │
│  - Creates issues in dependent repos                         │
│  - Fetches code context                                      │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Dev-Nexus (Optional Integration)                │
│  - Queries architecture context                              │
│  - Stores lessons learned                                    │
│  - Coordinates multi-agent workflows                         │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Relationship Registry

Edit `config/relationships.json` to define dependencies:

```json
{
  "relationships": {
    "patelmm79/vllm-container-ngc": {
      "type": "service_provider",
      "consumers": [
        {
          "repo": "patelmm79/resume-customizer",
          "relationship_type": "api_consumer",
          "interface_files": ["src/llm_client.py"],
          "change_triggers": ["api_contract", "authentication"],
          "urgency_mapping": {
            "api_contract": "critical"
          }
        }
      ],
      "derivatives": [
        {
          "repo": "patelmm79/vllm-container-coder",
          "relationship_type": "template_fork",
          "shared_concerns": ["infrastructure", "docker"],
          "divergent_concerns": ["application_logic"]
        }
      ]
    }
  }
}
```

### Environment Variables

Required:
- `ANTHROPIC_API_KEY` - Claude API key
- `GITHUB_TOKEN` - GitHub Personal Access Token with repo access

Optional:
- `WEBHOOK_URL` - Discord/Slack webhook for notifications
- `DEV_NEXUS_URL` - Dev-nexus URL for architecture integration
- `REQUIRE_AUTH` - Require API key authentication (default: false)
- `PORT` - Service port (default: 8080)

## Deployment

### Single-Step Cloud Run Deployment

The stateless v2.0 architecture simplifies deployment to a single Cloud Run service with no external infrastructure.

#### Prerequisites

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate with GCP
gcloud auth login
gcloud auth configure-docker

# Set environment variables
export GCP_PROJECT_ID="your-gcp-project-id"
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
```

#### Deploy Using Cloud Build (Recommended)

```bash
# Create secrets in Secret Manager (one-time setup)
echo -n "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-
echo -n "$GITHUB_TOKEN" | gcloud secrets create github-token --data-file=-
echo -n "$WEBHOOK_URL" | gcloud secrets create webhook-url --data-file=- 2>/dev/null || true

# Deploy with Cloud Build
chmod +x deploy-gcp-cloudbuild.sh
./deploy-gcp-cloudbuild.sh
```

#### Deploy Using Local Docker

```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

#### Deploy Using Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project_id and secrets

terraform init
terraform plan
terraform apply
```

### Note the Service URL

After deployment, you'll receive a Cloud Run service URL (e.g., `https://architecture-kb-orchestrator-xxxxx-uc.a.run.app`).

### Configure Monitored Repositories

For each monitored repository (e.g., `vllm-container-ngc`):

1. Add the `ORCHESTRATOR_URL` secret:
   - Go to repo Settings → Secrets → Actions
   - Add secret: `ORCHESTRATOR_URL` = your Cloud Run URL

2. Set up GitHub Actions workflow to send change notifications (see GITHUB_ACTIONS_SETUP.md)

## Local Development

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
export DEV_NEXUS_URL="https://dev-nexus-url"  # optional
```

### 3. Run the service

```bash
# Development mode with auto-reload
uvicorn orchestrator.app_unified:app --reload --port 8080
```

### 4. Test endpoints

```bash
# Health check
curl http://localhost:8080/

# A2A AgentCard discovery
curl http://localhost:8080/.well-known/agent.json

# View relationships
curl http://localhost:8080/api/relationships

# Test consumer triage (synchronous)
curl -X POST http://localhost:8080/api/test/consumer-triage \
  -H "Content-Type: application/json" \
  -d '{
    "source_repo": "patelmm79/vllm-container-ngc",
    "consumer_repo": "patelmm79/resume-customizer",
    "test_changes": {
      "commit_message": "Change health check endpoint",
      "changed_files": [{"path": "app.py", "diff": "..."}],
      "pattern_summary": {"keywords": ["api", "endpoint"]}
    }
  }'

# Test template triage (synchronous)
curl -X POST http://localhost:8080/api/test/template-triage \
  -H "Content-Type: application/json" \
  -d '{
    "source_repo": "patelmm79/vllm-container-ngc",
    "derivative_repo": "patelmm79/vllm-container-coder",
    "test_changes": {...}
  }'
```

## API Reference

### Health Check

#### `GET /`
Health check endpoint.

**Response**:
```json
{
  "service": "Dependency Orchestrator",
  "status": "healthy",
  "version": "2.0.0"
}
```

### A2A Protocol Endpoints

#### `GET /.well-known/agent.json`
AgentCard discovery for A2A protocol.

#### `GET /a2a/health`
A2A health check endpoint.

#### `GET /a2a/skills`
List available A2A skills.

#### `POST /a2a/execute`
Execute an A2A skill.

**Request**:
```json
{
  "skill_name": "get_dependencies",
  "input_data": {
    "repo": "owner/repo"
  }
}
```

### Legacy Webhook Endpoints

#### `GET /api/relationships`
Get all configured repository relationships.

#### `POST /api/webhook/change-notification`
Webhook endpoint for change notifications.

**Request Body**:
```json
{
  "source_repo": "patelmm79/vllm-container-ngc",
  "commit_sha": "abc123",
  "commit_message": "Improve health checks",
  "branch": "main",
  "changed_files": [...],
  "pattern_summary": {...},
  "timestamp": "2025-01-15T10:00:00Z"
}
```

**Response**:
```json
{
  "status": "accepted",
  "source_repo": "patelmm79/vllm-container-ngc",
  "dependents": {
    "consumers": ["patelmm79/resume-customizer"],
    "derivatives": ["patelmm79/vllm-container-coder"]
  }
}
```

**Note**: Returns immediately (202 Accepted). Triage happens asynchronously in the background.

## Triage Agents

### Consumer Triage Agent

**Purpose**: Analyze impact of API/service changes on consumers

**Triggers**:
- `api_contract` - API endpoint changes
- `authentication` - Auth mechanism changes
- `deployment` - Deployment config changes
- `configuration` - Environment variable changes
- `endpoints` - Route/URL changes

**Analysis**:
- Fetches consumer's interface code
- Compares with provider changes
- Uses Claude to assess breaking changes
- Determines urgency level

**Urgency Levels**:
- `critical` - Breaking change causing immediate failures
- `high` - Breaking change causing issues soon
- `medium` - Non-breaking but important update
- `low` - Optional improvement

### Template Triage Agent

**Purpose**: Identify template improvements to sync to derivatives

**Shared Concerns** (should sync):
- `infrastructure` - Docker, deployment configs
- `docker` - Dockerfile, docker-compose
- `gpu_configuration` - GPU settings
- `health_checks` - Health/readiness checks
- `logging` - Logging configuration
- `monitoring` - Metrics and monitoring

**Divergent Concerns** (should NOT sync):
- `application_logic` - Business logic
- `model_specific` - Model configurations
- `api_endpoints` - API routes
- `business_logic` - Domain logic

**Analysis**:
- Filters changes to shared concerns
- Fetches derivative's version
- Uses Claude to assess sync value
- Checks for conflicts

## Issue Creation

When a triage agent determines action is required, the orchestrator creates a GitHub issue in the target repository.

**Issue Format**:

```markdown
## Dependency Change Notification

**Source Repository**: patelmm79/vllm-container-ngc
**Commit**: abc1234
**Branch**: main
**Urgency**: HIGH
**Confidence**: 85%

### Impact Summary
The health check endpoint changed from /health to /v1/health...

### Recommended Changes
Update the health check URL in src/llm_client.py line 45...

### Affected Files
- src/llm_client.py
- config/llm_config.yaml
```

**Labels**:
- Critical: `dependency`, `urgent`, `breaking-change`
- High: `dependency`, `important`
- Medium: `dependency`, `enhancement`
- Low: `dependency`, `info`

## Monitoring

### Cloud Run Logs

View orchestrator logs:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=architecture-kb-orchestrator" --limit 50 --format json
```

### Metrics

Monitor in GCP Console:
- Request count
- Request latency
- Error rate
- Instance count

## Troubleshooting

### Orchestrator not receiving notifications

1. Check `ORCHESTRATOR_URL` secret is set in monitored repo
2. Verify orchestrator service is running: `curl <orchestrator-url>/`
3. Check pattern analyzer logs in GitHub Actions

### Triage agents not creating issues

1. Verify `GITHUB_TOKEN` has repo access
2. Check relationship configuration in `config/relationships.json`
3. Review orchestrator logs for errors

### Background tasks not executing

1. Check Cloud Run logs: `gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator"`
2. Verify all environment variables are set correctly
3. Ensure ANTHROPIC_API_KEY and GITHUB_TOKEN are valid

### False positives/negatives

1. Adjust change triggers in relationship config
2. Tune shared/divergent concerns
3. Update triage agent prompts if needed

## Cost Estimation

**GCP Cloud Run** (v2.0 Stateless):
- Free tier: 2 million requests/month
- After free tier: ~$0.40 per million requests
- Memory (512Mi): ~$0.0000025 per GB-second
- CPU (1): ~$0.00002 per vCPU-second
- Auto-scales to 0 when idle

**Anthropic API**:
- Claude Sonnet: ~$3 per million input tokens
- Estimated: $0.01-0.05 per triage analysis
- ~100 analyses/month: $1-5

**Total estimated cost**: $1-5/month for moderate usage (vs ~$95/month for v1.0 with PostgreSQL/Redis)

## Security

- Service runs on HTTPS (Cloud Run managed)
- Environment variables encrypted at rest
- GitHub token scoped to required repos only
- No persistent storage of sensitive data
- No external database connections
- Webhook endpoints secured with optional API key authentication

## Future Enhancements

- [ ] Web dashboard for dependency graph visualization
- [ ] Confidence scoring improvements
- [ ] Batch/digest notifications (daily/weekly)
- [ ] Auto-create PRs (not just issues)
- [ ] Bidirectional template sync detection
- [ ] Historical analysis and trends
- [ ] Custom notification templates
