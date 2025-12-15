"""
Task queue management for async A2A operations using Redis Queue (RQ)
"""
import os
import logging
from typing import Any, Dict, Optional
from redis import Redis
from rq import Queue
from rq.job import Job

logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Manages async task execution using Redis Queue.

    Tasks are enqueued and processed by RQ workers.
    Results are stored in Redis with 24-hour TTL.
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize task queue.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        """
        self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_conn = Redis.from_url(self.redis_url, decode_responses=True)
        self.queue = Queue(connection=self.redis_conn, default_timeout='10m')
        logger.info(f"Task queue initialized with Redis URL: {self.redis_url}")

    def enqueue_task(
        self,
        func: callable,
        *args,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Enqueue a task for async execution.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            task_id: Optional custom task ID
            **kwargs: Keyword arguments for function

        Returns:
            Task ID
        """
        job = self.queue.enqueue(
            func,
            *args,
            job_id=task_id,
            result_ttl=86400,  # 24 hours
            failure_ttl=86400,
            **kwargs
        )
        logger.info(f"Enqueued task {job.id}")
        return job.id

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a task.

        Args:
            task_id: Task ID

        Returns:
            Dictionary with status, result, and metadata
        """
        try:
            job = Job.fetch(task_id, connection=self.redis_conn)

            status = {
                'task_id': task_id,
                'status': job.get_status(),
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None,
            }

            if job.is_finished:
                status['result'] = job.result
            elif job.is_failed:
                status['error'] = str(job.exc_info) if job.exc_info else 'Unknown error'

            return status

        except Exception as e:
            logger.error(f"Error fetching task status: {e}")
            return {
                'task_id': task_id,
                'status': 'not_found',
                'error': str(e)
            }

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled successfully
        """
        try:
            job = Job.fetch(task_id, connection=self.redis_conn)
            job.cancel()
            logger.info(f"Cancelled task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            return False


# Global task queue instance
_global_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get the global task queue instance"""
    global _global_queue
    if _global_queue is None:
        _global_queue = TaskQueue()
    return _global_queue
