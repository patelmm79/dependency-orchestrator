# Authentication and Access Control

This document explains how to secure the Dependency Orchestrator with API key authentication.

## Overview

By default, the orchestrator runs with **public access** (no authentication). This is suitable for:
- Testing and development
- Internal networks with firewall protection
- Environments where you trust all callers

For production environments, you should enable **API key authentication** to:
- Prevent unauthorized access
- Track which services are calling the orchestrator
- Meet security compliance requirements

## Authentication Methods

### Current: API Key Authentication

The orchestrator uses HTTP header-based API key authentication:

- **Header**: `X-API-Key`
- **Value**: 32-character alphanumeric string
- **Security**: Constant-time comparison (prevents timing attacks)

**Protected Endpoints** (require API key when auth enabled):
- `POST /api/webhook/change-notification` - Incoming change notifications
- `GET /api/relationships` - View all relationships
- `GET /api/relationships/{repo}/{name}` - View specific relationship
- `POST /api/test/consumer-triage` - Test consumer triage
- `POST /api/test/template-triage` - Test template triage

**Public Endpoints** (always accessible):
- `GET /` - Health check (shows if auth is enabled)

### Future: Cloud IAM Authentication

For even stronger security, you can configure Cloud Run to use IAM:
- Requires GCP service account credentials
- Integrates with Google's identity system
- See "Cloud IAM Method" section below

## Enabling API Key Authentication

### Option 1: Via Terraform (Recommended)

Edit `terraform/terraform.tfvars`:

```hcl
# Enable authentication
require_authentication = true

# Option A: Auto-generate API key (recommended)
orchestrator_api_key = ""  # Leave empty

# Option B: Provide your own API key
orchestrator_api_key = "your-secure-32-char-api-key-here"
```

Apply Terraform:

```bash
cd terraform
terraform apply
```

**Save the generated API key:**
```bash
# If auto-generated, Terraform outputs the key once
terraform output generated_api_key

# Save it immediately - you won't see it again!
export ORCHESTRATOR_API_KEY=$(terraform output -raw generated_api_key)
echo $ORCHESTRATOR_API_KEY > ~/.orchestrator_api_key
chmod 600 ~/.orchestrator_api_key
```

### Option 2: Manual Configuration

If not using Terraform, set the environment variables:

```bash
# Generate a secure API key
ORCHESTRATOR_API_KEY=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)

# Create the secret
echo -n "$ORCHESTRATOR_API_KEY" | gcloud secrets create orchestrator-api-key --data-file=-

# Update Cloud Run to use the secret and enable auth
gcloud run services update architecture-kb-orchestrator \
  --region=us-central1 \
  --update-secrets=ORCHESTRATOR_API_KEY=orchestrator-api-key:latest \
  --set-env-vars=REQUIRE_AUTH=true
```

## Using the API with Authentication

### Testing with curl

```bash
# Without auth (when REQUIRE_AUTH=false)
curl https://your-service-url.run.app/api/relationships

# With auth (when REQUIRE_AUTH=true)
curl -H "X-API-Key: your-api-key-here" \
  https://your-service-url.run.app/api/relationships
```

### In GitHub Actions

Add the API key as a repository secret:

1. Go to repository **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `ORCHESTRATOR_API_KEY`
4. Value: Your API key
5. Click **Add secret**

In your workflow:

```yaml
- name: Notify Orchestrator
  run: |
    curl -X POST \
      -H "Content-Type: application/json" \
      -H "X-API-Key: ${{ secrets.ORCHESTRATOR_API_KEY }}" \
      -d @change-notification.json \
      https://your-orchestrator-url.run.app/api/webhook/change-notification
```

### In Python

```python
import requests

API_KEY = "your-api-key-here"
ORCHESTRATOR_URL = "https://your-service-url.run.app"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

response = requests.post(
    f"{ORCHESTRATOR_URL}/api/webhook/change-notification",
    headers=headers,
    json=change_event
)
```

### In JavaScript/TypeScript

```typescript
const API_KEY = process.env.ORCHESTRATOR_API_KEY;
const ORCHESTRATOR_URL = "https://your-service-url.run.app";

const response = await fetch(
  `${ORCHESTRATOR_URL}/api/webhook/change-notification`,
  {
    method: "POST",
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(changeEvent)
  }
);
```

## Rotating API Keys

### Via Terraform

1. Edit `terraform/terraform.tfvars`:
```hcl
orchestrator_api_key = "new-secure-32-char-api-key-here"
```

2. Apply:
```bash
terraform apply
```

3. Update all callers with new key

### Via gcloud

```bash
# Generate new key
NEW_KEY=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)

# Update secret
echo -n "$NEW_KEY" | gcloud secrets versions add orchestrator-api-key --data-file=-

# Cloud Run picks up new version automatically (may take 1-2 minutes)
```

### Best Practices for Rotation

1. **Advance notice**: Warn teams before rotating
2. **Overlap period**: Consider supporting both old and new keys temporarily
3. **Verify**: Test with new key before removing old one
4. **Document**: Track when keys were rotated
5. **Automate**: Schedule regular rotations (quarterly recommended)

