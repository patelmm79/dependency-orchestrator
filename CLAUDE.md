# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Dependency Orchestrator is an AI-powered service that coordinates automated triage agents to assess the impact of changes across related repositories. When changes occur in one repository, it spawns specialized AI agents to analyze impact on dependent repositories and automatically creates GitHub issues with recommendations.

**Version 2.0** introduces full A2A (Agent-to-Agent) protocol support, enabling seamless interoperability with other AI agents in the ecosystem. The service now operates as both a webhook receiver (legacy mode) and an A2A-compliant agent.

## A2A Protocol Support

### What is A2A?

The Agent-to-Agent (A2A) protocol is an open standard for AI agent communication and collaboration. Dependency Orchestrator exposes its capabilities through standardized A2A endpoints, allowing other agents (like dev-nexus) to discover and invoke orchestration skills programmatically.

### Key Features

- **AgentCard Discovery**: Publish capabilities at `/.well-known/agent.json` for automatic discovery
- **4 A2A Skills**: Synchronous skills for dependency orchestration (events, queries)
- **Stateless Design**: No database or task queue required - uses FastAPI BackgroundTasks
- **Backward Compatible**: Legacy webhook endpoints remain fully functional
- **Low Operational Overhead**: Single container deployment, minimal resources

### A2A Skills Available

The orchestrator exposes 4 skills:

**Events (entry points)**
- `receive_change_notification` - Receive and validate change notifications

**Queries (synchronous data retrieval)**
- `get_impact_analysis` - Synchronously analyze impact of changes on a target repo
- `get_dependencies` - Retrieve dependency graph for a repository

**Actions (mutating operations)**
- `add_dependency_relationship` - Add/update relationship configuration

### Architecture: Stateless Design

**Single-Process Design**:
- FastAPI server: Handles all HTTP requests (A2A + legacy)
- BackgroundTasks: In-process async execution (no separate workers)
- No external database or cache required
- Request → HTTP 202 → Background processing

**Deployment Stack**:
- Cloud Run: Single container, minimal configuration
- No VPC connector, PostgreSQL VM, or Redis needed
- **Estimated cost**: ~$1-5/month (just Cloud Run compute)
- Auto-scales from 0 instances based on traffic

**Why Stateless**:
- Simpler operations (single service, no dependencies)
- Faster deployment (no infrastructure setup)
- Cost-effective (minimal compute needed)
- Dev-nexus handles orchestration state if required

### Using A2A Endpoints

```bash
# Discover agent capabilities
curl https://orchestrator-url/.well-known/agent.json

# List available skills
curl https://orchestrator-url/a2a/skills

# Get synchronous impact analysis
curl -X POST https://orchestrator-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "get_impact_analysis",
    "input_data": {
      "source_repo": "owner/source",
      "target_repo": "owner/consumer",
      "relationship_type": "consumer",
      "change_event": {...}
    }
  }'

# Receive change notification (webhook/A2A)
curl -X POST https://orchestrator-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "receive_change_notification",
    "input_data": {
      "source_repo": "owner/source",
      "commit_sha": "abc123",
      "commit_message": "Fix API endpoint",
      "branch": "main",
      "changed_files": [...]
    }
  }'
```

Note: Async orchestration is handled through background tasks. HTTP 202 indicates task accepted; results are processed asynchronously.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"

# Optional environment variables
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # Discord/Slack notifications
export DEV_NEXUS_URL="https://dev-nexus-xxxxx-uc.a.run.app"  # Dev-nexus integration
export REQUIRE_AUTH="false"  # Set to "true" to require API key authentication
export ORCHESTRATOR_API_KEY="your-api-key-here"  # Required if REQUIRE_AUTH=true
```

### Running Locally
```bash
# Start the service locally (all endpoints work, no external dependencies)
uvicorn orchestrator.app_unified:app --reload --port 8080

# In production, use gunicorn for multi-worker support
gunicorn orchestrator.app_unified:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

### Testing
```bash
# Health check
curl http://localhost:8080/

# A2A AgentCard discovery
curl http://localhost:8080/.well-known/agent.json

# List A2A skills
curl http://localhost:8080/a2a/skills

# A2A health check
curl http://localhost:8080/a2a/health

# View configured relationships
curl http://localhost:8080/api/relationships

# Test consumer triage agent (synchronous)
curl -X POST http://localhost:8080/api/test/consumer-triage \
  -H "Content-Type: application/json" \
  -d @test/consumer_test.json

# Test template triage agent (synchronous)
curl -X POST http://localhost:8080/api/test/template-triage \
  -H "Content-Type: application/json" \
  -d @test/template_test.json

# Test change notification (processes asynchronously in background)
curl -X POST http://localhost:8080/api/webhook/change-notification \
  -H "Content-Type: application/json" \
  -d '{
    "source_repo": "owner/source",
    "commit_sha": "abc123",
    "commit_message": "Update API",
    "branch": "main",
    "changed_files": []
  }'
```

