# Dependency Orchestrator

> AI-powered dependency coordination service that uses triage agents to assess the impact of changes across related repositories

## What This Does

When you make a change to one repository, the orchestrator automatically:
1. Receives notification from your CI/CD pipeline
2. Identifies dependent repositories based on your configuration
3. Spawns AI triage agents to analyze the impact
4. Creates GitHub issues in affected repositories with detailed recommendations
5. Sends critical notifications via Discord/Slack

## Use Cases

### API Consumer Dependencies
**Problem**: Changes to a service API break dependent applications

**Solution**: ConsumerTriageAgent
- Monitors service provider for API changes
- Analyzes impact on consumer applications
- Detects breaking changes (endpoints, auth, deployment configs)
- Creates urgent issues when action is required

**Example**: `vllm-container-ngc` changes health check endpoint → issue created in `resume-customizer`

### Template Fork Synchronization
**Problem**: Infrastructure improvements in a template should propagate to derivatives

**Solution**: TemplateTriageAgent
- Monitors template repository for infrastructure changes
- Filters to shared concerns (Docker, GPU config, health checks)
- Ignores divergent concerns (application logic, model-specific code)
- Creates enhancement issues with backport recommendations

**Example**: `vllm-container-ngc` optimizes GPU memory → issue created in `vllm-container-coder`

## Architecture

```
Pattern Analyzer (architecture-kb) → HTTP POST → Orchestrator Service
                                                        ↓
                                        Load relationships.json
                                                        ↓
                                    ┌───────────────────┴────────────────┐
                                    ↓                                    ↓
                          Consumer Triage Agent                Template Triage Agent
                          - Fetch consumer code                - Filter shared concerns
                          - Analyze with Claude                - Analyze with Claude
                                    ↓                                    ↓
                            Create GitHub Issues              Create GitHub Issues
```

## Quick Start

### 1. Deploy to GCP Cloud Run

```bash
# Set environment variables
export GCP_PROJECT_ID="your-project-id"
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional

# Deploy
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

This will output your service URL (e.g., `https://dependency-orchestrator-xxxxx-uc.a.run.app`)

### 2. Configure Relationships

Edit `config/relationships.json` to define your repository dependencies:

```json
{
  "relationships": {
    "yourname/service-provider": {
      "type": "service_provider",
      "consumers": [
        {
          "repo": "yourname/consumer-app",
          "relationship_type": "api_consumer",
          "interface_files": ["src/client.py", "config/service.yaml"],
          "change_triggers": ["api_contract", "authentication", "deployment"]
        }
      ],
      "derivatives": [
        {
          "repo": "yourname/derived-service",
          "relationship_type": "template_fork",
          "shared_concerns": ["infrastructure", "docker", "deployment"],
          "divergent_concerns": ["application_logic", "model_specific"]
        }
      ]
    }
  }
}
```

### 3. Set Up GitHub Actions in Source Repositories

**📖 Complete guide: [docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md)**

For each repository you want to monitor, set up GitHub Actions to notify the orchestrator:

#### Option A: With architecture-kb Pattern Analyzer (Recommended)

```yaml
# .github/workflows/pattern-monitoring.yml
name: Pattern Monitoring
on:
  push:
    branches: [main]

jobs:
  analyze:
    uses: patelmm79/architecture-kb/.github/workflows/analyze-reusable.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ORCHESTRATOR_URL: ${{ secrets.ORCHESTRATOR_URL }}
```

#### Option B: Standalone Webhook

```yaml
# .github/workflows/notify-orchestrator.yml
name: Notify Dependency Orchestrator
on:
  push:
    branches: [main]

jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Send notification
        run: |
          curl -X POST ${{ secrets.ORCHESTRATOR_URL }}/api/webhook/change-notification \
            -H "Content-Type: application/json" \
            -d '{"source_repo": "${{ github.repository }}", ...}'
```

**See [GitHub Actions Setup Guide](docs/GITHUB_ACTIONS_SETUP.md) for**:
- Step-by-step setup instructions
- Complete workflow examples
- Troubleshooting common issues
- Advanced configuration options

## Configuration Reference

### Change Triggers

For consumer relationships, specify what types of changes should trigger notifications:

- `api_contract`: API endpoints, routes, schemas
- `authentication`: Auth mechanisms, tokens, security
- `deployment`: Docker configs, ports, environment variables
- `configuration`: Config files, settings
- `endpoints`: URL paths, API routes

