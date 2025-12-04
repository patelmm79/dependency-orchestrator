# Cost Tracking with Labels

This document explains the labeling strategy used for GCP cost tracking and resource organization.

## Overview

All GCP resources created by this project are tagged with consistent labels to enable:
- **Cost attribution** by application, environment, and component
- **Resource filtering** in GCP console and CLI
- **Budget alerts** specific to this application
- **Cost analysis** and optimization

## Label Schema

### Standard Labels

All resources include these standard labels:

| Label | Value | Purpose |
|-------|-------|---------|
| `application` | `dependency-orchestrator` | Identifies this application across all resources |
| `environment` | `production` | Environment (production, staging, dev) |
| `component` | `orchestration` | Application component/subsystem |
| `managed-by` | `terraform`, `cloud-build`, or `gcloud-cli` | How the resource is deployed |

### Resource-Specific Labels

Some resources have additional labels:

**Secret Manager Secrets:**
- `secret-type`: `api-key`, `access-token`, or `webhook`

**Cloud Build:**
- Uses `tags` instead of `labels` (GCP limitation)
- Tags: `dependency-orchestrator`, `production`, `orchestration`

## Resources with Labels

### Managed by Terraform

When deployed via Terraform (`terraform apply`), these resources get labels:

1. **Secret Manager Secrets** (`anthropic-api-key`, `github-token`, `webhook-url`)
   - Labels: Standard + `secret-type`

2. **Cloud Run Service** (`architecture-kb-orchestrator`)
   - Labels: Standard (on both service and revisions)

3. **Cloud Build Trigger** (optional, if enabled)
   - Tags: `terraform-managed`, `dependency-orchestrator`

### Managed by Cloud Build

When deployed via `deploy-gcp-cloudbuild.sh`, these get labels:

1. **Cloud Run Service**
   - Labels: Standard with `managed-by=cloud-build`

2. **Cloud Build Jobs**
   - Tags: `dependency-orchestrator`, `production`, `orchestration`

### Managed by Local Script

When deployed via `deploy-gcp.sh`, these get labels:

1. **Cloud Run Service**
   - Labels: Standard with `managed-by=gcloud-cli`

## Viewing Costs by Label

### In GCP Console

1. **Cloud Console → Billing → Reports**
2. **Filters → Labels**
3. Select label: `application = dependency-orchestrator`

This shows all costs for this application across:
- Cloud Run compute and requests
- Secret Manager storage and access
- Cloud Build minutes
- Container Registry storage
- Networking/egress

### Using gcloud CLI

```bash
# List all resources with the application label
gcloud asset search-all-resources \
  --query="labels.application=dependency-orchestrator" \
  --format=table

# Cloud Run services with labels
gcloud run services list \
  --filter="metadata.labels.application=dependency-orchestrator" \
  --format=table

# Secrets with labels
gcloud secrets list \
  --filter="labels.application=dependency-orchestrator" \
  --format=table
```

### Cost Queries

Use BigQuery export of billing data to query costs:

```sql
-- Total cost by application
SELECT
  labels.value AS application,
  SUM(cost) AS total_cost,
  SUM(usage.amount) AS usage_amount,
  usage.unit
FROM `project.dataset.gcp_billing_export_v1_XXXXX`
WHERE labels.key = 'application'
  AND labels.value = 'dependency-orchestrator'
  AND DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY application, usage.unit
ORDER BY total_cost DESC;

-- Cost breakdown by component
SELECT
  (SELECT value FROM UNNEST(labels) WHERE key = 'component') AS component,
  service.description AS service,
  SUM(cost) AS cost,
  ROUND(SUM(cost) / SUM(SUM(cost)) OVER() * 100, 2) AS cost_percentage
FROM `project.dataset.gcp_billing_export_v1_XXXXX`
WHERE ARRAY_LENGTH(labels) > 0
  AND EXISTS(SELECT 1 FROM UNNEST(labels) WHERE key = 'application' AND value = 'dependency-orchestrator')
  AND DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY component, service
ORDER BY cost DESC;
```

## Setting Up Budget Alerts

Create a budget alert filtered by label:

```bash
# Create budget for dependency-orchestrator
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="Dependency Orchestrator Budget" \
  --budget-amount=50 \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100 \
  --all-updates-rule-monitoring-notification-channels=CHANNEL_ID \
  --filter-labels="application=dependency-orchestrator"
```

Or in GCP Console:
1. **Billing → Budgets & alerts → Create budget**
2. **Projects**: Select your project
3. **Filters → Labels**: `application = dependency-orchestrator`
4. Set amount and thresholds

## Customizing Labels

### Via Terraform

Edit `terraform/variables.tf` to change default labels:

```hcl
variable "labels" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default = {
    application = "dependency-orchestrator"
    environment = "staging"  # Change to staging/dev
    managed-by  = "terraform"
    component   = "orchestration"
    team        = "platform"  # Add custom labels
    cost-center = "engineering"
  }
}
```

Or override via `terraform.tfvars`:

```hcl
labels = {
  application = "dependency-orchestrator"
  environment = "production"
  managed-by  = "terraform"
  component   = "orchestration"
  owner       = "john-doe"
}
```

### Via Deployment Scripts

Edit labels in:
- `cloudbuild.yaml` (line 55)
- `deploy-gcp.sh` (line 64)

## Best Practices

1. **Consistency**: Use the same label keys across all resources
2. **Lowercase**: Use lowercase with hyphens (e.g., `cost-center`, not `Cost_Center`)
3. **Limited values**: Keep label values simple and finite for better grouping
4. **Document**: Document your labeling strategy for the team
5. **Automation**: Use Terraform/scripts to apply labels consistently
6. **Review**: Periodically review and clean up unused labels

## Label Limitations

- **Max per resource**: 64 labels
- **Key length**: 1-63 characters
- **Value length**: 0-63 characters
- **Characters**: Lowercase letters, numbers, hyphens, underscores
- **Cloud Build**: Uses `tags` instead of `labels` (different namespace)
- **Not all resources**: Some GCP resources don't support labels

## Troubleshooting

### Labels not appearing in billing

- **Delay**: Labels may take 24-48 hours to appear in billing reports
- **Export**: Ensure billing export to BigQuery is enabled
- **Scope**: Some costs (like network egress) may not have resource-level labels

### Updating existing resources

To add labels to existing resources:

```bash
# Update Cloud Run service labels
gcloud run services update architecture-kb-orchestrator \
  --region=us-central1 \
  --update-labels=application=dependency-orchestrator,environment=production

# Update Secret labels
gcloud secrets update anthropic-api-key \
  --update-labels=application=dependency-orchestrator,secret-type=api-key
```

Or re-run Terraform:
```bash
cd terraform
terraform apply  # Will update labels on all resources
```

## Resources

- [GCP Labels Best Practices](https://cloud.google.com/resource-manager/docs/creating-managing-labels)
- [Cloud Run Labels](https://cloud.google.com/run/docs/configuring/labels)
- [Billing Reports](https://cloud.google.com/billing/docs/how-to/reports)
- [Budget Alerts](https://cloud.google.com/billing/docs/how-to/budgets)
