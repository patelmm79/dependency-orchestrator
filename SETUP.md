# Orchestrator Setup Guide

This guide walks you through deploying and configuring the dependency orchestrator service.

## Prerequisites

- GCP account with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally
- GitHub Personal Access Token with `repo` scope
- Anthropic API key

## Step-by-Step Setup

### 1. Configure Your Relationships

Edit `config/relationships.json` to define your repository dependencies:

```json
{
  "relationships": {
    "patelmm79/vllm-container-ngc": {
      "type": "service_provider",
      "consumers": [
        {
          "repo": "patelmm79/resume-customizer",
          "relationship_type": "api_consumer",
          "interface_files": [
            "src/llm_client.py",
            "config/llm_config.yaml"
          ],
          "change_triggers": [
            "api_contract",
            "authentication",
            "deployment"
          ]
        }
      ],
      "derivatives": [
        {
          "repo": "patelmm79/vllm-container-coder",
          "relationship_type": "template_fork",
          "shared_concerns": [
            "infrastructure",
            "docker",
            "deployment"
          ],
          "divergent_concerns": [
            "application_logic",
            "model_specific"
          ]
        }
      ]
    }
  }
}
```

**Key Configuration Options**:

- **`change_triggers`**: What types of changes trigger notifications
  - `api_contract`: API endpoints, routes, schemas
  - `authentication`: Auth mechanisms, tokens
  - `deployment`: Docker, ports, environment
  - `configuration`: Config files, env vars
  - `endpoints`: URL paths, routes

- **`shared_concerns`**: What should sync in template relationships
  - `infrastructure`: General infra improvements
  - `docker`: Docker/compose changes
  - `gpu_configuration`: GPU settings
  - `health_checks`: Health/readiness probes
  - `logging`: Logging configuration
  - `monitoring`: Metrics and monitoring

- **`divergent_concerns`**: What should NOT sync
  - `application_logic`: Business logic
  - `model_specific`: Model configurations
  - `api_endpoints`: API routes
  - `business_logic`: Domain-specific code

### 2. Set Environment Variables