### Shared vs Divergent Concerns

For template relationships:

**Shared Concerns** (should sync):
- `infrastructure`: General infra improvements
- `docker`: Dockerfile, docker-compose changes
- `deployment`: Deployment configurations
- `gpu_configuration`: GPU/CUDA settings
- `health_checks`: Health/readiness probes
- `logging`: Logging setup
- `monitoring`: Metrics and monitoring

**Divergent Concerns** (should NOT sync):
- `application_logic`: Business/domain logic
- `model_specific`: ML model configurations
- `api_endpoints`: API route definitions
- `business_logic`: Application-specific code

### Urgency Levels

The orchestrator assigns urgency based on impact:

- **Critical**: Breaking changes causing immediate failures → Creates issue immediately with urgent label
- **High**: Breaking changes causing issues soon → Creates issue immediately
- **Medium**: Non-breaking but important updates → Creates issue
- **Low**: Optional improvements → Adds to digest (future feature)

## API Reference

### `POST /api/webhook/change-notification`

Receive change notifications from CI/CD pipelines.

**Request Body**:
```json
{
  "source_repo": "owner/repo",
  "commit_sha": "abc123",
  "commit_message": "Fix health check endpoint",
  "branch": "main",
  "changed_files": [
    {
      "path": "app.py",
      "change_type": "M",
      "diff": "..."
    }
  ],
  "pattern_summary": {
    "keywords": ["api", "health", "endpoint"],
    "patterns": ["API endpoint modification"]
  },
  "timestamp": "2025-12-02T10:00:00Z"
}
```

**Response**:
```json
{
  "status": "accepted",
  "consumers_scheduled": ["owner/consumer-repo"],
  "derivatives_scheduled": ["owner/derivative-repo"],
  "total_dependents": 2
}
```

### `GET /api/relationships`

Get all configured repository relationships.

### `GET /api/relationships/{owner}/{repo}`

Get relationships for a specific repository.

## Local Development

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional

# Run locally
uvicorn orchestrator.app:app --reload --port 8080
```

### Testing

```bash
# Health check
curl http://localhost:8080/

# Test consumer triage
curl -X POST http://localhost:8080/api/test/consumer-triage \
  -H "Content-Type: application/json" \
  -d @test/consumer_test.json

# Test template triage
curl -X POST http://localhost:8080/api/test/template-triage \
  -H "Content-Type: application/json" \
  -d @test/template_test.json
```

## Monitoring

### View Logs

```bash
# GCP Cloud Run logs
gcloud logging read "resource.labels.service_name=dependency-orchestrator" --limit 50

# Stream logs in real-time
gcloud logging tail "resource.labels.service_name=dependency-orchestrator"
```

### Metrics

Monitor in GCP Console → Cloud Run:
- Request count
- Request latency
- Error rate
- Instance count

## Troubleshooting

### Orchestrator not receiving notifications

1. Verify service is running: `curl <orchestrator-url>/`
2. Check CI/CD logs for connection errors
3. Verify `ORCHESTRATOR_URL` is set correctly

### Triage agents not creating issues

1. Check GitHub token has repo access
2. Verify relationships are configured correctly
3. Review orchestrator logs: `gcloud logging read ...`
4. Test triage endpoints directly

### Too many/few notifications

Tune `change_triggers` in `config/relationships.json`:
- Too many: Remove triggers or increase confidence thresholds
- Too few: Add more triggers or expand shared concerns

## Cost Estimation

**GCP Cloud Run**: ~$1-3/month (mostly free tier)
**Anthropic API**: ~$1-5/month (depends on commit frequency)
**Total**: ~$3-8/month for typical usage

Scales with number of commits and triage analyses.

## Security

- Service runs on HTTPS (Cloud Run managed)
- Environment variables encrypted at rest
- GitHub token scoped to required repos only
- No persistent storage of sensitive data

## Related Projects

- **[architecture-kb](https://github.com/patelmm79/architecture-kb)**: Pattern discovery system that integrates with this orchestrator

## Documentation

- **[SETUP.md](SETUP.md)**: Detailed deployment guide
- **[docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md)**: GitHub Actions workflow setup guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: System architecture and implementation details
- **[docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)**: API authentication configuration
- **[docs/COST_TRACKING.md](docs/COST_TRACKING.md)**: Cost tracking and optimization

## License

MIT

---

**Questions?** Open an issue or check the documentation.
