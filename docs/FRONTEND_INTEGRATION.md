# Frontend Integration Guide - Dependency Orchestrator

## Overview

The Dependency Orchestrator is an AI-powered service that coordinates automated triage agents to assess the impact of changes across related repositories. It provides two integration approaches:

1. **A2A Protocol** (Recommended) - Modern, standardized agent-to-agent communication
2. **Legacy Webhooks** - Direct REST API for backward compatibility

**Service URL:** `https://architecture-kb-orchestrator-665374072631.us-central1.run.app`

---

## Authentication

Most endpoints require API key authentication (except health checks and agent discovery).

### Headers Required

```javascript
{
  "X-API-Key": "your-api-key-here",
  "Content-Type": "application/json"
}
```

### Check if Authentication is Required

```bash
GET /
```

Response includes `authentication_required: true/false`

---

## A2A Protocol Integration (Recommended)

The A2A (Agent-to-Agent) protocol provides a standardized way to interact with the orchestrator.

### 1. Discover Agent Capabilities

```javascript
// Discover what the agent can do
const response = await fetch('https://your-service-url/.well-known/agent.json');
const agentCard = await response.json();

console.log(agentCard.skills); // List of available skills
```

**Response:**
```json
{
  "name": "dependency-orchestrator",
  "display_name": "Dependency Orchestrator",
  "description": "AI-powered dependency orchestration agent...",
  "version": "2.0.0",
  "skills": [
    "receive_change_notification",
    "get_impact_analysis",
    "get_dependencies",
    "trigger_consumer_triage",
    "trigger_template_triage",
    "get_orchestration_status",
    "add_dependency_relationship"
  ],
  "endpoints": {
    "skills": "/a2a/skills",
    "execute": "/a2a/execute",
    "health": "/a2a/health"
  }
}
```

### 2. List Available Skills

```javascript
// List all skills
const response = await fetch('https://your-service-url/a2a/skills');
const data = await response.json();

console.log(data.skills);
```

**Filter by category:**
```javascript
// Categories: event, query, action, management
const response = await fetch('https://your-service-url/a2a/skills?category=query');
```

**Response:**
```json
{
  "skills": [
    {
      "name": "get_impact_analysis",
      "display_name": "Get Impact Analysis",
      "description": "Analyze impact of changes on a specific repository",
      "category": "query",
      "requires_auth": true,
      "is_async": false
    },
    {
      "name": "trigger_consumer_triage",
      "display_name": "Trigger Consumer Triage",
      "description": "Manually trigger consumer impact analysis",
      "category": "action",
      "requires_auth": true,
      "is_async": true
    }
  ]
}
```

### 3. Execute Skills

#### Query: Get Impact Analysis

Analyze how changes in one repo affect another:

```javascript
const response = await fetch('https://your-service-url/a2a/execute', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    skill_name: 'get_impact_analysis',
    input_data: {
      source_repo: 'owner/source-repo',
      target_repo: 'owner/target-repo',
      changed_files: [
        { path: 'src/api/routes.py', status: 'modified' }
      ]
    }
  })
});

const result = await response.json();
```

**Response:**
```json
{
  "success": true,
  "skill_name": "get_impact_analysis",
  "result": {
    "requires_action": true,
    "urgency": "high",
    "impact_summary": "API endpoint changes require consumer updates",
    "affected_files": ["src/client.py", "config/api.yaml"],
    "recommended_changes": "Update API client to handle new endpoints...",
    "confidence": 0.85,
    "reasoning": "Breaking changes detected in authentication flow..."
  }
}
```

#### Query: Get Dependencies

Get all configured dependencies for a repository:

```javascript
const response = await fetch('https://your-service-url/a2a/execute', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    skill_name: 'get_dependencies',
    input_data: {
      repo: 'owner/repo-name'
    }
  })
});
```

**Response:**
```json
{
  "success": true,
  "result": {
    "repo": "owner/source-repo",
    "consumers": [
      {
        "repo": "owner/consumer-repo",
        "relationship_type": "api_consumer",
        "interface_files": ["src/client.py"]
      }
    ],
    "derivatives": [
      {
        "repo": "owner/derivative-repo",
        "relationship_type": "template_fork"
      }
    ]
  }
}
```

#### Action: Trigger Consumer Triage (Async)