### Setting Up Source Repositories

⚠️ **CRITICAL**: After deploying the orchestrator, you MUST configure GitHub Actions workflows in your source repositories (e.g., `vllm-container-ngc`) to send change notifications. Without this, the orchestrator won't receive any notifications.

**Complete setup instructions**: `docs/GITHUB_ACTIONS_SETUP.md`

This separate guide includes:
- Full workflow files (not partial snippets)
- Step-by-step secret configuration
- Testing procedures
- Troubleshooting tips

### Deployment

**Stateless Deployment to Cloud Run**

The orchestrator is a stateless FastAPI service that deploys easily to Cloud Run with minimal infrastructure.

**Single-Step Deployment:**
```bash
# Prerequisites
gcloud auth login
gcloud auth configure-docker

# Set your project and secrets
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="us-central1"

# Create secrets in Secret Manager (one-time setup)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional

echo -n "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-
echo -n "$GITHUB_TOKEN" | gcloud secrets create github-token --data-file=-
echo -n "$WEBHOOK_URL" | gcloud secrets create webhook-url --data-file=-

# Deploy using Cloud Build
chmod +x deploy-gcp-cloudbuild.sh
./deploy-gcp-cloudbuild.sh
```

**What this does:**
- Builds Docker image in Cloud Build (no Docker required locally)
- Deploys to Cloud Run with minimal configuration
- Auto-scales from 0 instances based on traffic
- Configures: 512Mi memory, 1 CPU, 300s timeout, max 10 instances
- Pulls secrets from Secret Manager at runtime

**Cost Estimate:** ~$1-5/month (just Cloud Run compute, no databases)

**View Logs:**
```bash
# View recent logs
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator" --limit 50

# Stream logs in real-time
gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator"
```

## Architecture

### High-Level Flow
```
GitHub Actions (source repo)
  → POST /api/webhook/change-notification
  → Orchestrator loads config/relationships.json
  → Spawns appropriate triage agents based on relationship type
  → Agents use Claude API to analyze impact
  → Creates GitHub issues in target repos if action required
  → Sends notifications (Discord/Slack) for critical issues
```

### Core Components

**orchestrator/app.py** - FastAPI service that:
- Receives webhook notifications from CI/CD pipelines
- Loads relationship configuration from `config/relationships.json`
- Dispatches background tasks to process consumer and template relationships
- Creates GitHub issues and sends notifications based on triage results
- Provides test endpoints for agent validation

**orchestrator/agents/consumer_triage.py** - Analyzes impact of API/service changes on consumers:
- Fetches consumer's interface code (files that interact with the provider)
- Filters changes based on configured triggers (api_contract, authentication, deployment, etc.)
- Uses Claude to analyze if changes are breaking and determine urgency
- Returns structured triage result with action recommendations

**orchestrator/agents/template_triage.py** - Analyzes template/fork sync opportunities:
- Filters changes to shared concerns (infrastructure, docker, gpu_configuration, etc.)
- Excludes divergent concerns (application_logic, model_specific, api_endpoints)
- Fetches derivative's current state of changed files
- Uses Claude to determine if changes should backport to derivative

**config/relationships.json** - Defines repository dependency graph:
- Maps service providers to their consumers and derivatives
- Specifies interface files, change triggers, and shared/divergent concerns
- Configures urgency mappings and notification settings

**orchestrator/clients/dev_nexus_client.py** - Integrates with dev-nexus knowledge base (optional):
- Queries deployment patterns and architecture context before analysis
- Posts lessons learned after each triage analysis
- Enriches triage prompts with cross-repo knowledge
- Enables continuous learning across the entire codebase ecosystem

### Dev-Nexus Integration

