# Setup Verification Checklist

This checklist helps you verify that your Dependency Orchestrator setup is working correctly.

## Prerequisites Verification

### ✅ 1. Orchestrator Service is Running

```bash
# Get your orchestrator URL
gcloud run services describe architecture-kb-orchestrator \
  --region=us-central1 \
  --format="value(status.url)"

# Test health endpoint
curl https://your-orchestrator-url.run.app/

# Expected response:
# {"service":"Architecture KB Orchestrator","status":"healthy","version":"1.0.0","authentication_required":false}
```

**Status**: ⬜ Pass / ⬜ Fail

---

### ✅ 2. Relationships are Configured

```bash
# View configured relationships
curl https://your-orchestrator-url.run.app/api/relationships | jq

# Verify your source repo is listed
curl https://your-orchestrator-url.run.app/api/relationships/patelmm79/vllm-container-ngc | jq
```

**Expected**: Your repository should show consumers and/or derivatives

**Status**: ⬜ Pass / ⬜ Fail

---

## GitHub Actions Setup Verification

### ✅ 3. Workflow File Exists

Check that `.github/workflows/pattern-monitoring.yml` exists in your source repository:

```bash
cd /path/to/vllm-container-ngc
ls -la .github/workflows/pattern-monitoring.yml
```

**Expected**: File exists with correct content (see [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md))

**Status**: ⬜ Pass / ⬜ Fail

---

### ✅ 4. GitHub Secrets are Set

**You cannot programmatically verify secrets exist**, but you can check via GitHub UI:

1. Go to: `https://github.com/YOUR_ORG/vllm-container-ngc/settings/secrets/actions`
2. Verify these secrets exist:
   - ⬜ `ORCHESTRATOR_URL`
   - ⬜ `ANTHROPIC_API_KEY`

**Important**: The values are hidden, but you should see the secret names listed.

**Status**: ⬜ Pass / ⬜ Fail

---

### ✅ 5. Workflow Runs Successfully

1. Go to: `https://github.com/YOUR_ORG/vllm-container-ngc/actions`
2. Find the most recent "Pattern Monitoring" workflow run
3. Check that:
   - ⬜ Workflow status is "Success" (green checkmark)
   - ⬜ All steps completed without errors

**Status**: ⬜ Pass / ⬜ Fail

---

### ✅ 6. Pattern Analysis Completed

In the workflow run logs, check the "Run Pattern Analysis" step:

1. Click on the latest workflow run
2. Click on the "analyze / analyze-patterns" job
3. Expand the "Run Pattern Analysis" step
4. Look for these messages:

**Expected output**:
```
Analyzing patterns for patelmm79/vllm-container-ngc...
Found X changed files
Extracting patterns with Claude...
Updating knowledge base...
Checking for similar patterns in other repos...
Notifying orchestrator for dependency triage...
✓ Orchestrator notified successfully
  Consumers scheduled: [...]
  Derivatives scheduled: [...]
```

**Red flags** (these indicate problems):
- ❌ `"No orchestrator URL configured, skipping dependency notification"`
  → **Problem**: `ORCHESTRATOR_URL` secret is not set or is empty
- ❌ `"⚠ Error notifying orchestrator: ..."`
  → **Problem**: Connection failed or URL is incorrect
- ❌ `"⚠ Orchestrator notification timed out"`
  → **Problem**: Orchestrator is slow or not responding

**Status**: ⬜ Pass / ⬜ Fail

---

## End-to-End Verification

### ✅ 7. Test with a Real Commit

Make a test change to trigger the full flow:

```bash
cd /path/to/vllm-container-ngc

# Make a test change
echo "# Test: $(date)" >> README.md
git add README.md
git commit -m "Test: verify orchestrator integration"
git push
```

**What to check**:

1. **GitHub Actions runs** (~30-60 seconds)
   - Go to: `https://github.com/YOUR_ORG/vllm-container-ngc/actions`
   - Wait for workflow to complete
   - Status should be ✅ Success

2. **Orchestrator receives notification** (check logs)
   ```bash
   # Check orchestrator logs for incoming webhook
   gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND httpRequest.requestMethod=\"POST\"" \
     --limit 5 \
     --format=json
   ```
   **Expected**: You should see POST requests to `/api/webhook/change-notification`

3. **Issues are created in dependent repos** (2-5 minutes)
   - Check consumer repos (e.g., `resume-customizer`)
   - Look for new issues with label "dependency"
   - Example: `https://github.com/YOUR_ORG/resume-customizer/issues`

**Status**: ⬜ Pass / ⬜ Fail

---

## Troubleshooting Common Failures

### ❌ Orchestrator Health Check Fails

**Problem**: `curl https://your-orchestrator-url.run.app/` returns an error

**Solutions**:
1. Check service is deployed:
   ```bash
   gcloud run services list | grep architecture-kb-orchestrator
   ```
