-- PostgreSQL Schema for Dependency Orchestrator Task Queue
-- Based on dev-nexus approach: PostgreSQL as primary data store

-- ============================================================================
-- Task Queue Tables
-- ============================================================================

-- Tasks table: Stores all triage tasks (consumer and template)
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,  -- 'consumer_triage' or 'template_triage'
    status VARCHAR(20) NOT NULL DEFAULT 'queued',  -- 'queued', 'started', 'finished', 'failed'

    -- Input data
    source_repo VARCHAR(255) NOT NULL,
    target_repo VARCHAR(255) NOT NULL,
    change_event JSONB NOT NULL,
    relationship_config JSONB NOT NULL,

    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,

    -- Result
    result JSONB,
    error TEXT,

    -- Metadata
    worker_id VARCHAR(100),
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,

    -- Indexes
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_created_at (created_at),
    INDEX idx_tasks_source_repo (source_repo),
    INDEX idx_tasks_target_repo (target_repo),
    INDEX idx_tasks_type (task_type)
);

-- Task history: Audit trail of all task executions
CREATE TABLE IF NOT EXISTS task_history (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    worker_id VARCHAR(100),
    error TEXT,
    duration_ms INTEGER,

    INDEX idx_history_task_id (task_id),
    INDEX idx_history_timestamp (timestamp)
);

-- ============================================================================
-- Triage Results Cache
-- ============================================================================

-- Cache frequently accessed triage results for performance
CREATE TABLE IF NOT EXISTS triage_results_cache (
    id SERIAL PRIMARY KEY,
    source_repo VARCHAR(255) NOT NULL,
    target_repo VARCHAR(255) NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,

    requires_action BOOLEAN NOT NULL,
    urgency VARCHAR(20),
    impact_summary TEXT,
    confidence FLOAT,

    result_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Unique constraint to prevent duplicates
    UNIQUE(source_repo, target_repo, commit_sha),

    INDEX idx_cache_repos (source_repo, target_repo),
    INDEX idx_cache_expires (expires_at)
);

-- ============================================================================
-- Dependency Relationships (Optional: Store in DB instead of JSON file)
-- ============================================================================

CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    repo_name VARCHAR(255) UNIQUE NOT NULL,
    repo_type VARCHAR(50) DEFAULT 'service_provider',
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dependency_relationships (
    id SERIAL PRIMARY KEY,
    source_repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    target_repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- 'api_consumer' or 'template_fork'

    -- Consumer relationship config
    interface_files JSONB,
    change_triggers JSONB,

    -- Template relationship config
    shared_concerns JSONB,
    divergent_concerns JSONB,

    -- Common config
    urgency_mapping JSONB,
    metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(source_repo_id, target_repo_id, relationship_type),
    INDEX idx_relationships_source (source_repo_id),
    INDEX idx_relationships_target (target_repo_id)
);

-- ============================================================================
-- Task Queue Functions
-- ============================================================================

-- Function to clean up old tasks (older than 7 days)
CREATE OR REPLACE FUNCTION cleanup_old_tasks() RETURNS void AS $$
BEGIN
    DELETE FROM tasks WHERE created_at < NOW() - INTERVAL '7 days';
    DELETE FROM triage_results_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to get next pending task (for worker polling)
CREATE OR REPLACE FUNCTION get_next_task(worker_id_param VARCHAR)
RETURNS TABLE(
    task_id VARCHAR,
    skill_name VARCHAR,
    task_type VARCHAR,
    source_repo VARCHAR,
    target_repo VARCHAR,
    change_event JSONB,
    relationship_config JSONB
) AS $$
BEGIN
    RETURN QUERY
    UPDATE tasks
    SET status = 'started',
        started_at = NOW(),
        worker_id = worker_id_param,
        attempt_count = attempt_count + 1
    WHERE tasks.task_id = (
        SELECT t.task_id
        FROM tasks t
        WHERE t.status = 'queued'
        AND t.attempt_count < t.max_attempts
        ORDER BY t.created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING
        tasks.task_id,
        tasks.skill_name,
        tasks.task_type,
        tasks.source_repo,
        tasks.target_repo,
        tasks.change_event,
        tasks.relationship_config;
END;
$$ LANGUAGE plpgsql;

-- Function to update task status
CREATE OR REPLACE FUNCTION update_task_status(
    task_id_param VARCHAR,
    status_param VARCHAR,
    result_param JSONB DEFAULT NULL,
    error_param TEXT DEFAULT NULL
) RETURNS void AS $$
BEGIN
    UPDATE tasks
    SET status = status_param,
        ended_at = CASE WHEN status_param IN ('finished', 'failed') THEN NOW() ELSE ended_at END,
        result = COALESCE(result_param, result),
        error = error_param
    WHERE task_id = task_id_param;

    -- Log to history
    INSERT INTO task_history (task_id, status, worker_id, error)
    SELECT task_id_param, status_param, worker_id, error_param
    FROM tasks WHERE task_id = task_id_param;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_tasks_queued ON tasks(created_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_tasks_processing ON tasks(started_at) WHERE status = 'started';

-- ============================================================================
-- Statistics View
-- ============================================================================

CREATE OR REPLACE VIEW task_statistics AS
SELECT
    task_type,
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) as avg_duration_seconds,
    MAX(ended_at) as last_completed
FROM tasks
WHERE ended_at IS NOT NULL
GROUP BY task_type, status;

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Create a cleanup job (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-old-tasks', '0 2 * * *', 'SELECT cleanup_old_tasks()');
