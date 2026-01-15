# Dependency Orchestrator - Architecture Documentation

## Version 2.0 - Stateless Architecture

The Dependency Orchestrator is a stateless AI-powered service that coordinates automated triage agents to assess the impact of changes across related repositories.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR ECOSYSTEM                              │
└─────────────────────────────────────────────────────────────────────────┘

                          Source Repository
                          (e.g., vllm-container-ngc)
                                   │
                    GitHub Actions (Pattern Analyzer)
                                   │
                                   ▼
                    POST /api/webhook/change-notification
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
   Webhook Receiver        Relationship Registry      A2A Protocol Server
   (Accept & Return)       (Load Dependencies)        (AgentCard Discovery)
   (202 Accepted)          (Identify Dependents)      (4 Synchronous Skills)
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
                                   ▼
                        BackgroundTasks Queue
                        (In-Process FastAPI)
                        (No External Storage)
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
  Consumer Triage         Template Triage           Issue Creation
  Agent                   Agent                     & Notifications
  (API Impact)            (Template Sync)           (GitHub Issues)
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
            GitHub API                    Dev-Nexus (Optional)
            (Create Issues)               (Post Lessons Learned)
```

## System Architecture

### v2.0 - Stateless Design (Current)

**Single Cloud Run Container**:
```
┌──────────────────────────────────────────────────────┐
│   Cloud Run Service (512Mi memory, 1 CPU core)       │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │              FastAPI Application               │ │
│  │                                                │ │
│  │  ┌─────────────┐  ┌──────────────────────┐   │ │
│  │  │   HTTP      │  │  A2A Protocol        │   │ │
│  │  │   Server    │  │  Endpoints           │   │ │
│  │  │             │  │  - /.well-known/...  │   │ │
│  │  │ :8080       │  │  - /a2a/skills       │   │ │
│  │  │             │  │  - /a2a/execute      │   │ │
│  │  └─────────────┘  └──────────────────────┘   │ │
│  │       │                   │                    │ │
│  │       ▼                   ▼                    │ │
│  │  ┌─────────────┐  ┌──────────────────────┐   │ │
│  │  │  Webhook    │  │  A2A Skills          │   │ │
│  │  │  Handler    │  │  (Synchronous)       │   │ │
│  │  │             │  │  - get_dependencies  │   │ │
│  │  │ POST /api/  │  │  - get_impact_...    │   │ │
│  │  │ webhook/... │  │  - add_relationship  │   │ │
│  │  │             │  │  - receive_change_.. │   │ │
│  │  └──────┬──────┘  └──────────────────────┘   │ │
│  │         │                                     │ │
│  │         ▼                                     │ │
│  │  ┌──────────────────────────────────────┐   │ │
│  │  │   BackgroundTasks Queue              │   │ │
│  │  │   (In-Process, No External Storage)  │   │ │
│  │  │                                      │   │ │
│  │  │   • process_consumer_relationship()  │   │ │
│  │  │   • process_template_relationship()  │   │ │
│  │  └──────────────────────────────────────┘   │ │
│  │         │                                     │ │
│  │         ▼                                     │ │
│  │  ┌──────────────────────────────────────┐   │ │
│  │  │   Triage Agents (Async)              │   │ │
│  │  │                                      │   │ │
│  │  │   • ConsumerTriageAgent              │   │ │
│  │  │   • TemplateTriageAgent              │   │ │
│  │  │   • Claude API calls                 │   │ │
│  │  │   • GitHub Issue creation            │   │ │
│  │  │   • Dev-Nexus integration            │   │ │
│  │  └──────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  Environment Variables (from Secret Manager):       │
│  • ANTHROPIC_API_KEY                               │
│  • GITHUB_TOKEN                                    │
│  • WEBHOOK_URL (optional)                          │
│  • DEV_NEXUS_URL (optional)                        │
│  • REQUIRE_AUTH (optional)                         │
└──────────────────────────────────────────────────────┘
```

### Key Features of Stateless Design

**Advantages**:
- ✅ No external database required
- ✅ No Redis/Memorystore needed
- ✅ No VPC Connector overhead
- ✅ Single container deployment
- ✅ Auto-scales to 0 when idle
- ✅ ~$1-5/month cost vs ~$95/month
- ✅ Simplified operations & debugging

**Tradeoffs**:
- ⚠️ Task state not persisted (tasks in queue die on container restart)
- ⚠️ No task status polling (no task_id returned from webhook)
- ⚠️ Async processing limited to container lifetime
- ⚠️ Results posted to dev-nexus for persistence (if configured)

## Component Architecture

### 1. HTTP Server (`orchestrator/app_unified.py`)

**Responsibilities**:
- Receive webhook notifications from source repositories
- Validate incoming change events
- Load relationship configuration from `config/relationships.json`
- Route requests to appropriate handlers
- Return immediate responses to webhooks (202 Accepted)
- Schedule background tasks for async processing
- Serve A2A protocol endpoints

**Key Endpoints**:
```
GET /                              # Health check
GET /.well-known/agent.json        # A2A AgentCard discovery
GET /a2a/health                    # A2A health check
GET /a2a/skills                    # List available A2A skills
POST /a2a/execute                  # Execute A2A skill

