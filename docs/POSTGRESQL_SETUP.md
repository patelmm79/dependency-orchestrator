## PostgreSQL Setup Guide

### Overview

Dependency Orchestrator uses **PostgreSQL as the primary backend** for task queue management, following the same approach as dev-nexus. PostgreSQL provides:

- **Lower cost**: ~$5-10/month (vs ~$45/month for Redis)
- **Free tier eligible**: e2-micro VM
- **Better persistence**: Relational database with full ACID compliance
- **Rich querying**: SQL-based task management and analytics
- **Audit trails**: Built-in task history tracking

### Architecture

```
Cloud Run (orchestrator)
├── Web Process → VPC Connector → PostgreSQL VM (10.8.0.2:5432)
└── Worker Processes → VPC Connector → PostgreSQL VM (task queue)
```

**Key Components:**
- **PostgreSQL VM**: e2-micro instance (free tier eligible)
- **Database**: `orchestrator` with task queue tables
- **VPC Connector**: Secure Cloud Run ↔ PostgreSQL communication
- **Internal IP**: 10.8.0.2 (no public internet access)

### Deployment Options

#### Option 1: Terraform (Recommended)

**Fully automated PostgreSQL setup via Terraform**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
# Set: use_postgresql = true

terraform init
terraform plan
terraform apply
```

**What Terraform creates:**
- PostgreSQL VM (e2-micro, 30GB disk)
- VPC Connector for Cloud Run
- Secret Manager for PostgreSQL password
- Automatic database initialization
- Cloud Run configuration with PostgreSQL env vars

**After Terraform completes:**
```bash
# Initialize database schema
gcloud compute scp orchestrator/a2a/postgres_schema.sql orchestrator-postgres-vm:/tmp/ --zone=us-central1-a

gcloud compute ssh orchestrator-postgres-vm --zone=us-central1-a \
  --command="PGPASSWORD='your-password' psql -h localhost -U orchestrator -d orchestrator -f /tmp/postgres_schema.sql"

# Deploy application
./deploy-gcp-cloudbuild.sh
```

#### Option 2: Manual Setup Script

**Quick setup for dev/testing**

```bash
# Set password (or script will generate one)
export POSTGRES_PASSWORD="your-secure-password"

# Run setup script
./setup-postgresql.sh

# Outputs connection details:
# POSTGRES_HOST=10.8.0.2
# POSTGRES_PORT=5432
# POSTGRES_DB=orchestrator
# POSTGRES_USER=orchestrator
# POSTGRES_PASSWORD=<generated-or-provided>
```

### Database Schema

The PostgreSQL schema includes:

**Core Tables:**
- `tasks`: All triage tasks with status tracking
- `task_history`: Audit trail of task executions
- `triage_results_cache`: Performance cache for frequent queries
- `repositories`: Repository metadata (optional)
- `dependency_relationships`: Relationship configuration (optional)

**Key Features:**
- **Task Queue Functions**: `get_next_task()`, `update_task_status()`
- **Worker Polling**: `SELECT FOR UPDATE SKIP LOCKED` for concurrency
- **Auto Cleanup**: Function to remove old tasks (7 day retention)
- **Performance Indexes**: Optimized for queue operations

**Schema Location:** `orchestrator/a2a/postgres_schema.sql`

### Connection Configuration

**Environment Variables (set automatically by Terraform):**
```bash
USE_POSTGRESQL=true          # Enable PostgreSQL backend
POSTGRES_HOST=10.8.0.2       # Internal IP
POSTGRES_PORT=5432           # Default PostgreSQL port
POSTGRES_DB=orchestrator     # Database name
POSTGRES_USER=orchestrator   # Database user
POSTGRES_PASSWORD=<secret>   # From Secret Manager
```

**Cloud Run Configuration:**
- VPC Connector: `orchestrator-backend-connector`
- Egress: `private-ranges-only` (only VPC traffic)
- Secrets: `POSTGRES_PASSWORD` from Secret Manager

### Worker Configuration

The unified worker automatically selects PostgreSQL:

**Supervisor Configuration:**
```ini
[program:worker]
command=sh -c 'if [ "$USE_POSTGRESQL" = "true" ]; then python orchestrator/postgres_worker.py; else rq worker --url $REDIS_URL; fi'
numprocs=2  # 2 workers in parallel
```

**PostgreSQL Worker:**
- Polls database for pending tasks
- Uses connection pooling (10 connections max)
- Graceful shutdown on SIGTERM
- Exponential backoff on errors
- Automatic task retry (max 3 attempts)

### Task Queue Operations

**Enqueue a Task:**
```python
from orchestrator.a2a.unified_queue import get_unified_queue

