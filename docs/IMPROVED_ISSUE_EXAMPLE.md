# Example: Improved Issue Output

## Before (Current Format)

### Title
⚠️ Dependency Update Required: patelmm79/vllm-container-ngc

### Body
```markdown
## Dependency Change Notification

**Source Repository**: patelmm79/vllm-container-ngc
**Commit**: 1865d05
**Branch**: main
**Urgency**: CRITICAL
**Confidence**: 95%

### Impact Summary
The provider added mandatory API key authentication and changed the service port from 8080 to 8000, which will break existing API calls.

### Commit Message
```
Add API key authentication with FastAPI gateway and Secret Manager
```

### Recommended Changes
Update API endpoint URLs to use port 8000 instead of 8080. 2. Add X-API-Key header to all API requests with a valid API key. 3. Update environment variables or configuration to include API key management. 4. If using docker-compose, update port mappings and add API key configuration. 5. Obtain valid API keys from the provider's Secret Manager setup.

### Affected Files in This Repository
- `src/llm_client.py`
- `config/llm_config.yaml`
- `docker-compose.yml`

### Reasoning
The provider introduced a FastAPI gateway on port 8000 with mandatory X-API-Key authentication, while the original vLLM service runs on port 8080. The entrypoint shows both services running, but the gateway acts as a proxy requiring authentication. This is a breaking change because: (1) The consumer likely needs to connect to port 8000 for authenticated access, (2) All requests must include X-API-Key header or they'll be rejected, (3) The consumer needs valid API keys from Google Secret Manager. Without these changes, the consumer's API calls will fail with authentication errors.
```

### Problems with Current Format
1. ❌ Files listed don't exist (`src/llm_client.py` vs actual `utils/llm_client.py`)
2. ❌ Buried the lead - FastAPI gateway is the real story, not port change
3. ❌ Recommendations are numbered but formatted as one long string
4. ❌ No verification step to check if consumer actually uses the service
5. ❌ Reasoning section is verbose and comes last
6. ❌ Claude had to read through everything before understanding impact

---

## After (New Format)

### Title
⚠️ Dependency Update Required: patelmm79/vllm-container-ngc

### Body
```markdown
## 🔔 Dependency Update: patelmm79/vllm-container-ngc

### ⚠️ Key Change
Provider added FastAPI authentication gateway with mandatory API keys - IF you use this service via CUSTOM_LLM_BASE_URL, you must update your configuration to authenticate.

**Urgency**: HIGH | **Confidence**: 85%

### 📋 What You Need To Do

1. **First, verify if you're affected**: Check your `.env` file for:
   - Is `CUSTOM_LLM_BASE_URL` set to point to `vllm-container-ngc`?
   - If not configured or points elsewhere, you can close this issue.

2. **If you ARE using this service**, update your `.env`:
   ```bash
   # OLD (will break)
   CUSTOM_LLM_BASE_URL=http://your-vllm-host:8080/v1
   CUSTOM_LLM_API_KEY=dummy

   # NEW (required)
   CUSTOM_LLM_BASE_URL=http://your-vllm-host:8000/v1
   CUSTOM_LLM_API_KEY=<obtain_real_key_from_provider>
   ```

3. **Get valid API key**: Contact the provider to get your API key from their Secret Manager setup.

4. **Test the connection**: After updating, verify the CustomLLMClient can connect and authenticate properly.

### 📂 Files That May Need Updates
- `utils/llm_client.py` - Already uses OpenAI SDK which handles API keys correctly
- `.env` - Update CUSTOM_LLM_BASE_URL port (8080→8000) and add real API key

---

<details>
<summary>📖 Technical Details & Analysis</summary>

### Source Change Details
- **Repository**: patelmm79/vllm-container-ngc
- **Commit**: [1865d05](https://github.com/patelmm79/vllm-container-ngc/commit/1865d05)
- **Branch**: main

### Commit Message
```
Add API key authentication with FastAPI gateway and Secret Manager
```

### Analysis Reasoning
Cannot definitively determine if resume-customizer uses vllm-container-ngc from code context alone. The CustomLLMClient in utils/llm_client.py is a generic OpenAI-compatible client that could connect to any service. The .env.example mentions vLLM as one option alongside Ollama, LM Studio, etc.

However, IF you have configured CUSTOM_LLM_BASE_URL to point to vllm-container-ngc, then this is a breaking change. The provider introduced a FastAPI gateway on port 8000 with mandatory X-API-Key authentication, while the original vLLM service runs on port 8080. Without updating, API calls will fail with authentication errors.

The good news: OpenAI SDK (used by CustomLLMClient) already handles API keys correctly via the `api_key` parameter, so no code changes needed - just configuration updates.

</details>

---
_🤖 Automatically created by [Dependency Orchestrator](https://github.com/patelmm79/vllm-container-ngc/commit/1865d05)_
```

### Improvements in New Format
1. ✅ **Leads with conditional context**: "IF you use this service..."
2. ✅ **Key change highlighted first**: FastAPI authentication is the headline
3. ✅ **Verification step #1**: How to check if you're affected
4. ✅ **Precise instructions**: Exact env var changes with before/after examples
5. ✅ **Correct file paths**: Only lists files that exist
6. ✅ **Technical details collapsed**: Reasoning available but not blocking action
7. ✅ **Urgency adjusted**: HIGH not CRITICAL since usage uncertain
8. ✅ **Clear to Claude**: First step is to verify - Claude will understand this immediately

### Expected Claude Response
With this new format, when Claude in resume-customizer sees the issue, it should:

1. Read "IF you use this service" → immediately understand it needs to check first
2. See verification step → check `.env` for CUSTOM_LLM_BASE_URL
3. See exact before/after → know precisely what needs changing
4. See correct files → trust the analysis more
5. Make informed decision based on actual configuration

Instead of getting confused by non-existent files and verbose reasoning.