GET /api/relationships             # View configured relationships
POST /api/webhook/change-notification  # Receive change events
POST /api/test/consumer-triage     # Test consumer triage agent
POST /api/test/template-triage     # Test template triage agent
```

### 2. Background Task Processor

**Consumer Triage Background Task** (`process_consumer_relationship`):
```python
async def process_consumer_relationship(
    change_event: ChangeEvent,
    consumer_repo: str,
    interface_files: List[str],
    change_triggers: List[str],
    consumer_config: Dict
):
    # 1. Fetch consumer repository interface code
    # 2. Fetch changed files from source repository
    # 3. Filter changes based on triggers
    # 4. Spawn ConsumerTriageAgent with Claude API
    # 5. Parse triage result
    # 6. Create GitHub issue if action_required
    # 7. Post lessons learned to dev-nexus (if configured)
    # 8. Send webhook notification (if configured)
```

**Template Triage Background Task** (`process_template_relationship`):
```python
async def process_template_relationship(
    change_event: ChangeEvent,
    derivative_repo: str,
    shared_concerns: List[str],
    divergent_concerns: List[str],
    derivative_config: Dict
):
    # 1. Fetch derivative repository files
    # 2. Fetch changed files from source repository
    # 3. Filter changes to shared concerns
    # 4. Spawn TemplateTriageAgent with Claude API
    # 5. Parse triage result
    # 6. Create GitHub issue if sync_recommended
    # 7. Post lessons learned to dev-nexus (if configured)
    # 8. Send webhook notification (if configured)
