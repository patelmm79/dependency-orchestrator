# Orchestrator Service Documentation

The Architecture KB Orchestrator is a dependency management service that coordinates automated triage agents to assess the impact of changes across related repositories.

## Overview

When you make a change to one repository, the orchestrator automatically:
1. Receives notification from the pattern analyzer
2. Identifies dependent repositories (consumers or template derivatives)
3. Spawns AI triage agents to analyze impact
4. Creates GitHub issues in affected repositories
5. Sends notifications for critical changes

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
│                    Orchestrator Service (GCP Cloud Run)      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Webhook      │  │ Relationship │  │ Triage Agent │      │
│  │ Receiver     │─▶│ Registry     │─▶│ Dispatcher   │      │
│  └──────────────┘  └──────────────┘  └──────┬───────┘      │
│                                               │              │
│  ┌──────────────────────────────────────────┴──────┐       │
│  │                                                   │       │
│  │  ┌─────────────────────┐  ┌─────────────────┐   │       │
│  │  │ ConsumerTriageAgent │  │TemplateTriageAgt│   │       │
│  │  │ - API impact        │  │ - Sync analysis │   │       │
│  │  └─────────────────────┘  └─────────────────┘   │       │
│  └──────────────────────┬────────────────────────┘         │
└─────────────────────────┼──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub API                                │
│  - Creates issues in dependent repos                         │
│  - Fetches code context                                      │
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
- `PORT` - Service port (default: 8080)

## Deployment

### GCP Cloud Run Deployment

1. **Set environment variables**:
```bash
export GCP_PROJECT_ID="your-project-id"
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
```

2. **Run deployment script**:
```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

3. **Note the service URL** (e.g., `https://architecture-kb-orchestrator-xxxxx-uc.a.run.app`)

### Configure Monitored Repositories

For each monitored repository (e.g., `vllm-container-ngc`):

1. Add the `ORCHESTRATOR_URL` secret:
   - Go to repo Settings → Secrets → Actions
   - Add secret: `ORCHESTRATOR_URL` = your Cloud Run URL

2. Update the workflow file (or it will auto-inherit if using `workflow_call`)

## Local Development

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set environment variables**:
```bash
cp .env.example .env
# Edit .env with your keys
source .env  # Unix
# or
set -a; source .env; set +a  # Alternative
```

3. **Run the service**:
```bash
python orchestrator/app.py
# or
uvicorn orchestrator.app:app --reload --port 8080
```

4. **Test endpoints**:
```bash
# Health check
curl http://localhost:8080/

# View relationships
curl http://localhost:8080/api/relationships

# Test consumer triage (mock)
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
```

## API Reference

### Endpoints

#### `GET /`
Health check endpoint.

**Response**:
```json
{
  "service": "Architecture KB Orchestrator",
  "status": "healthy",
  "version": "1.0.0"
}
```

#### `GET /api/relationships`
Get all configured repository relationships.

#### `POST /api/webhook/change-notification`
Webhook endpoint for pattern analyzer notifications.

**Request Body**:
```json
{
  "source_repo": "patelmm79/vllm-container-ngc",
  "commit_sha": "abc123",
  "commit_message": "Improve health checks",
  "branch": "main",
  "changed_files": [...],
  "pattern_summary": {...},
  "timestamp": "2025-12-02T10:00:00Z"
}
```

**Response**:
```json
{
  "status": "accepted",
  "consumers_scheduled": ["patelmm79/resume-customizer"],
  "derivatives_scheduled": ["patelmm79/vllm-container-coder"],
  "total_dependents": 2
}
```

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

### False positives/negatives

1. Adjust change triggers in relationship config
2. Tune shared/divergent concerns
3. Update triage agent prompts if needed

## Cost Estimation

**GCP Cloud Run**:
- Free tier: 2 million requests/month
- After free tier: ~$0.40 per million requests
- Memory (512Mi): ~$0.0000025 per GB-second
- CPU (1): ~$0.00002 per vCPU-second

**Anthropic API**:
- Claude Sonnet: ~$3 per million input tokens
- Estimated: $0.01-0.05 per triage analysis
- ~100 analyses/month: $1-5

**Total estimated cost**: $5-10/month for moderate usage

## Security

- Service runs on HTTPS (Cloud Run managed)
- Environment variables encrypted at rest
- GitHub token scoped to required repos only
- No persistent storage of sensitive data
- Webhook endpoints can be secured with authentication (configure in Cloud Run)

## Future Enhancements

- [ ] Web dashboard for dependency graph visualization
- [ ] Confidence scoring improvements
- [ ] Batch/digest notifications (daily/weekly)
- [ ] Auto-create PRs (not just issues)
- [ ] Bidirectional template sync detection
- [ ] Historical analysis and trends
- [ ] Custom notification templates