The orchestrator integrates with [dev-nexus](https://github.com/patelmm79/dev-nexus) (if configured) to:

1. **Query Architecture Context**: Before analyzing changes, triage agents query dev-nexus for:
   - Deployment platform information
   - Recent lessons learned
   - Reusable components identified
   - Cross-repo pattern insights

2. **Contribute Lessons Learned**: After analysis, agents post insights back to dev-nexus:
   - Consumer impact patterns
   - Template sync recommendations
   - Breaking change detection learnings
   - Confidence scores for future reference

3. **Enrich Analysis**: Architecture context from dev-nexus is included in LLM prompts, improving:
   - Accuracy of impact assessment
   - Understanding of deployment dependencies
   - Recognition of common patterns
   - Confidence in recommendations

**Configuration**: Set `DEV_NEXUS_URL` environment variable to enable integration. If not set, orchestrator works normally without dev-nexus features.

### Relationship Types

**Consumer Relationships** (`api_consumer`):
- For API dependencies where one service consumes another's API
- Example: `resume-customizer` consumes `vllm-container-ngc` API
- Key config: `interface_files`, `change_triggers`, `urgency_mapping`

**Template Relationships** (`template_fork`):
- For repositories that share infrastructure but have diverged in application logic
- Example: `vllm-container-coder` derived from `vllm-container-ngc` template
- Key config: `shared_concerns`, `divergent_concerns`, `sync_strategy`

### Triage Agent Behavior

Both agents use Claude Sonnet 4 (`claude-sonnet-4-20250514`) to analyze changes. The LLM receives:
- Source repository changes (diffs, commit message, pattern summary)
- Target repository context (interface files or current state)
- Relationship configuration (triggers, concerns)

The LLM returns structured JSON with:
- `requires_action`: Whether target repo needs changes
- `urgency`: critical|high|medium|low
- `impact_summary`: Brief description of impact
- `affected_files`: Files in target repo that need updating
- `recommended_changes`: Detailed recommendations
- `confidence`: 0.0-1.0 score
- `reasoning`: Explanation of analysis

### Issue Creation Logic

Issues are created based on urgency thresholds in `config/relationships.json`:
- **critical**: Creates issue immediately with labels `dependency`, `urgent`, `breaking-change` + webhook notification
- **high**: Creates issue immediately with labels `dependency`, `important` + webhook notification
- **medium**: Creates issue with labels `dependency`, `enhancement`
- **low**: Adds to digest (future feature)

## Configuration

### Adding New Relationships

Edit `config/relationships.json`:

```json
{
  "relationships": {
    "owner/source-repo": {
      "type": "service_provider",
      "consumers": [
        {
          "repo": "owner/consumer-repo",
          "relationship_type": "api_consumer",
          "interface_files": ["src/client.py", "config/service.yaml"],
          "change_triggers": ["api_contract", "authentication", "deployment"]
        }
      ],
      "derivatives": [
        {
          "repo": "owner/derivative-repo",
          "relationship_type": "template_fork",
          "shared_concerns": ["infrastructure", "docker", "gpu_configuration"],
          "divergent_concerns": ["application_logic", "model_specific"]
        }
      ]
    }
  }
}
```

### Change Triggers (Consumer Relationships)
- `api_contract`: API endpoints, routes, schemas
- `authentication`: Auth mechanisms, tokens, security
- `deployment`: Docker configs, ports, environment variables
- `configuration`: Config files, settings
- `endpoints`: URL paths, API routes

### Concerns (Template Relationships)

**Shared Concerns** (should sync):
- `infrastructure`, `docker`, `deployment`, `gpu_configuration`, `health_checks`, `logging`, `monitoring`

**Divergent Concerns** (should NOT sync):
- `application_logic`, `model_specific`, `api_endpoints`, `business_logic`

## Important Implementation Notes

### Background Task Processing
The orchestrator uses FastAPI's `BackgroundTasks` to process triage agents asynchronously. The webhook endpoint returns immediately after scheduling tasks, preventing timeout issues with CI/CD pipelines.

### GitHub API Rate Limits
Both triage agents limit file fetches to 5 files and truncate content to avoid hitting GitHub API rate limits and Claude context limits. Files over 100KB are skipped.

### LLM Response Parsing
Agent responses strip markdown code blocks (````json`) before JSON parsing to handle cases where Claude wraps responses in code blocks.

### Error Handling
Agents return `requires_action: false` with error details in `reasoning` when analysis fails, preventing false positives from errors.

### Filtering Logic
Consumer triage uses keyword matching on patterns/keywords and file paths to determine relevance. Template triage requires shared concerns to outweigh divergent concerns for changes to be considered relevant.

## Debugging Tips

- Check orchestrator logs for triage agent execution and results
- Use test endpoints (`/api/test/consumer-triage`, `/api/test/template-triage`) to validate agent behavior without triggering real webhooks
- Verify GitHub token has repo access to all configured repositories
- Ensure ANTHROPIC_API_KEY is valid and has sufficient credits
- Review created issues to assess if urgency levels and recommendations are appropriate