```

### 3. Triage Agents

#### Consumer Triage Agent (`orchestrator/agents/consumer_triage.py`)

**Purpose**: Analyze impact of API/service changes on dependent consumers

**Input**:
- Source repository changes (diffs, commit message, patterns)
- Consumer repository interface code (files that interact with provider)
- Relationship configuration (interface_files, change_triggers, urgency_mapping)

**Analysis Process**:
1. Filter changes based on configured triggers (api_contract, authentication, deployment, etc.)
2. Fetch affected interface files from consumer repo
3. Send to Claude Sonnet for impact analysis
4. Claude determines if changes are breaking, urgency level
5. Return structured triage result

**Output**:
```json
{
  "requires_action": true,
  "urgency": "critical|high|medium|low",
  "impact_summary": "String description of impact",
  "affected_files": ["list", "of", "files"],
  "recommended_changes": "Detailed action recommendations",
  "confidence": 0.85,
  "reasoning": "Explanation of analysis"
}
```

#### Template Triage Agent (`orchestrator/agents/template_triage.py`)

**Purpose**: Identify template improvements to sync to derivatives

**Input**:
- Source repository changes (diffs, commit message, patterns)
- Derivative repository current state (files in shared concerns)
- Relationship configuration (shared_concerns, divergent_concerns)

**Analysis Process**:
1. Filter changes to configured shared concerns (infrastructure, docker, etc.)
2. Check if divergent concerns are affected (should not be)
3. Fetch derivative's current version of affected files
4. Send to Claude Sonnet for sync recommendation
5. Claude determines if sync is valuable, checks for conflicts
6. Return structured triage result

**Output**:
```json
{
  "requires_action": true,
  "urgency": "high|medium|low",
  "sync_recommended": true,
  "impact_summary": "String description",
  "affected_files": ["list", "of", "files"],
  "recommended_changes": "Sync instructions",
  "confidence": 0.88,
  "reasoning": "Explanation"
}
```

### 4. Relationship Configuration (`config/relationships.json`)

**Structure**:
```json
{
  "relationships": {
    "owner/provider-repo": {
      "type": "service_provider",
      "consumers": [
        {
          "repo": "owner/consumer",
          "relationship_type": "api_consumer",
          "interface_files": ["src/client.py", "config/service.yaml"],
          "change_triggers": ["api_contract", "authentication"],
          "urgency_mapping": {
            "api_contract": "critical",
            "authentication": "high"
          }
        }
      ],
      "derivatives": [
        {
          "repo": "owner/derivative",
          "relationship_type": "template_fork",
          "shared_concerns": ["infrastructure", "docker"],
          "divergent_concerns": ["application_logic"],
          "sync_strategy": "sync_on_conflict_free"
        }
      ]
    }
  }
}
```

### 5. A2A Protocol Implementation

**4 Synchronous Skills** (no task_id, all return immediately):

1. **`receive_change_notification`** (Event Entry Point)
   - Input: Change event details
   - Output: List of dependent repos
   - Background: Tasks scheduled immediately

2. **`get_dependencies`** (Graph Query)
   - Input: Repository name
   - Output: Consumer and derivative list

3. **`get_impact_analysis`** (Sync Triage)
   - Input: Source repo, target repo, change event
   - Output: Impact analysis result

4. **`add_dependency_relationship`** (Configuration Action)
   - Input: Relationship definition
   - Output: Success/failure confirmation

### 6. External Integrations

#### GitHub API (`orchestrator/clients/github_client.py`)

**Operations**:
- Fetch repository file content
- Create GitHub issues in target repositories
- Add labels, assignees, and descriptions to issues
- Handle API rate limits gracefully

#### Dev-Nexus Integration (`orchestrator/clients/dev_nexus_client.py`)

**Operations** (if `DEV_NEXUS_URL` configured):
- Query architecture context before triage (optional)
- Post lessons learned after triage (optional)
- Enable cross-repo knowledge sharing
- Improve triage accuracy over time

#### Webhook Notifications (`orchestrator/clients/webhook_client.py`)

**Operations** (if `WEBHOOK_URL` configured):
- Send Discord/Slack notifications for critical issues
- Include issue summary, urgency, recommended actions
- Help ops teams stay informed of breaking changes

## Data Flow

### Change Detection to Issue Creation

```
1. Source Repository Push
   └─> GitHub Actions workflow triggers
       └─> Pattern Analyzer extracts changes
           └─> POST /api/webhook/change-notification

2. Orchestrator Receives Notification
   └─> Validates change event
   └─> Returns 202 Accepted immediately
   └─> Schedules background tasks

3. Background Task Processing (Async)

   For each Consumer:
   ├─> Fetch consumer interface files
   ├─> Filter changes by triggers
   ├─> Call ConsumerTriageAgent
   ├─> Create GitHub issue (if required_action=true)
   └─> Post to dev-nexus (if configured)

   For each Derivative:
   ├─> Fetch derivative's current state
   ├─> Filter changes to shared concerns
   ├─> Call TemplateTriageAgent
   ├─> Create GitHub issue (if sync_recommended=true)
   └─> Post to dev-nexus (if configured)

4. Issue Creation in Target Repository
   ├─> Add labels based on urgency
   ├─> Include triage analysis in description
   ├─> Include recommended changes
   └─> Notify dependent teams

5. Results Persistence (Optional)
   └─> Post lessons learned to dev-nexus
       └─> Archived for future reference
       └─> Used to improve triage accuracy
```

## Request/Response Lifecycle

### Webhook Request

```
Request Arrival (< 1ms)
    │
    ▼
Validate Event (< 10ms)
    │
    ├─> Check required fields
    ├─> Parse change summary
    └─> Load relationships

    │
    ▼
Identify Dependents (< 50ms)
    │
    ├─> Find consumers in config
    ├─> Find derivatives in config
    └─> Filter for relevance

    │
    ▼
Return 202 Accepted (< 100ms total)
    │
    ├─> Respond to caller immediately
    └─> Include list of dependents in response

    │
    ▼
Schedule Background Tasks (async)
    │
    ├─> Queue consumer triage tasks
    └─> Queue template triage tasks

    │
    ▼
Process Async (30-60 seconds each)
    │
    ├─> Fetch code context
    ├─> Call Claude API
    ├─> Create issues / send notifications
    └─> Post to dev-nexus
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Webhook validation | < 100ms | Sync, returns immediately |
| get_dependencies query | 50-200ms | Graph lookup, no API calls |
| Receive change notification | < 200ms | Identify dependents, schedule tasks |
| Background task startup | < 1s | Immediate after return |
| Consumer triage (async) | 30-60s | Includes Claude API call |
| Template triage (async) | 20-40s | Includes Claude API call |
| GitHub issue creation | 1-3s | Per issue created |
| Dev-nexus integration | 1-2s | Per lesson learned posted |