Manually trigger impact analysis for a consumer:

```javascript
const response = await fetch('https://your-service-url/a2a/execute', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    skill_name: 'trigger_consumer_triage',
    input_data: {
      source_repo: 'owner/source-repo',
      consumer_repo: 'owner/consumer-repo',
      change_event: {
        commit_sha: 'abc123',
        commit_message: 'Update API endpoints',
        branch: 'main',
        changed_files: [
          { path: 'src/api/routes.py', status: 'modified' }
        ],
        pattern_summary: {
          patterns_detected: ['api_contract']
        },
        timestamp: '2025-01-15T10:30:00Z'
      }
    }
  })
});

const result = await response.json();
console.log('Task ID:', result.result.task_id);
```

**Response:**
```json
{
  "success": true,
  "skill_name": "trigger_consumer_triage",
  "result": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "message": "Consumer triage task queued for processing"
  }
}
```

#### Query: Check Task Status

For async operations, poll for status:

```javascript
const response = await fetch('https://your-service-url/a2a/execute', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    skill_name: 'get_orchestration_status',
    input_data: {
      task_id: '550e8400-e29b-41d4-a716-446655440000'
    }
  })
});
```

**Response:**
```json
{
  "success": true,
  "result": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "finished",
    "skill_name": "trigger_consumer_triage",
    "created_at": "2025-01-15T10:30:00Z",
    "completed_at": "2025-01-15T10:31:45Z",
    "result": {
      "requires_action": true,
      "urgency": "high",
      "impact_summary": "Breaking API changes detected",
      "github_issue_url": "https://github.com/owner/consumer-repo/issues/123"
    }
  }
}
```

**Task Status Values:**
- `queued` - Task is waiting to be processed
- `started` - Task is currently being processed
- `finished` - Task completed successfully
- `failed` - Task failed with error

---

## Legacy Webhook Integration

For direct REST API access without A2A protocol.

### 1. Get Relationships

```javascript
// Get all relationships
const response = await fetch('https://your-service-url/api/relationships', {
  headers: { 'X-API-Key': 'your-api-key' }
});
```

```javascript
// Get specific repo relationships
const response = await fetch('https://your-service-url/api/relationships/owner/repo-name', {
  headers: { 'X-API-Key': 'your-api-key' }
});
```

### 2. Send Change Notification

Notify the orchestrator of repository changes:

```javascript
const response = await fetch('https://your-service-url/api/webhook/change-notification', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    source_repo: 'owner/repo-name',
    commit_sha: 'abc123def456',
    commit_message: 'Update API endpoints',
    branch: 'main',
    changed_files: [
      {
        path: 'src/api/routes.py',
        status: 'modified',
        additions: 45,
        deletions: 12
      }
    ],
    pattern_summary: {
      patterns_detected: ['api_contract', 'authentication'],
      keywords_found: ['endpoint', 'auth', 'token']
    },
    timestamp: '2025-01-15T10:30:00Z'
  })
});
```

**Response:**
```json
{
  "status": "accepted",
  "source_repo": "owner/repo-name",
  "consumers_scheduled": [
    {
      "repo": "owner/consumer-repo",
      "task_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ],
  "derivatives_scheduled": [],
  "total_dependents": 1
}
```

---

## Complete React/TypeScript Example