Create a `.env` file (don't commit this!):

```bash
# Required
export GCP_PROJECT_ID="your-gcp-project-id"
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"

# Optional
export GCP_REGION="us-central1"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"
```

Load them:
```bash
source .env
```

### 3. Deploy to GCP Cloud Run

Run the deployment script:

```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

The script will:
1. Authenticate with GCP
2. Build Docker image
3. Push to Google Container Registry
4. Deploy to Cloud Run
5. Output your service URL

**Example output**:
```
✅ Deployment complete!
🌐 Service URL: https://architecture-kb-orchestrator-abc123-uc.a.run.app

Next steps:
1. Test the service: curl https://architecture-kb-orchestrator-abc123-uc.a.run.app
2. Add ORCHESTRATOR_URL secret to your monitored repos
```

### 4. Test the Deployment

**Health check**:
```bash
curl https://your-service-url.run.app/
```

Expected response:
```json
{
  "service": "Architecture KB Orchestrator",
  "status": "healthy",
  "version": "1.0.0"
}
```

**View relationships**:
```bash
curl https://your-service-url.run.app/api/relationships | jq
```

### 5. Configure Monitored Repositories

For each repository in your relationships config:

#### Add ORCHESTRATOR_URL Secret

1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `ORCHESTRATOR_URL`
4. Value: Your Cloud Run service URL (e.g., `https://architecture-kb-orchestrator-abc123-uc.a.run.app`)
5. Click "Add secret"

#### Update Workflow (if needed)

If using the reusable workflow, it should already include the ORCHESTRATOR_URL. Verify your `.github/workflows/pattern-monitoring.yml` has:

```yaml
secrets:
  ORCHESTRATOR_URL: ${{ secrets.ORCHESTRATOR_URL }}
```

### 6. Test End-to-End

Make a test commit to a monitored repository:

```bash
cd vllm-container-ngc
echo "# Test change" >> README.md
git add README.md
git commit -m "Test orchestrator integration"
git push
```

**Check the flow**:

1. **GitHub Actions**: View the workflow run in the Actions tab
   - Should see pattern analysis complete
   - Look for "✓ Orchestrator notified successfully"

2. **Orchestrator Logs**: Check Cloud Run logs
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=architecture-kb-orchestrator" --limit 20
   ```

3. **Dependent Repos**: Check for new issues
   - Go to dependent repository (e.g., resume-customizer)
   - Check Issues tab for new dependency notifications

## Local Development

To run the orchestrator locally for testing:

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export GITHUB_TOKEN="ghp_xxxxx"
export WEBHOOK_URL="https://discord.com/api/webhooks/xxxxx"  # optional
```

### 3. Run the Service

```bash
# Option 1: Direct Python
python orchestrator/app.py

# Option 2: With uvicorn (better for dev)
uvicorn orchestrator.app:app --reload --port 8080
```

### 4. Test Locally

**Health check**:
```bash
curl http://localhost:8080/
```

**Test consumer triage**:
```bash
curl -X POST http://localhost:8080/api/test/consumer-triage \
  -H "Content-Type: application/json" \
  -d '{
    "source_repo": "patelmm79/vllm-container-ngc",
    "consumer_repo": "patelmm79/resume-customizer",
    "test_changes": {
      "commit_message": "Change health check endpoint",
      "changed_files": [{
        "path": "app.py",
        "change_type": "M",
        "diff": "@@ -10,7 +10,7 @@\n-@app.get(\"/health\")\n+@app.get(\"/v1/health\")"
      }],
      "pattern_summary": {
        "keywords": ["api", "endpoint", "health"],
        "patterns": ["API endpoint modification"]
      }
    }
  }'
```

**Test template triage**:
```bash
curl -X POST http://localhost:8080/api/test/template-triage \
  -H "Content-Type: application/json" \
  -d '{
    "template_repo": "patelmm79/vllm-container-ngc",
    "derivative_repo": "patelmm79/vllm-container-coder",
    "test_changes": {
      "commit_message": "Optimize GPU memory allocation",
      "changed_files": [{
        "path": "docker-compose.yml",
        "change_type": "M",
        "diff": "@@ -15,7 +15,10 @@\n     shm_size: 1gb\n+    deploy:\n+      resources:\n+        reservations:\n+          devices:\n+            - driver: nvidia\n+              count: 1\n+              capabilities: [gpu]"
      }],
      "pattern_summary": {
        "keywords": ["gpu", "docker", "memory"],
        "patterns": ["GPU resource optimization"]
      }
    }
  }' | jq
```

## Troubleshooting

### Orchestrator Not Receiving Notifications

**Symptoms**: Pattern analyzer completes but orchestrator shows no activity

**Solutions**:
1. Verify `ORCHESTRATOR_URL` secret is set in monitored repo
2. Check Cloud Run service is running: `gcloud run services list`
3. Verify URL is correct: `curl <orchestrator-url>/`
4. Check pattern analyzer logs for connection errors

### Triage Agents Not Creating Issues

**Symptoms**: Orchestrator receives notification but no issues created

**Solutions**:
1. Check GitHub token has correct permissions:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
   ```
2. Verify relationships are configured correctly
3. Check orchestrator logs for errors:
   ```bash
   gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator" --limit 50
   ```
4. Test the triage endpoint directly (see local testing above)

### False Positives

**Symptoms**: Issues created for irrelevant changes

**Solutions**:
1. Tune `change_triggers` in relationships config
2. Adjust `shared_concerns` and `divergent_concerns` for template relationships
3. Modify trigger detection logic in `consumer_triage.py` or `template_triage.py`

### High Costs

**Symptoms**: Unexpected GCP or Anthropic bills

**Solutions**:
1. Check Cloud Run request volume:
   ```bash
   gcloud monitoring time-series list --filter='metric.type="run.googleapis.com/request_count"'
   ```
2. Review Anthropic API usage at console.anthropic.com
3. Consider:
   - Reducing max-instances in Cloud Run
   - Adding caching for repeated analyses
   - Batching notifications

## Monitoring

### Cloud Run Metrics

View in GCP Console > Cloud Run > architecture-kb-orchestrator:
- Request count
- Request latency
- Error rate
- Instance count
- Memory usage

### Logs

**View recent logs**:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=architecture-kb-orchestrator" \
  --limit 50 \
  --format json
```

**Filter by severity**:
```bash
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND severity>=ERROR" \
  --limit 20
```

**Stream logs in real-time**:
```bash
gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator"
```

## Updating the Orchestrator

After making changes to the code:

```bash
# Pull latest changes
git pull

# Redeploy
./deploy-gcp.sh
```

The script will build a new image and deploy with zero downtime.

## Security Best Practices

1. **Never commit secrets**: Keep `.env` and credentials out of git
2. **Rotate tokens regularly**: Update GitHub token and Anthropic key periodically
3. **Limit token scope**: GitHub token should only have access to required repos
4. **Use GCP IAM**: Restrict who can deploy/modify the service
5. **Enable Cloud Run authentication** (optional): For additional security, configure IAM-based authentication

## Cost Optimization

**Current setup costs** (estimated):
- Cloud Run: ~$1-3/month (mostly free tier)
- Anthropic API: ~$1-5/month (depends on commit frequency)
- Container Registry: ~$0.50/month

**To minimize costs**:
1. Set Cloud Run max-instances to 3-5
2. Use `--min-instances 0` (scale to zero when idle)
3. Enable request/response caching where possible
4. Batch low-priority notifications

## Next Steps

1. **Monitor for a week**: Watch for false positives/negatives
2. **Tune relationships**: Adjust triggers and concerns based on results
3. **Add more repos**: Gradually expand monitoring
4. **Review issues**: Learn from triage agent recommendations
5. **Iterate**: Improve prompts and logic based on experience

## Getting Help

- Check [ORCHESTRATOR.md](ORCHESTRATOR.md) for detailed documentation
- Review [CLAUDE.md](CLAUDE.md) for architecture details
- Open an issue in the architecture-kb repository
- Check orchestrator logs for error messages

---

**You're all set!** The orchestrator will now proactively notify you when changes in one repository affect others.