## Error Handling

### Webhook Errors

```
400 Bad Request      - Invalid request structure
422 Unprocessable    - Missing required fields
500 Server Error     - Unexpected error during processing
```

### Background Task Errors

```
Task Failures (logged but don't block other tasks):
├─> GitHub API rate limit
├─> Claude API error
├─> Network connectivity issue
├─> Repository access denied
└─> File fetch failure

Error Handling Strategy:
├─> Log error details for debugging
├─> Notify ops via webhook (if critical)
├─> Don't create misleading issues
└─> Continue with other dependents
```

## Security Architecture

### Authentication & Authorization

- ✅ API key authentication (optional, configurable)
- ✅ GitHub token scoped to required repos only
- ✅ Anthropic API key encrypted in Secret Manager
- ✅ No plaintext credentials in logs

### Data Protection

- ✅ HTTPS for all external communication
- ✅ No persistent storage of sensitive data
- ✅ Secrets managed via GCP Secret Manager
- ✅ Environment variables injected at runtime

### Network Security

- ✅ Cloud Run public by default (can be restricted)
- ✅ No internal database connections
- ✅ No VPC configuration needed
- ✅ Stateless design eliminates connection pooling risks

## Deployment Architecture

### Cloud Run Configuration

```
Service: architecture-kb-orchestrator
├─> Memory: 512Mi
├─> CPU: 1 core
├─> Timeout: 300 seconds
├─> Max Instances: 10
├─> Min Instances: 0 (auto-scales to 0 when idle)
└─> Concurrency: 80 requests per container

Environment Variables (from Secret Manager):
├─> ANTHROPIC_API_KEY
├─> GITHUB_TOKEN
├─> WEBHOOK_URL (optional)
├─> DEV_NEXUS_URL (optional)
├─> REQUIRE_AUTH (default: false)
└─> [Other runtime settings]
```

### Infrastructure Requirements

**v2.0 Stateless** (Current):
- ✅ Cloud Run service (managed)
- ✅ Secret Manager (for secrets)
- ✅ Cloud Logging (for logs)
- ✅ No database
- ✅ No Redis
- ✅ No VPC connector
- ✅ **~$1-5/month cost**

## Monitoring & Observability

### Logs

```bash
# View recent logs
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator" --limit 50

# Stream logs in real-time
gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator"

# Filter by severity
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND severity=ERROR" --limit 20
```

### Metrics

- Request count
- Request latency (p50, p95, p99)
- Error rate
- Instance count
- Memory utilization
- CPU utilization

### Alerts (Recommended)

- High error rate (> 5%)
- High latency (p95 > 30s)
- Service unavailability
- Out of memory conditions

## Future Architecture Enhancements

1. **Distributed Tracing**: Add tracing for background task execution
2. **Metrics Export**: Export to Prometheus/Grafana
3. **Task Retries**: Add exponential backoff for transient failures
4. **Batch Processing**: Process multiple notifications efficiently
5. **Multi-Region**: Deploy orchestrator across regions
6. **Dashboard**: Web UI for dependency graph visualization
7. **Event Streaming**: Integrate with event bus for other agents

## Comparison with Alternatives

| Feature | Orchestrator | Polling | Webhooks Only |
|---------|--------------|---------|---------------|
| **Real-time Updates** | ✅ Yes | ❌ No | ✅ Yes |
| **Async Processing** | ✅ BackgroundTasks | ✅ External Queue | ❌ Sync only |
| **Cost** | $1-5/month | ~$50+/month | ~$1-2/month |
| **Complexity** | Low | Medium | Low |
| **Scalability** | High (auto-scale) | Medium | Low |
| **Dependencies** | None | Queue Service | None |
| **Multi-Agent** | ✅ A2A Protocol | ⚠️ Custom | ❌ No |

## References

- [CLAUDE.md](./CLAUDE.md) - Development and deployment guide
- [docs/SETUP.md](./docs/SETUP.md) - Deployment instructions
- [docs/A2A_README.md](./docs/A2A_README.md) - A2A protocol documentation
- [A2A_MIGRATION_SUMMARY.md](./A2A_MIGRATION_SUMMARY.md) - Migration from v1.0 to v2.0 stateless
