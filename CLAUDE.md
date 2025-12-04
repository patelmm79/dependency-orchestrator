# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Dependency Orchestrator is an AI-powered service that coordinates automated triage agents to assess the impact of changes across related repositories. When changes occur in one repository, it spawns specialized AI agents to analyze impact on dependent repositories and automatically creates GitHub issues with recommendations.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
```

### Running Locally
```bash
# Option 1: Direct Python
python orchestrator/app.py

# Option 2: With uvicorn (recommended for development)
uvicorn orchestrator.app:app --reload --port 8080
```

### Testing
```bash
# Health check
curl http://localhost:8080/

# View configured relationships
curl http://localhost:8080/api/relationships

# Test consumer triage agent
curl -X POST http://localhost:8080/api/test/consumer-triage \
  -H "Content-Type: application/json" \
  -d @test/consumer_test.json

# Test template triage agent
curl -X POST http://localhost:8080/api/test/template-triage \
  -H "Content-Type: application/json" \
  -d @test/template_test.json
```

### Deployment

**Two-Step Process:**
1. **Infrastructure Setup** (one-time): Secrets, IAM, Cloud Run service skeleton
2. **Application Deployment** (ongoing): Build and deploy your code

You can use Terraform for step 1, or let the deployment scripts handle both steps.

---

#### Infrastructure Setup: Option A - Terraform (Recommended)

**Use Terraform to manage infrastructure as code.**

**What Terraform does:**
- Enables required GCP APIs (cloudbuild, run, secretmanager)
- Creates Secret Manager secrets with IAM bindings
- Configures Cloud Run service account with secret access
- Creates Cloud Run service skeleton (no application code yet)
- **Does NOT build or deploy your application**

**Prerequisites:**
```bash
# Install Terraform
# https://developer.hashicorp.com/terraform/downloads

# Authenticate with GCP
gcloud auth login
gcloud auth application-default login

# Navigate to terraform directory
cd terraform

# Copy example tfvars and configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values:
#   - project_id
#   - anthropic_api_key
#   - github_token
#   - webhook_url (optional)
```

**Deploy infrastructure:**
```bash
# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Apply configuration
terraform apply
```

**After Terraform completes, deploy application code (choose one):**

Option A: Cloud Build (no Docker needed)
```bash
cd ..
./deploy-gcp-cloudbuild.sh
```

Option B: Local Docker (faster iteration)
```bash
cd ..
export GCP_PROJECT_ID="your-project-id"
./deploy-gcp.sh
```

**Pros:** Infrastructure as code, reproducible, team collaboration, manages IAM properly
**Cons:** Learning curve, two-step process (infra then app)

---

#### Infrastructure Setup: Option B - Let Scripts Handle It

**The deployment scripts can create infrastructure AND deploy the app in one step.**

Skip to Option 1 or Option 2 below to let the scripts handle infrastructure setup automatically.

---

#### Application Deployment: Option 1 - Local Docker Build

**Builds Docker image locally and deploys to Cloud Run.**

**What this does:**
- Builds Docker image on your machine
- Pushes to Google Container Registry
- Deploys to Cloud Run
- Passes secrets as environment variables (not Secret Manager)

**Prerequisites:**
```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate with GCP
gcloud auth login
gcloud auth configure-docker

# Set required environment variables (these will be passed to Cloud Run)
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="us-central1"  # optional, defaults to us-central1
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
```

**Deploy:**
```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

**What it does:**
1. Builds Docker image locally: `docker build -t gcr.io/$PROJECT_ID/architecture-kb-orchestrator .`
2. Pushes to GCR: `docker push gcr.io/$PROJECT_ID/architecture-kb-orchestrator`
3. Deploys to Cloud Run with `gcloud run deploy`, passing environment variables via `--set-env-vars`
4. Configures: 512Mi memory, 1 CPU, 300s timeout, max 10 instances, unauthenticated access

**Pros:** Faster builds, no GCP build quota usage, simpler for development
**Cons:** Requires Docker locally, environment variables passed as flags (less secure)

---

#### Application Deployment: Option 2 - Cloud Build

**Builds Docker image remotely using Cloud Build and deploys to Cloud Run.**

**What this does:**
- Submits build to Cloud Build (builds in GCP, not locally)
- Pushes to Google Container Registry
- Deploys to Cloud Run
- Uses Secret Manager for secrets (more secure)

**Prerequisites:**
```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate with GCP
gcloud auth login

# Set project
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="us-central1"  # optional, defaults to us-central1

# Create secrets in Secret Manager (one-time setup)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"

echo -n "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-
echo -n "$GITHUB_TOKEN" | gcloud secrets create github-token --data-file=-
echo -n "$WEBHOOK_URL" | gcloud secrets create webhook-url --data-file=-

# To update existing secrets
echo -n "$ANTHROPIC_API_KEY" | gcloud secrets versions add anthropic-api-key --data-file=-
echo -n "$GITHUB_TOKEN" | gcloud secrets versions add github-token --data-file=-
echo -n "$WEBHOOK_URL" | gcloud secrets versions add webhook-url --data-file=-
```

**Deploy:**
```bash
chmod +x deploy-gcp-cloudbuild.sh
./deploy-gcp-cloudbuild.sh
```

**What it does:**
1. Validates that required secrets exist in Secret Manager
2. Enables required GCP APIs (cloudbuild, run, secretmanager)
3. Grants Cloud Run service account access to secrets
4. Submits build to Cloud Build using `cloudbuild.yaml`
5. Cloud Build: builds image, pushes to GCR, deploys to Cloud Run
6. Cloud Run pulls secrets from Secret Manager at runtime

**Pros:** No Docker required locally, secrets managed securely, build logs in GCP, better for CI/CD
**Cons:** Slower builds, uses Cloud Build quota, requires Secret Manager setup

---

#### View logs
```bash
# View recent logs
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator" --limit 50

# Stream logs in real-time
gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator"

# View Cloud Build logs (Cloud Build option only)
gcloud builds list --limit=5
gcloud builds log <BUILD_ID>
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
