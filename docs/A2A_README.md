# A2A Protocol Implementation - v2.0

## Overview

Dependency Orchestrator v2.0 is a fully A2A-compliant stateless agent that exposes 4 standardized skills for dependency orchestration and impact analysis across repository relationships.

## What is A2A?

The Agent-to-Agent (A2A) protocol is an open standard developed by Google and donated to the Linux Foundation. It enables seamless communication and collaboration between AI agents built on different frameworks and platforms.

**Key Benefits:**
- **Interoperability**: Connect agents across different platforms (LangGraph, CrewAI, etc.)
- **Task Delegation**: Agents can delegate analysis and coordination tasks
- **Discovery**: AgentCard publishing enables automatic capability discovery
- **Security**: Agents collaborate without exposing internal logic

## AgentCard Discovery

The Dependency Orchestrator publishes its AgentCard at:
```
https://your-service-url/.well-known/agent.json
```

**Example AgentCard:**
```json
{
  "agent": {
    "name": "dependency-orchestrator",
    "display_name": "Dependency Orchestrator",
    "description": "Stateless AI-powered dependency orchestration agent",
    "version": "2.0.0",
    "vendor": "patelmm79",
    "capabilities": [
      "dependency_tracking",
      "impact_analysis",
      "consumer_triage",
      "template_sync",
      "stateless_orchestration"
    ]
  },
  "skills": [...],
  "endpoints": {
    "execute_skill": "/a2a/execute",
    "list_skills": "/a2a/skills",
    "health": "/a2a/health"
  },
  "authentication": {
    "required": false,
    "methods": ["api_key"]
  }
}
```

## Skills Reference (4 Synchronous Skills)

### Events (Entry Points)

#### `receive_change_notification`
Primary entry point for change notifications from source repositories.

**Behavior:**
- Validates incoming change events
- Identifies dependent repositories
- Returns list of dependents for orchestration
- Background tasks trigger async triage (stateless)

**Input:**
```json
{
  "source_repo": "owner/repo",
  "commit_sha": "abc123",
  "commit_message": "feat: add new endpoint",
  "branch": "main",
  "changed_files": [
    {
      "path": "app.py",
      "change_type": "M",
      "diff": "..."
    }
  ],
  "pattern_summary": {
    "keywords": ["api", "endpoint"],
    "patterns": ["API endpoint modification"]
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Output:**
```json
{
  "status": "accepted",
  "source_repo": "owner/repo",
  "dependents": {
    "consumers": ["owner/consumer1", "owner/consumer2"],
    "derivatives": ["owner/fork1"]
  }
}
```

**Note:** Actual orchestration/triage is handled at the HTTP/webhook layer with FastAPI BackgroundTasks. No task_id returned (stateless).

---

### Queries (Synchronous Data Retrieval)

#### `get_impact_analysis`
Synchronously analyze impact of changes on a specific dependent repository.

**Input:**
```json
{
  "source_repo": "owner/source",
  "target_repo": "owner/target",
  "relationship_type": "consumer",
  "change_event": {...}
}
```

**Output:**
```json
{
  "requires_action": true,
  "urgency": "high",
  "impact_summary": "Breaking API changes detected",
  "affected_files": ["src/client.py", "config/api.yaml"],
  "recommended_changes": "Update API client to use new endpoint...",
  "confidence": 0.92,
  "reasoning": "Detected removal of /v1/predict endpoint..."
}
```

**Use Case:** Direct synchronous analysis without queuing (useful for dev-nexus integration).

---

#### `get_dependencies`
Retrieve dependency graph for a repository.

**Input:**
```json
{
  "repo": "owner/repo",
  "include_metadata": false
}
```

**Output:**
```json
{
  "repo": "owner/repo",
  "consumers": [
    {"repo": "owner/consumer1"},
    {"repo": "owner/consumer2"}
  ],
  "derivatives": [
    {"repo": "owner/fork1"}
  ],
  "upstream_dependencies": [
    {
      "repo": "owner/library",
      "relationship_type": "api_consumer"
    }
  ]
}
```

**Use Case:** Graph queries for understanding ecosystem structure and dependencies.

---

### Actions (Mutating Operations)

#### `add_dependency_relationship`
Add or update a repository dependency relationship.

**Input:**
```json
{
  "source_repo": "owner/source",
  "target_repo": "owner/target",
  "relationship_type": "api_consumer|template_fork",
  "config": {
    "interface_files": ["src/client.py"],
    "change_triggers": ["api_contract", "authentication"],
    "shared_concerns": ["infrastructure", "docker"],
    "divergent_concerns": ["application_logic"]
  }
}
```

**Output:**
```json
{
  "status": "updated",
  "source_repo": "owner/source",
  "target_repo": "owner/target",
  "relationship_type": "api_consumer"
}
```

**Use Case:** Dynamic relationship configuration from other agents.

---

## Architecture: Stateless Design

### What Changed from v1.0

| Aspect | v1.0 | v2.0 |
|--------|------|------|
| **Task Queue** | Redis + PostgreSQL | None (BackgroundTasks) |
| **Worker Processes** | 2-3 workers | None (in-process) |
| **Async Skills** | 7 skills (3 async) | 4 skills (all sync) |
| **Deployment** | Multi-container | Single container |
| **Memory** | 1GB | 512Mi |
| **Cost** | ~$95/month | ~$1-5/month |
| **State Persistence** | Task queue | None (stateless) |

### Background Task Processing

When `receive_change_notification` is called:

1. **HTTP Request** → Validats notification, returns 202 Accepted
2. **Background Task** → Scheduled immediately (no queue)
3. **In-Process Execution** → Triage agents run in FastAPI process
4. **Results** → Posted to dev-nexus (if configured) or GitHub issues created

```
Request → Validate → Return 202 → Background Task → Triage → Results
         (< 100ms)              (async, non-blocking)