```typescript
// orchestrator-client.ts
interface ChangeEvent {
  source_repo: string;
  commit_sha: string;
  commit_message: string;
  branch: string;
  changed_files: Array<{
    path: string;
    status: string;
    additions?: number;
    deletions?: number;
  }>;
  pattern_summary: {
    patterns_detected: string[];
    keywords_found?: string[];
  };
  timestamp: string;
}

interface ImpactAnalysisResult {
  requires_action: boolean;
  urgency: 'critical' | 'high' | 'medium' | 'low';
  impact_summary: string;
  affected_files: string[];
  recommended_changes: string;
  confidence: number;
  reasoning: string;
}

class OrchestratorClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return response.json();
  }

  // A2A Protocol Methods

  async getAgentCard() {
    const response = await fetch(`${this.baseUrl}/.well-known/agent.json`);
    return response.json();
  }

  async listSkills(category?: 'event' | 'query' | 'action' | 'management') {
    const url = category ? `/a2a/skills?category=${category}` : '/a2a/skills';
    return this.request(url);
  }

  async executeSkill(skillName: string, inputData: any) {
    return this.request('/a2a/execute', {
      method: 'POST',
      body: JSON.stringify({
        skill_name: skillName,
        input_data: inputData,
      }),
    });
  }

  async getImpactAnalysis(
    sourceRepo: string,
    targetRepo: string,
    changedFiles: Array<{ path: string; status: string }>
  ): Promise<ImpactAnalysisResult> {
    const result = await this.executeSkill('get_impact_analysis', {
      source_repo: sourceRepo,
      target_repo: targetRepo,
      changed_files: changedFiles,
    });
    return result.result;
  }

  async getDependencies(repo: string) {
    const result = await this.executeSkill('get_dependencies', {
      repo: repo,
    });
    return result.result;
  }

  async triggerConsumerTriage(
    sourceRepo: string,
    consumerRepo: string,
    changeEvent: ChangeEvent
  ) {
    const result = await this.executeSkill('trigger_consumer_triage', {
      source_repo: sourceRepo,
      consumer_repo: consumerRepo,
      change_event: changeEvent,
    });
    return result.result;
  }

  async getTaskStatus(taskId: string) {
    const result = await this.executeSkill('get_orchestration_status', {
      task_id: taskId,
    });
    return result.result;
  }

  async pollTaskUntilComplete(
    taskId: string,
    maxWaitMs: number = 60000
  ): Promise<any> {
    const startTime = Date.now();
    const pollInterval = 2000; // 2 seconds

    while (Date.now() - startTime < maxWaitMs) {
      const status = await this.getTaskStatus(taskId);

      if (status.status === 'finished') {
        return status.result;
      }

      if (status.status === 'failed') {
        throw new Error(`Task failed: ${status.error}`);
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    throw new Error('Task polling timeout');
  }

  // Legacy Webhook Methods

  async sendChangeNotification(event: ChangeEvent) {
    return this.request('/api/webhook/change-notification', {
      method: 'POST',
      body: JSON.stringify(event),
    });
  }

  async getRelationships(owner?: string, repoName?: string) {
    const endpoint = owner && repoName
      ? `/api/relationships/${owner}/${repoName}`
      : '/api/relationships';
    return this.request(endpoint);
  }
}

// Usage Example
const client = new OrchestratorClient(
  'https://architecture-kb-orchestrator-665374072631.us-central1.run.app',
  process.env.ORCHESTRATOR_API_KEY!
);

// Example 1: Get impact analysis
async function analyzeImpact() {
  const result = await client.getImpactAnalysis(
    'owner/source-repo',
    'owner/consumer-repo',
    [{ path: 'src/api/routes.py', status: 'modified' }]
  );

  console.log('Impact:', result.impact_summary);
  console.log('Urgency:', result.urgency);
  console.log('Confidence:', result.confidence);
}

// Example 2: Trigger triage and wait for result
async function triggerAndWait() {
  const changeEvent: ChangeEvent = {
    source_repo: 'owner/source-repo',
    commit_sha: 'abc123',
    commit_message: 'Update API',
    branch: 'main',
    changed_files: [
      { path: 'src/api/routes.py', status: 'modified' }
    ],
    pattern_summary: {
      patterns_detected: ['api_contract']
    },
    timestamp: new Date().toISOString(),
  };

  const { task_id } = await client.triggerConsumerTriage(
    'owner/source-repo',
    'owner/consumer-repo',
    changeEvent
  );

  console.log('Task queued:', task_id);

  const result = await client.pollTaskUntilComplete(task_id);
  console.log('Analysis complete:', result);
}

// Example 3: List dependencies
async function showDependencies() {
  const deps = await client.getDependencies('owner/my-repo');
  console.log('Consumers:', deps.consumers);
  console.log('Derivatives:', deps.derivatives);
}
```

---

## React Component Example