queue = get_unified_queue()

task_id = queue.enqueue_consumer_triage(
    source_repo="owner/source",
    consumer_repo="owner/consumer",
    change_event={...},
    consumer_config={...}
)
# Returns: task-uuid-123
```

**Check Task Status:**
```python
status = queue.get_task_status(task_id)

# Returns:
# {
#   'task_id': 'task-uuid-123',
#   'status': 'finished',  # queued, started, finished, failed
#   'created_at': '2025-01-15T10:30:00Z',
#   'started_at': '2025-01-15T10:30:02Z',
#   'ended_at': '2025-01-15T10:30:45Z',
#   'result': {...},  # Triage result
#   'attempt_count': 1
# }
```

**Queue Statistics:**
```python
stats = queue.get_queue_stats()

# Returns:
# {
#   'backend': 'postgresql',
#   'queued': 5,
#   'processing': 2,
#   'completed': 100,
#   'failed': 3,
#   'avg_duration_seconds': 43.5
# }
```

### Monitoring & Maintenance

**View Queue Status:**
```bash
# SSH to PostgreSQL VM
gcloud compute ssh orchestrator-postgres-vm --zone=us-central1-a

# Connect to database
psql -U orchestrator -d orchestrator

# Check queue status
SELECT status, COUNT(*) FROM tasks GROUP BY status;

# View recent tasks
SELECT task_id, task_type, source_repo, target_repo, status, created_at
FROM tasks
ORDER BY created_at DESC
LIMIT 10;

# Check statistics
SELECT * FROM task_statistics;
```

**Cleanup Old Tasks:**
```sql
-- Manual cleanup (older than 7 days)
SELECT cleanup_old_tasks();

-- Or specific date
DELETE FROM tasks WHERE created_at < NOW() - INTERVAL '30 days';
```

**Monitor Worker Activity:**
```bash
# View Cloud Run logs
gcloud logging tail "resource.labels.service_name=architecture-kb-orchestrator" \
  --format="table(timestamp, textPayload)"

# Filter for worker logs
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND textPayload=~'PostgreSQL Worker'" \
  --limit=50
```

### Performance Tuning

**PostgreSQL Configuration:**
```sql
-- View current settings
SHOW max_connections;  -- 50
SHOW shared_buffers;   -- ~128MB on e2-micro

-- Adjust if needed (requires restart)
ALTER SYSTEM SET max_connections = 50;
ALTER SYSTEM SET work_mem = '4MB';
```

**Connection Pooling:**
- Min connections: 1
- Max connections: 10
- Adjust in `orchestrator/a2a/postgres_queue.py`

**Task Retention:**
- Default: 7 days
- Configure via `cleanup_old_tasks()` function
- Consider pg_cron for automated cleanup

### Backup & Recovery

**Manual Backup:**
```bash
# Backup database
gcloud compute ssh orchestrator-postgres-vm --zone=us-central1-a \
  --command="pg_dump -U orchestrator orchestrator > /tmp/backup.sql"

# Copy backup locally
gcloud compute scp orchestrator-postgres-vm:/tmp/backup.sql ./backup-$(date +%Y%m%d).sql \
  --zone=us-central1-a
```

**Restore from Backup:**
```bash
# Copy backup to VM
gcloud compute scp ./backup.sql orchestrator-postgres-vm:/tmp/ --zone=us-central1-a

# Restore
gcloud compute ssh orchestrator-postgres-vm --zone=us-central1-a \
  --command="psql -U orchestrator -d orchestrator < /tmp/backup.sql"
