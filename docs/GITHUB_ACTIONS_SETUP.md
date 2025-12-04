# GitHub Actions Setup Guide

This guide provides step-by-step instructions for setting up GitHub Actions workflows in your source repositories to notify the Dependency Orchestrator of changes.

## Overview

The orchestrator needs to receive notifications when changes occur in your monitored repositories. There are two ways to set this up:

1. **Option A: With architecture-kb Pattern Analyzer** (Recommended) - Uses the architecture-kb reusable workflow for automatic pattern detection
2. **Option B: Standalone Webhook** - Direct webhook notification without pattern analysis

## Prerequisites

Before setting up GitHub Actions, ensure:

- ✅ Orchestrator service is deployed and you have the service URL
- ✅ You have admin access to the source repositories you want to monitor
- ✅ Repositories are configured in `config/relationships.json`

## Option A: With architecture-kb Pattern Analyzer (Recommended)

**Use this if**: You want automatic pattern detection and detailed change analysis.

### What This Does

The architecture-kb pattern analyzer:
- Analyzes your code changes automatically
- Detects patterns (API changes, infrastructure updates, etc.)
- Extracts relevant context from diffs
- Sends enriched notifications to the orchestrator

### Step-by-Step Setup

#### 1. Add ORCHESTRATOR_URL Secret

Navigate to your source repository (e.g., `vllm-container-ngc`):

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Enter:
   - **Name**: `ORCHESTRATOR_URL`
   - **Value**: Your orchestrator URL (e.g., `https://architecture-kb-orchestrator-abc123-uc.a.run.app`)
4. Click **"Add secret"**

#### 2. Create Workflow File

Create `.github/workflows/pattern-monitoring.yml` in your repository:

```yaml
name: Pattern Monitoring

on:
  push:
    branches:
      - main
      - master
  workflow_dispatch:  # Allow manual triggering

jobs:
  analyze:
    uses: patelmm79/architecture-kb/.github/workflows/analyze-reusable.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      ORCHESTRATOR_URL: ${{ secrets.ORCHESTRATOR_URL }}
```

#### 3. Add ANTHROPIC_API_KEY Secret

The pattern analyzer needs an Anthropic API key:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Enter:
   - **Name**: `ANTHROPIC_API_KEY`
   - **Value**: Your Anthropic API key (e.g., `sk-ant-xxxxx`)
4. Click **"Add secret"**

#### 4. Commit and Push

```bash
git add .github/workflows/pattern-monitoring.yml
git commit -m "Add pattern monitoring workflow"
git push
```

#### 5. Verify Setup

1. Go to **Actions** tab in your repository
2. You should see the "Pattern Monitoring" workflow
3. Make a test change and push to trigger it:
   ```bash
   echo "# Test" >> README.md
   git add README.md
   git commit -m "Test pattern monitoring"
   git push
   ```
4. Check the workflow run to see pattern analysis and orchestrator notification

### Example Workflow Output

When the workflow runs successfully, you'll see:

```
✓ Changed files detected: 3 files
✓ Pattern analysis complete
✓ Orchestrator notified successfully
  - Consumers scheduled: 1
  - Derivatives scheduled: 1
```

---

## Option B: Standalone Webhook (No Pattern Analysis)

**Use this if**: You want a simpler setup without pattern analysis, or want to customize the notification payload.

### What This Does

Sends a direct webhook to the orchestrator with basic change information:
- Commit details (SHA, message, branch)
- List of changed files
- Basic diff information

### Step-by-Step Setup

#### 1. Add ORCHESTRATOR_URL Secret

Navigate to your source repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Enter:
   - **Name**: `ORCHESTRATOR_URL`
   - **Value**: Your orchestrator URL (e.g., `https://architecture-kb-orchestrator-abc123-uc.a.run.app`)
4. Click **"Add secret"**

#### 2. Create Workflow File

Create `.github/workflows/notify-orchestrator.yml` in your repository:

```yaml
name: Notify Dependency Orchestrator

on:
  push:
    branches:
      - main
      - master
  workflow_dispatch:  # Allow manual triggering

jobs:
  notify:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 2  # Fetch last 2 commits to get diff

      - name: Get changed files
        id: changed-files
        run: |
          # Get list of changed files with their status
          git diff --name-status HEAD^ HEAD > changed_files.txt

          # Build JSON array of changed files
          echo "files<<EOF" >> $GITHUB_OUTPUT
          python3 << 'PYTHON_SCRIPT'
          import json
          import subprocess

          # Get changed files
          result = subprocess.run(
              ['git', 'diff', '--name-status', 'HEAD^', 'HEAD'],
              capture_output=True,
              text=True
          )

          files = []
          for line in result.stdout.strip().split('\n'):
              if not line:
                  continue
              parts = line.split('\t')
              if len(parts) >= 2:
                  change_type = parts[0]
                  file_path = parts[1]

                  # Get diff for this file
                  diff_result = subprocess.run(
                      ['git', 'diff', 'HEAD^', 'HEAD', '--', file_path],
                      capture_output=True,
                      text=True
                  )

                  files.append({
                      'path': file_path,
                      'change_type': change_type,
                      'diff': diff_result.stdout[:5000]  # Limit diff size
                  })

          print(json.dumps(files))
          PYTHON_SCRIPT
          echo "EOF" >> $GITHUB_OUTPUT

      - name: Send webhook notification
        env:
          ORCHESTRATOR_URL: ${{ secrets.ORCHESTRATOR_URL }}
        run: |
          # Build webhook payload
          cat << EOF > payload.json
          {
            "source_repo": "${{ github.repository }}",
            "commit_sha": "${{ github.sha }}",
            "commit_message": $(echo '${{ github.event.head_commit.message }}' | jq -Rs .),
            "branch": "${{ github.ref_name }}",
            "changed_files": ${{ steps.changed-files.outputs.files }},
            "pattern_summary": {
              "keywords": [],
              "patterns": []
            },
            "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
          }
          EOF

          # Send to orchestrator
          response=$(curl -s -w "\n%{http_code}" -X POST \
            "${ORCHESTRATOR_URL}/api/webhook/change-notification" \
            -H "Content-Type: application/json" \
            -d @payload.json)

          # Extract status code and body
          http_code=$(echo "$response" | tail -n1)
          body=$(echo "$response" | sed '$d')

          echo "Response status: $http_code"
          echo "Response body: $body"

          # Check if successful
          if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
            echo "✓ Orchestrator notified successfully"
            echo "$body" | jq '.'
          else
            echo "✗ Failed to notify orchestrator"
            exit 1
          fi
```

#### 3. Commit and Push

```bash
git add .github/workflows/notify-orchestrator.yml
git commit -m "Add orchestrator notification workflow"
git push
```

#### 4. Verify Setup

1. Go to **Actions** tab in your repository
2. You should see the "Notify Dependency Orchestrator" workflow
3. Make a test change and push to trigger it:
   ```bash
   echo "# Test" >> README.md
   git add README.md
   git commit -m "Test orchestrator notification"
   git push
   ```
4. Check the workflow run to see the webhook notification

### Example Workflow Output

When the workflow runs successfully, you'll see:

```
✓ Changed files detected: 3 files
✓ Orchestrator notified successfully
{
  "status": "accepted",
  "consumers_scheduled": ["owner/consumer-repo"],
  "derivatives_scheduled": ["owner/derivative-repo"],
  "total_dependents": 2
}
```

---

## Comparison: Option A vs Option B

| Feature | Option A (architecture-kb) | Option B (Standalone) |
|---------|---------------------------|----------------------|
| **Pattern Detection** | ✅ Automatic AI-powered analysis | ❌ Manual keywords only |
| **Context Extraction** | ✅ Detailed change summaries | ⚠️ Basic diff info |
| **Setup Complexity** | Low (reusable workflow) | Medium (custom script) |
| **API Keys Needed** | Anthropic + Orchestrator URL | Orchestrator URL only |
| **Cost** | ~$0.01-0.05 per analysis | Free |
| **Best For** | Production, detailed analysis | Simple setups, testing |

**Recommendation**: Use **Option A** for production environments where accurate pattern detection is important. Use **Option B** for testing or if you want to minimize API costs.

---

## Troubleshooting

### Workflow Not Triggering

**Problem**: Workflow doesn't run on push

**Solutions**:
1. Check that the workflow file is in `.github/workflows/` directory
2. Verify branch name matches (`main` vs `master`)
3. Ensure YAML syntax is correct (use a YAML validator)
4. Check repository Actions settings: Settings → Actions → "Allow all actions"

### Orchestrator Not Receiving Notifications

**Problem**: Workflow runs but orchestrator doesn't respond

**Solutions**:
1. Verify `ORCHESTRATOR_URL` secret is set correctly
2. Test orchestrator health: `curl https://your-orchestrator-url/`
3. Check orchestrator logs:
   ```bash
   gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator" --limit 20
   ```
4. Verify the URL doesn't have trailing slashes
5. Check if orchestrator requires authentication

### Authentication Errors

**Problem**: 401 Unauthorized or 403 Forbidden

**Solutions**:
1. Verify API keys are valid and not expired
2. Check that secrets are added to the repository (not organization level)
3. Ensure secret names match exactly (case-sensitive)

### Workflow Fails with "Pattern Analysis Failed"

**Problem**: Option A workflow fails during pattern analysis