## Disabling Authentication

### Via Terraform

```hcl
require_authentication = false
```

```bash
terraform apply
```

### Via gcloud

```bash
gcloud run services update architecture-kb-orchestrator \
  --region=us-central1 \
  --set-env-vars=REQUIRE_AUTH=false
```

## Cloud IAM Authentication Method

For stronger security, use Cloud Run's built-in IAM:

### 1. Disable unauthenticated access

```bash
# Via Terraform
variable "allow_unauthenticated" {
  default = false
}

# Via gcloud
gcloud run services remove-iam-policy-binding architecture-kb-orchestrator \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

### 2. Grant specific service accounts access

```bash
gcloud run services add-iam-policy-binding architecture-kb-orchestrator \
  --region=us-central1 \
  --member="serviceAccount:caller@project.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 3. Call with authentication

```bash
# Get ID token
TOKEN=$(gcloud auth print-identity-token)

# Call service
curl -H "Authorization: Bearer $TOKEN" \
  https://your-service-url.run.app/api/relationships
```

**Pros:**
- Integrates with GCP IAM
- No API keys to manage
- Audit logging included
- Fine-grained permissions

**Cons:**
- Requires GCP service accounts for callers
- More complex setup
- GitHub Actions needs workload identity

## Monitoring and Auditing

### Check Authentication Status

```bash
# Via health endpoint
curl https://your-service-url.run.app/

# Returns:
# {
#   "service": "Architecture KB Orchestrator",
#   "status": "healthy",
#   "version": "1.0.0",
#   "authentication_required": true
# }
```

### View Failed Authentication Attempts

```bash
gcloud logging read \
  'resource.labels.service_name="architecture-kb-orchestrator"
   AND jsonPayload.message=~"Invalid API key"' \
  --limit=50 \
  --format=json
```

### Track API Usage by Caller

Consider adding custom headers to identify callers:

```python
headers = {
    "X-API-Key": API_KEY,
    "X-Caller-ID": "github-actions-repo-name"  # Custom header
}
```

Then filter logs:

```bash
gcloud logging read \
  'resource.labels.service_name="architecture-kb-orchestrator"
   AND httpRequest.requestMethod="POST"' \
  --format=json
```

## Security Best Practices

1. **Always enable auth in production**
   - `require_authentication = true`

2. **Use auto-generated keys**
   - Let Terraform generate secure random keys
   - Don't use predictable values

3. **Store keys securely**
   - Use Secret Manager (not environment variables in code)
   - Never commit keys to git
   - Use GitHub Secrets for Actions

4. **Rotate regularly**
   - Set a rotation schedule (quarterly recommended)
   - Have a rotation procedure documented

5. **Limit key distribution**
   - Only give keys to services that need them
   - Use different keys per environment (dev/staging/prod)

6. **Monitor for suspicious activity**
   - Alert on repeated 401 errors
   - Track unusual usage patterns
   - Review logs regularly

7. **Use HTTPS only**
   - Cloud Run enforces HTTPS by default
   - Never send API keys over HTTP

8. **Consider IP allowlisting**
   - Use Cloud Armor for additional network-level security
   - Restrict to known IP ranges

## Troubleshooting

### "Missing or invalid API key" Error

**Check:**
1. Is `REQUIRE_AUTH=true`?
2. Is `ORCHESTRATOR_API_KEY` set in Cloud Run?
3. Are you sending the `X-API-Key` header?
4. Is the key value correct?

```bash
# View current Cloud Run environment
gcloud run services describe architecture-kb-orchestrator \
  --region=us-central1 \
  --format=yaml

# Check if REQUIRE_AUTH is set
# Check if ORCHESTRATOR_API_KEY secret is mounted
```

### Authentication works locally but not in Cloud Run

- Cloud Run might be caching old environment variables
- Force new revision:
  ```bash
  gcloud run services update architecture-kb-orchestrator \
    --region=us-central1 \
    --no-traffic  # Deploy without traffic

  # Test, then migrate traffic
  gcloud run services update-traffic architecture-kb-orchestrator \
    --region=us-central1 \
    --to-latest
  ```

### Can't retrieve API key after Terraform apply

- Terraform only shows the generated key once
- Retrieve from Secret Manager:
  ```bash
  gcloud secrets versions access latest \
    --secret=orchestrator-api-key \
    --format='get(payload.data)' | base64 -d
  ```

## Migration Guide: Public → Authenticated

1. **Deploy with auth disabled** (current state)
2. **Add API key** via Terraform but keep `require_authentication = false`
3. **Distribute key** to all callers
4. **Update callers** to send `X-API-Key` header
5. **Test** that all callers work with the key
6. **Enable auth**: Set `require_authentication = true`
7. **Monitor** for 401 errors
8. **Fix** any callers that were missed

## Resources

- [Cloud Run Authentication](https://cloud.google.com/run/docs/authenticating/overview)
- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