```tsx
// ImpactAnalyzer.tsx
import React, { useState } from 'react';
import { OrchestratorClient } from './orchestrator-client';

const client = new OrchestratorClient(
  process.env.REACT_APP_ORCHESTRATOR_URL!,
  process.env.REACT_APP_ORCHESTRATOR_API_KEY!
);

export const ImpactAnalyzer: React.FC = () => {
  const [sourceRepo, setSourceRepo] = useState('');
  const [targetRepo, setTargetRepo] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzeImpact = async () => {
    setLoading(true);
    setError(null);

    try {
      const analysis = await client.getImpactAnalysis(
        sourceRepo,
        targetRepo,
        [{ path: 'src/api/routes.py', status: 'modified' }]
      );
      setResult(analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="impact-analyzer">
      <h2>Dependency Impact Analyzer</h2>

      <div>
        <input
          type="text"
          placeholder="Source repo (owner/repo)"
          value={sourceRepo}
          onChange={(e) => setSourceRepo(e.target.value)}
        />
        <input
          type="text"
          placeholder="Target repo (owner/repo)"
          value={targetRepo}
          onChange={(e) => setTargetRepo(e.target.value)}
        />
        <button onClick={analyzeImpact} disabled={loading}>
          {loading ? 'Analyzing...' : 'Analyze Impact'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <h3>Analysis Result</h3>
          <p><strong>Requires Action:</strong> {result.requires_action ? 'Yes' : 'No'}</p>
          <p><strong>Urgency:</strong> <span className={`urgency-${result.urgency}`}>{result.urgency}</span></p>
          <p><strong>Impact:</strong> {result.impact_summary}</p>
          <p><strong>Confidence:</strong> {(result.confidence * 100).toFixed(0)}%</p>

          <details>
            <summary>Affected Files ({result.affected_files.length})</summary>
            <ul>
              {result.affected_files.map((file: string) => (
                <li key={file}>{file}</li>
              ))}
            </ul>
          </details>

          <details>
            <summary>Recommended Changes</summary>
            <pre>{result.recommended_changes}</pre>
          </details>

          <details>
            <summary>Reasoning</summary>
            <p>{result.reasoning}</p>
          </details>
        </div>
      )}
    </div>
  );
};
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message here"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing or invalid API key)
- `404` - Not Found (skill or resource doesn't exist)
- `500` - Internal Server Error

**Error Handling Example:**
```typescript
try {
  const result = await client.getImpactAnalysis(source, target, files);
} catch (error) {
  if (error.status === 401) {
    console.error('Invalid API key');
  } else if (error.status === 404) {
    console.error('Repository not found');
  } else {
    console.error('Unexpected error:', error);
  }
}
```

---

## Health Checks

Check if the service is running:

```javascript
// Simple health check
const response = await fetch('https://your-service-url/health');
// Returns: {"status": "healthy"}

// Detailed health check
const response = await fetch('https://your-service-url/a2a/health');
// Returns: {"status": "healthy", "agent": "dependency-orchestrator", "version": "2.0.0"}

// Service info
const response = await fetch('https://your-service-url/');
// Returns full service information including available endpoints
```

---

## Rate Limiting & Best Practices

1. **Async Operations**: Use async skills for long-running operations (triage analysis)
2. **Polling**: Poll task status every 2-5 seconds, don't poll continuously
3. **Caching**: Cache agent card and skills list (they rarely change)
4. **Error Retry**: Implement exponential backoff for failed requests
5. **Timeouts**: Set reasonable timeouts (30-60s for queries, 5min for async operations)

---

## Environment Variables

```bash
# .env
REACT_APP_ORCHESTRATOR_URL=https://architecture-kb-orchestrator-665374072631.us-central1.run.app
REACT_APP_ORCHESTRATOR_API_KEY=your-api-key-here
```

---

## Testing

Use the test endpoints to validate integration:

```bash
# Test health check
curl https://your-service-url/health

# Test agent card
curl https://your-service-url/.well-known/agent.json

# Test skills list
curl https://your-service-url/a2a/skills

# Test with authentication
curl -H "X-API-Key: your-key" https://your-service-url/api/relationships
```

---

## Support & Documentation

- **A2A Protocol Spec**: https://a2a-protocol.org
- **Service Status**: Check `/health` endpoint
- **Issues**: Report integration issues to the backend team

---

## Quick Start Checklist

- [ ] Get API key from backend team
- [ ] Test health endpoint to verify connectivity
- [ ] Fetch agent card to understand capabilities
- [ ] List available skills
- [ ] Implement basic skill execution (start with `get_dependencies`)
- [ ] Add error handling and retry logic
- [ ] Implement async task polling for long-running operations
- [ ] Add loading states and user feedback in UI