2. Verify service is running:
   ```bash
   gcloud run services describe architecture-kb-orchestrator --region=us-central1
   ```
3. Check recent deployments worked:
   ```bash
   gcloud builds list --limit=5
   ```

---

### ❌ "No orchestrator URL configured" in Workflow Logs

**Problem**: The `ORCHESTRATOR_URL` secret is not set or is empty

**Solutions**:
1. Go to: `https://github.com/YOUR_ORG/vllm-container-ngc/settings/secrets/actions`
2. Click "New repository secret" (or "Update" if it exists)
3. Name: `ORCHESTRATOR_URL`
4. Value: Your full orchestrator URL (e.g., `https://architecture-kb-orchestrator-75l7mntama-uc.a.run.app`)
   - ⚠️ **No trailing slash**
   - ⚠️ **Must include https://**
5. Click "Add secret"
6. Re-run the workflow to test

---

### ❌ Workflow Succeeds but Orchestrator Logs Show Nothing

**Problem**: Workflow completes but orchestrator never receives the request

**Possible causes**:
1. **Wrong URL**: Secret has incorrect or outdated URL
2. **Network issue**: Temporary connectivity problem
3. **Timeout**: Request timed out (pattern analyzer has 10s timeout)

**Solutions**:
1. Verify the secret value is correct (you'll need to update it to check):
   ```bash
   # Get current orchestrator URL
   gcloud run services describe architecture-kb-orchestrator \
     --region=us-central1 \
     --format="value(status.url)"
   ```
2. Update the secret in GitHub with the correct URL
3. Test manually from your local machine:
   ```bash
   curl -X POST https://your-orchestrator-url.run.app/api/webhook/change-notification \
     -H "Content-Type: application/json" \
     -d '{"source_repo":"patelmm79/vllm-container-ngc","commit_sha":"test","commit_message":"test","branch":"main","changed_files":[],"pattern_summary":{"keywords":[],"patterns":[]},"timestamp":"2025-12-04T00:00:00Z"}'
   ```

---

### ❌ No Issues Created in Dependent Repos

**Problem**: Orchestrator receives notification but doesn't create issues

**Solutions**:
1. Check orchestrator logs for triage processing:
   ```bash
   gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator" \
     --limit 50 \
     --format=json | grep -i "triage\|issue\|consumer\|derivative"
   ```

2. Verify GitHub token has permissions:
   - Check that `GITHUB_TOKEN` environment variable is set in orchestrator
   - Token needs `repo` scope for creating issues

3. Test triage endpoints directly:
   ```bash
   # Test consumer triage
   curl -X POST http://localhost:8080/api/test/consumer-triage \
     -H "Content-Type: application/json" \
     -d @test/consumer_test.json
   ```

4. Check relationships config:
   ```bash
   curl https://your-orchestrator-url.run.app/api/relationships/patelmm79/vllm-container-ngc
   ```

---

## Quick Verification Command

Run this single command to check the most critical components:

```bash
#!/bin/bash
echo "=== Orchestrator Health ==="
ORCH_URL=$(gcloud run services describe architecture-kb-orchestrator --region=us-central1 --format="value(status.url)" 2>/dev/null)
echo "URL: $ORCH_URL"
curl -s $ORCH_URL | jq

echo -e "\n=== Relationships Config ==="
curl -s $ORCH_URL/api/relationships/patelmm79/vllm-container-ngc | jq

echo -e "\n=== Recent Orchestrator POST Requests ==="
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND httpRequest.requestMethod=\"POST\"" --limit 3 --format="table(timestamp,httpRequest.requestUrl,httpRequest.status)"

echo -e "\n=== Recent GitHub Actions Runs ==="
echo "Check: https://github.com/patelmm79/vllm-container-ngc/actions"
```

Save this as `verify-setup.sh` and run it to get a quick health check.

---

## Success Criteria

Your setup is working correctly if:

- ✅ Orchestrator health endpoint returns `"status":"healthy"`
- ✅ Workflow runs complete with ✅ Success status
- ✅ Workflow logs show "✓ Orchestrator notified successfully"
- ✅ Orchestrator logs show POST requests to `/api/webhook/change-notification`
- ✅ Dependent repository issues are created (for relevant changes)

---

## Next Steps

Once all checks pass:
1. ✅ Remove test commits (optional)
2. ✅ Repeat setup for other monitored repositories
3. ✅ Configure webhook notifications (Discord/Slack) if desired
4. ✅ Monitor first few real changes to tune trigger sensitivity

---

## Getting Help

If you're still having issues after following this checklist:

1. Capture the following information:
   - Orchestrator health check output
   - GitHub Actions workflow run URL
   - Orchestrator logs (last 50 lines)
   - Relationship configuration for your repo

2. Check the troubleshooting section in:
   - [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md#troubleshooting)
   - [SETUP.md](../SETUP.md#troubleshooting)
   - [README.md](../README.md#troubleshooting)

3. Open an issue with the captured information