```

**Automated Backups:**
Consider setting up:
- Cloud Storage bucket for backups
- Cron job on VM for daily dumps
- Snapshot schedule for VM disk

### Cost Analysis

**Monthly Costs (PostgreSQL):**
| Resource | Configuration | Cost |
|----------|--------------|------|
| Compute Engine VM | e2-micro (0.25 vCPU, 1GB RAM) | $0-7 (free tier) |
| Persistent Disk | 30GB standard | $3 |
| VPC Connector | 2-3 instances | $0 |
| Secrets | 1 secret | $0.06 |
| **Total** | | **~$5-10/month** |

**vs Redis Memorystore:**
| Resource | Configuration | Cost |
|----------|--------------|------|
| Redis Memorystore | 1GB Basic | $45/month |
| **Total** | | **~$45/month** |

**PostgreSQL saves ~$35-40/month!**

### Troubleshooting

**Issue: Cannot connect to PostgreSQL**
```bash
# Check VM is running
gcloud compute instances describe orchestrator-postgres-vm --zone=us-central1-a

# Check PostgreSQL service
gcloud compute ssh orchestrator-postgres-vm --zone=us-central1-a \
  --command="sudo systemctl status postgresql"

# Check VPC connector
gcloud compute networks vpc-access connectors describe orchestrator-backend-connector \
  --region=us-central1
```

**Issue: Workers not picking up tasks**
```bash
# Check worker logs
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND textPayload=~'Worker'" \
  --limit=20

# Verify database connection
gcloud compute ssh orchestrator-postgres-vm --zone=us-central1-a \
  --command="psql -U orchestrator -d orchestrator -c 'SELECT COUNT(*) FROM tasks WHERE status='\''queued'\'';'"
```

**Issue: Tasks stuck in 'started' status**
```sql
-- Find stuck tasks (started > 10 minutes ago)
SELECT task_id, worker_id, started_at
FROM tasks
WHERE status = 'started'
AND started_at < NOW() - INTERVAL '10 minutes';

-- Reset stuck tasks (worker probably crashed)
UPDATE tasks
SET status = 'queued', started_at = NULL, worker_id = NULL
WHERE status = 'started'
AND started_at < NOW() - INTERVAL '10 minutes';
```

**Issue: Database performance degradation**
```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('orchestrator'));

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Vacuum and analyze
VACUUM ANALYZE;

-- Reindex if needed
REINDEX DATABASE orchestrator;
```

### Migration from Redis to PostgreSQL

If you're currently using Redis:

```bash
# 1. Deploy PostgreSQL VM
terraform apply -target=google_compute_instance.postgres

# 2. Initialize schema
# (see "After Terraform completes" section above)

# 3. Update Cloud Run environment
terraform apply  # This will update USE_POSTGRESQL=true

# 4. Redeploy application
./deploy-gcp-cloudbuild.sh

# 5. Verify workers are using PostgreSQL
gcloud logging read "resource.labels.service_name=architecture-kb-orchestrator AND textPayload=~'PostgreSQL Worker'" \
  --limit=5

# 6. (Optional) Delete Redis Memorystore
gcloud redis instances delete orchestrator-task-queue --region=us-central1
```

**Note:** Task history is NOT migrated. Old Redis tasks will be lost.

### Best Practices

1. **Monitor disk usage**: 30GB should be sufficient for millions of tasks
2. **Regular backups**: Schedule daily pg_dump to Cloud Storage
3. **Task retention**: Clean up old tasks (7-30 days)
4. **Connection pooling**: Don't exceed max_connections (50)
5. **Index maintenance**: Run VACUUM ANALYZE weekly
6. **Security**: PostgreSQL is internal-only (no public IP)
7. **Scaling**: If VM becomes bottleneck, upgrade to e2-small

### References

- **Schema**: `orchestrator/a2a/postgres_schema.sql`
- **Queue Implementation**: `orchestrator/a2a/postgres_queue.py`
- **Worker**: `orchestrator/postgres_worker.py`
- **Terraform**: `terraform/main.tf` (PostgreSQL resources)
- **Dev-nexus approach**: https://github.com/patelmm79/dev-nexus/blob/main/docs/POSTGRESQL_SETUP.md
