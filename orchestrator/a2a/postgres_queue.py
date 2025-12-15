"""
PostgreSQL-based Task Queue for A2A Operations

Similar to dev-nexus approach: PostgreSQL as primary backend
Falls back to Redis if PostgreSQL is not available
"""
import os
import uuid
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


class PostgresTaskQueue:
    """
    PostgreSQL-based task queue for async operations.

    Provides similar interface to Redis Queue but uses PostgreSQL for persistence.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 5432,
        database: str = "orchestrator",
        user: Optional[str] = None,
        password: Optional[str] = None,
        min_connections: int = 1,
        max_connections: int = 10
    ):
        """
        Initialize PostgreSQL task queue.

        Args:
            host: PostgreSQL host (defaults to POSTGRES_HOST env var)
            port: PostgreSQL port (defaults to 5432)
            database: Database name (defaults to 'orchestrator')
            user: Database user (defaults to POSTGRES_USER env var)
            password: Database password (defaults to POSTGRES_PASSWORD env var)
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
        """
        self.host = host or os.environ.get('POSTGRES_HOST', 'localhost')
        self.port = port
        self.database = database or os.environ.get('POSTGRES_DB', 'orchestrator')
        self.user = user or os.environ.get('POSTGRES_USER', 'orchestrator')
        self.password = password or os.environ.get('POSTGRES_PASSWORD')

        if not self.password:
            raise ValueError("PostgreSQL password is required (set POSTGRES_PASSWORD)")

        # Create connection pool
        try:
            self.pool = ThreadedConnectionPool(
                min_connections,
                max_connections,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"PostgreSQL task queue initialized: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def _get_connection(self):
        """Get a connection from the pool"""
        return self.pool.getconn()

    def _return_connection(self, conn):
        """Return a connection to the pool"""
        self.pool.putconn(conn)

    def enqueue_task(
        self,
        skill_name: str,
        task_type: str,
        source_repo: str,
        target_repo: str,
        change_event: Dict[str, Any],
        relationship_config: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> str:
        """
        Enqueue a task for async execution.

        Args:
            skill_name: Name of the A2A skill to execute
            task_type: Type of task ('consumer_triage' or 'template_triage')
            source_repo: Source repository
            target_repo: Target repository
            change_event: Change event data
            relationship_config: Relationship configuration
            task_id: Optional custom task ID

        Returns:
            Task ID
        """
        task_id = task_id or str(uuid.uuid4())
        conn = self._get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks (
                        task_id, skill_name, task_type, status,
                        source_repo, target_repo, change_event, relationship_config
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    task_id,
                    skill_name,
                    task_type,
                    'queued',
                    source_repo,
                    target_repo,
                    Json(change_event),
                    Json(relationship_config)
                ))
                conn.commit()
                logger.info(f"Enqueued task {task_id}: {task_type} {source_repo} -> {target_repo}")
                return task_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Error enqueueing task: {e}")
            raise
        finally:
            self._return_connection(conn)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a task.

        Args:
            task_id: Task ID

        Returns:
            Dictionary with status, result, and metadata
        """
        conn = self._get_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        task_id, skill_name, task_type, status,
                        source_repo, target_repo,
                        created_at, started_at, ended_at,
                        result, error, worker_id, attempt_count
                    FROM tasks
                    WHERE task_id = %s
                """, (task_id,))

                row = cur.fetchone()

                if not row:
                    return {
                        'task_id': task_id,
                        'status': 'not_found',
                        'error': 'Task not found'
                    }

                return {
                    'task_id': row['task_id'],
                    'status': row['status'],
                    'skill_name': row['skill_name'],
                    'task_type': row['task_type'],
                    'source_repo': row['source_repo'],
                    'target_repo': row['target_repo'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                    'ended_at': row['ended_at'].isoformat() if row['ended_at'] else None,
                    'result': row['result'],
                    'error': row['error'],
                    'worker_id': row['worker_id'],
                    'attempt_count': row['attempt_count']
                }

        finally:
            self._return_connection(conn)

    def get_next_task(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get next pending task for worker processing.

        Uses SELECT FOR UPDATE SKIP LOCKED for concurrent worker safety.

        Args:
            worker_id: Worker identifier

        Returns:
            Task data or None if no tasks available
        """
        conn = self._get_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM get_next_task(%s)", (worker_id,))
                row = cur.fetchone()
                conn.commit()

                if not row:
                    return None

                return dict(row)

        except Exception as e:
            conn.rollback()
            logger.error(f"Error getting next task: {e}")
            return None
        finally:
            self._return_connection(conn)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update task status and result.

        Args:
            task_id: Task ID
            status: New status ('started', 'finished', 'failed')
            result: Task result data
            error: Error message if failed
        """
        conn = self._get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT update_task_status(%s, %s, %s, %s)",
                    (task_id, status, Json(result) if result else None, error)
                )
                conn.commit()
                logger.info(f"Updated task {task_id}: {status}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating task status: {e}")
            raise
        finally:
            self._return_connection(conn)

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled successfully
        """
        conn = self._get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE tasks
                    SET status = 'failed', error = 'Cancelled by user', ended_at = NOW()
                    WHERE task_id = %s AND status IN ('queued', 'started')
                """, (task_id,))
                conn.commit()
                cancelled = cur.rowcount > 0
                if cancelled:
                    logger.info(f"Cancelled task {task_id}")
                return cancelled

        except Exception as e:
            conn.rollback()
            logger.error(f"Error cancelling task: {e}")
            return False
        finally:
            self._return_connection(conn)

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get task queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        conn = self._get_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Count by status
                cur.execute("""
                    SELECT status, COUNT(*) as count
                    FROM tasks
                    GROUP BY status
                """)
                status_counts = {row['status']: row['count'] for row in cur.fetchall()}

                # Count by type
                cur.execute("""
                    SELECT task_type, COUNT(*) as count
                    FROM tasks
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY task_type
                """)
                type_counts = {row['task_type']: row['count'] for row in cur.fetchall()}

                # Average processing time
                cur.execute("""
                    SELECT
                        AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) as avg_duration_seconds
                    FROM tasks
                    WHERE status = 'finished'
                    AND ended_at IS NOT NULL
                    AND created_at > NOW() - INTERVAL '24 hours'
                """)
                avg_duration = cur.fetchone()['avg_duration_seconds'] or 0

                return {
                    'status_counts': status_counts,
                    'type_counts': type_counts,
                    'avg_duration_seconds': float(avg_duration),
                    'queued': status_counts.get('queued', 0),
                    'processing': status_counts.get('started', 0),
                    'completed': status_counts.get('finished', 0),
                    'failed': status_counts.get('failed', 0)
                }

        finally:
            self._return_connection(conn)

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        Clean up tasks older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of tasks deleted
        """
        conn = self._get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM tasks
                    WHERE created_at < NOW() - INTERVAL '%s days'
                """, (days,))
                conn.commit()
                deleted = cur.rowcount
                logger.info(f"Cleaned up {deleted} old tasks")
                return deleted

        except Exception as e:
            conn.rollback()
            logger.error(f"Error cleaning up tasks: {e}")
            return 0
        finally:
            self._return_connection(conn)

    def close(self):
        """Close all connections in the pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# Global instance
_global_postgres_queue: Optional[PostgresTaskQueue] = None


def get_postgres_queue() -> PostgresTaskQueue:
    """Get the global PostgreSQL task queue instance"""
    global _global_postgres_queue
    if _global_postgres_queue is None:
        _global_postgres_queue = PostgresTaskQueue()
    return _global_postgres_queue
