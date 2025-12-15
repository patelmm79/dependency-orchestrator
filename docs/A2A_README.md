# A2A Protocol Implementation

## Overview

Dependency Orchestrator v2.0 is a fully A2A-compliant agent that exposes 7 standardized skills for dependency orchestration and impact analysis across repository relationships.

## What is A2A?

The Agent-to-Agent (A2A) protocol is an open standard developed by Google and donated to the Linux Foundation. It enables seamless communication and collaboration between AI agents built on different frameworks and platforms.

**Key Benefits:**
- **Interoperability**: Connect agents across different platforms (LangGraph, CrewAI, etc.)
- **Task Delegation**: Agents can delegate subtasks and coordinate complex workflows
- **Discovery**: AgentCard publishing enables automatic capability discovery
- **Security**: Agents collaborate without exposing internal logic

## AgentCard

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
    "description": "AI-powered dependency orchestration agent",
    "version": "2.0.0",
    "vendor": "patelmm79",
    "capabilities": [
      "dependency_tracking",
      "impact_analysis",
      "consumer_triage",
      "template_sync",
      "async_orchestration"
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

## Skills Reference

### Events (Fire-and-Forget)

#### `receive_change_notification`
Primary entry point for change notifications from source repositories.

**Input:**
```json
{
  "source_repo": "owner/repo",
  "commit_sha": "abc123",
  "commit_message": "feat: add new endpoint",
  "branch": "main",
  "changed_files": [...],
  "pattern_summary": {...},
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Output:**
```json
{
  "status": "accepted",
  "source_repo": "owner/repo",
  "consumers_scheduled": [
    {"repo": "owner/consumer1", "task_id": "task-123"}
  ],
  "derivatives_scheduled": [
    {"repo": "owner/derivative1", "task_id": "task-456"}
  ],
  "total_dependents": 2
}
```

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

#### `get_orchestration_status`
Poll status of async orchestration tasks.

**Input:**
```json
{
  "task_id": "task-123"
}
```

**Output:**
```json
{
  "task_id": "task-123",
  "status": "finished",
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:02Z",
  "ended_at": "2025-01-15T10:30:45Z",
  "result": {
    "requires_action": true,
    "urgency": "high",
    ...
  }
}
```

### Actions (Mutating Operations)

#### `trigger_consumer_triage`
Manually trigger async consumer triage analysis.

**Requires Authentication**: Yes

**Input:**
```json
{
  "source_repo": "owner/source",
  "consumer_repo": "owner/consumer",
  "change_event": {...}
}
```

**Output:**
```json
{
  "status": "enqueued",
  "task_id": "task-789",
  "message": "Consumer triage analysis scheduled"
}
```

#### `trigger_template_triage`
Manually trigger async template sync analysis.

**Requires Authentication**: Yes

**Input:**
```json
{
  "template_repo": "owner/template",
  "derivative_repo": "owner/derivative",
  "change_event": {...}
}
```

**Output:**
```json
{
  "status": "enqueued",
  "task_id": "task-012",
  "message": "Template sync analysis scheduled"
}
```

#### `add_dependency_relationship`
Add or update dependency relationships in configuration.

**Requires Authentication**: Yes

**Input:**
```json
{
  "source_repo": "owner/source",
  "target_repo": "owner/target",
  "relationship_type": "api_consumer",
  "relationship_config": {
    "interface_files": ["src/client.py"],
    "change_triggers": ["api_contract", "authentication"]
  }
}
```

**Output:**
```json
{
  "status": "success",
  "message": "Added new consumer relationship",
  "relationship": {...}
}
```

## Using the A2A Client

The orchestrator includes an A2A client for calling other A2A agents:

```python
from orchestrator.a2a.client import A2AClient, DevNexusA2AClient

# Generic A2A client
client = A2AClient(
    base_url="https://other-agent-url",
    api_key="optional-api-key"
)

# Discover agent capabilities
agent_card = client.discover_agent()

# List available skills
skills = client.list_skills(category="query")

# Execute a skill
result = client.execute_skill(
    skill_name="query_data",
    input_data={"query": "..."}
)

# Dev-nexus specific client
dev_nexus = DevNexusA2AClient(
    base_url="https://dev-nexus-url",
    api_key="api-key"
)

# Query architecture knowledge
arch_info = dev_nexus.query_architecture(
    repo="owner/repo",
    query="deployment platform"
)

# Post lesson learned
dev_nexus.post_lesson_learned(
    repo="owner/repo",
    lesson="Breaking API changes require immediate action",
    confidence=0.95,
    category="consumer_triage"
)
```

## Task Queue Architecture

### Redis Queue (RQ)

The orchestrator uses Redis Queue for async task processing:

**Task Lifecycle:**
1. Skill execution creates task via `task_queue.enqueue_task()`
2. Task stored in Redis with unique task_id
3. RQ worker picks up task from queue
4. Worker executes triage agent (calls Claude API, GitHub API)
5. Result stored in Redis with 24-hour TTL
6. Client polls status via `get_orchestration_status` skill

**Configuration:**
- **Queue**: Default queue, 10-minute task timeout
- **Result TTL**: 24 hours
- **Workers**: 2 worker processes (configurable in supervisord.conf)
- **Concurrency**: Workers process tasks in parallel

### Monitoring Tasks

```bash
# View queue status
rq info --url redis://your-redis-url/0

# List all tasks
rq worker-pool --url redis://your-redis-url/0

# View failed tasks
rq list failed --url redis://your-redis-url/0

# Retry failed tasks
rq retry failed --url redis://your-redis-url/0
```

## Authentication

**Query Skills**: No authentication required (read-only)

**Action Skills**: Require API key authentication

**Header:**
```
X-API-Key: your-orchestrator-api-key
```

**Setting API Key:**
```bash
export ORCHESTRATOR_API_KEY="your-secret-key"
export REQUIRE_AUTH="true"
```

## Integration with Dev-Nexus

The orchestrator integrates with dev-nexus via A2A protocol:

**Before Triage:**
- Query dev-nexus for architecture context
- Enrich triage prompts with deployment patterns
- Improve accuracy of impact assessment

**After Triage:**
- Post lessons learned to dev-nexus
- Share impact patterns across repos
- Build cross-repo knowledge base

**Configuration:**
```bash
export DEV_NEXUS_URL="https://dev-nexus-service-url"
```

The orchestrator will automatically discover dev-nexus capabilities via AgentCard and use A2A protocol for communication.

## Performance Considerations

**Synchronous vs Async:**
- **Synchronous** (`get_impact_analysis`): Use for immediate results, blocks until complete (~30-60s)
- **Async** (`trigger_*_triage`): Use for batch operations, returns immediately with task_id

**Task Queue Capacity:**
- Default: 2 workers processing tasks in parallel
- Increase workers: Edit `numprocs` in supervisord.conf
- Redis capacity: 1GB supports ~10,000 tasks in queue

**Cost Optimization:**
- Async tasks reduce API request concurrency
- Workers can be scaled based on workload
- Redis caching reduces redundant API calls

## Error Handling

**Skill Execution Errors:**
```json
{
  "success": false,
  "error": "Skill not found: invalid_skill",
  "task_id": null
}
```

**Task Failures:**
- Failed tasks stored in Redis with error details
- Accessible via `get_orchestration_status`
- Can be retried manually via `rq retry` command

**Worker Failures:**
- Supervisor automatically restarts crashed workers
- Tasks remain in queue and are retried
- Check logs: `gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator"`

## Best Practices

1. **Use Async for Batch Operations**: Trigger multiple triage analyses, poll results later
2. **Poll Task Status**: Don't rely on immediate results for async operations
3. **Set Proper Timeouts**: Long-running analyses can take 2-5 minutes
4. **Monitor Queue Depth**: Alert if queue grows beyond expected bounds
5. **Use AgentCard Discovery**: Always call `/.well-known/agent.json` first
6. **Cache Dependency Graph**: `get_dependencies` results change infrequently

## Troubleshooting

**Issue**: A2A endpoints return 404
- **Solution**: Ensure using `app_unified.py` not legacy `app.py`

**Issue**: Async tasks stuck in "queued" status
- **Solution**: Check RQ workers are running: `ps aux | grep rq`

**Issue**: Redis connection errors
- **Solution**: Verify `REDIS_URL` environment variable and VPC connector

**Issue**: Tasks timing out
- **Solution**: Increase timeout in `task_queue.py` (default: 10 minutes)

**Issue**: High Redis memory usage
- **Solution**: Reduce result TTL or increase Redis instance size

## Further Reading

- [A2A Protocol Specification](https://a2a-protocol.org/latest/)
- [Migration Guide](./A2A_MIGRATION_GUIDE.md)
- [Deployment Guide](../CLAUDE.md)
- [Conversion Plan](https://github.com/patelmm79/dev-nexus/blob/main/docs/DEPENDENCY_ORCHESTRATOR_A2A_CONVERSION_PLAN.md)