```

---

## Usage Examples

### 1. Get Agent Capabilities
```bash
curl https://your-orchestrator-url/.well-known/agent.json
```

### 2. List Available Skills
```bash
curl https://your-orchestrator-url/a2a/skills
```

### 3. Query Dependency Graph
```bash
curl -X POST https://your-orchestrator-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "get_dependencies",
    "input_data": {
      "repo": "owner/vllm-container-ngc"
    }
  }'
```

### 4. Analyze Change Impact
```bash
curl -X POST https://your-orchestrator-url/a2a/execute \
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
```

### 5. Receive Change Notification
```bash
curl -X POST https://your-orchestrator-url/a2a/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "receive_change_notification",
    "input_data": {
      "source_repo": "owner/vllm-container-ngc",
      "commit_sha": "abc123",
      "commit_message": "Fix health check endpoint",
      "branch": "main",
      "changed_files": [...]
    }
  }'
```

Returns: `{"status": "accepted", "dependents": {...}}`

**Note:** Returns immediately (202). Triage happens asynchronously in background.

---

## Integration with Dev-Nexus

The Dependency Orchestrator integrates with [dev-nexus](https://github.com/patelmm79/dev-nexus):

1. **Receives notifications** → Validates change events
2. **Runs async triage** → Analyzes impact (BackgroundTask)
3. **Posts lessons learned** → Contributes insights to dev-nexus
4. **Creates GitHub issues** → Logs recommendations in affected repos

---

## Performance Characteristics

### Response Times
- **`receive_change_notification`** (validate): < 100ms
- **`get_dependencies`** (graph query): 50-200ms
- **`get_impact_analysis`** (sync triage): 30-60s (runs Claude API)
- **`add_dependency_relationship`** (config update): < 50ms

### Background Triage
- Starts: Immediately after HTTP 202 response
- Duration: 30-60 seconds per repository
- Failures: Logged, don't block orchestrator
- Retry: Not implemented (simple execution model)

---

## Error Handling

All A2A skills return structured error responses:

```json
{
  "error": "invalid_input",
  "message": "Missing required field: source_repo",
  "details": {...}
}
```

No task_id to poll (stateless architecture).

---

## See Also

- **[CLAUDE.md](../CLAUDE.md)** - Complete architecture & deployment guide
- **[README.md](../README.md)** - General project documentation
- **[docs/GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)** - Webhook configuration