**Solutions**:
1. Check `ANTHROPIC_API_KEY` is valid
2. Verify you have API credits remaining
3. Check architecture-kb service status
4. Try Option B as a fallback

### Issues Not Being Created

**Problem**: Orchestrator receives notification but doesn't create issues

**Solutions**:
1. Check orchestrator logs for errors
2. Verify relationships are configured in `config/relationships.json`
3. Ensure GitHub token in orchestrator has repo access
4. Test triage endpoints directly:
   ```bash
   curl -X POST http://localhost:8080/api/test/consumer-triage \
     -H "Content-Type: application/json" \
     -d @test/consumer_test.json
   ```

---

## Advanced Configuration

### Filtering Which Changes Trigger Notifications

You can add path filters to only notify on specific file changes:

```yaml
on:
  push:
    branches:
      - main
    paths:
      - 'src/**'
      - 'config/**'
      - 'Dockerfile'
      - 'docker-compose.yml'
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

### Running on Pull Requests

To get notifications on PRs (useful for preview):

```yaml
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
```

### Adding Custom Pattern Keywords

For Option B, you can add custom keywords to help triage:

```yaml
- name: Extract patterns
  id: patterns
  run: |
    # Analyze commit message and files for patterns
    keywords=()

    # Check for API changes
    if git diff HEAD^ HEAD | grep -q "def.*api\|@app\.\|@router\."; then
      keywords+=("api")
    fi

    # Check for Docker changes
    if git diff HEAD^ HEAD --name-only | grep -q "Dockerfile\|docker-compose"; then
      keywords+=("docker")
    fi

    # Check for config changes
    if git diff HEAD^ HEAD --name-only | grep -q "\.ya?ml$\|\.env"; then
      keywords+=("configuration")
    fi

    echo "keywords=$(printf '%s\n' "${keywords[@]}" | jq -R . | jq -s .)" >> $GITHUB_OUTPUT

# Then use in payload:
"pattern_summary": {
  "keywords": ${{ steps.patterns.outputs.keywords }},
  "patterns": []
}
```

### Conditional Notifications

Only notify orchestrator for certain types of changes:

```yaml
- name: Check if notification needed
  id: should-notify
  run: |
    # Only notify if changes affect API or deployment
    if git diff HEAD^ HEAD --name-only | grep -qE "(api|app|docker|config)"; then
      echo "notify=true" >> $GITHUB_OUTPUT
    else
      echo "notify=false" >> $GITHUB_OUTPUT
    fi

- name: Send webhook notification
  if: steps.should-notify.outputs.notify == 'true'
  # ... rest of webhook step
```

---

## Testing Your Setup

### Manual Workflow Trigger

Test without making code changes:

1. Go to **Actions** tab
2. Select your workflow
3. Click **"Run workflow"** dropdown
4. Select branch and click **"Run workflow"**

### Test Notification Payload

Test the payload locally before adding to GitHub Actions:

```bash
# Create test payload
cat << EOF > test-payload.json
{
  "source_repo": "owner/repo",
  "commit_sha": "abc123",
  "commit_message": "Test notification",
  "branch": "main",
  "changed_files": [
    {
      "path": "src/app.py",
      "change_type": "M",
      "diff": "@@ -10,7 +10,7 @@\n-old line\n+new line"
    }
  ],
  "pattern_summary": {
    "keywords": ["api", "test"],
    "patterns": ["API change"]
  },
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Send to orchestrator
curl -X POST https://your-orchestrator-url.run.app/api/webhook/change-notification \
  -H "Content-Type: application/json" \
  -d @test-payload.json | jq
```

### Validate Workflow YAML

Use GitHub's workflow syntax checker:

```bash
# Install act (GitHub Actions local runner)
# https://github.com/nektos/act

# Test workflow locally
act push --secret ORCHESTRATOR_URL=https://your-url.run.app
```

---

## Next Steps

After setting up GitHub Actions:

1. **Monitor the first few runs** - Check that notifications are sent successfully
2. **Review created issues** - Ensure triage agents are working as expected
3. **Tune filters** - Add path filters to reduce noise
4. **Expand to other repos** - Repeat setup for all monitored repositories
5. **Set up monitoring** - Watch orchestrator logs for patterns and errors

---

## Related Documentation

- [SETUP.md](../SETUP.md) - Main orchestrator setup guide
- [README.md](../README.md) - Overview and quick start
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture details
- [architecture-kb](https://github.com/patelmm79/architecture-kb) - Pattern analyzer repository

---

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review orchestrator logs: `gcloud logging read ...`
3. Test the orchestrator health endpoint
4. Check GitHub Actions workflow logs
5. Open an issue in the repository

---

**You're all set!** Your repository will now automatically notify the orchestrator of changes, and dependent repositories will receive impact assessments.
