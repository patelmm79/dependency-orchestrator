"""
Unified Task Queue Interface

Supports both PostgreSQL (primary) and Redis (secondary) backends.
Automatically selects backend based on USE_POSTGRESQL environment variable.
"""
import os
import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TaskQueueBackend(ABC):
    """Abstract base class for task queue backends"""

    @abstractmethod
    def enqueue_task(self, *args, **kwargs) -> str:
        """Enqueue a task and return task ID"""
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a task"""
        pass

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        pass

    @abstractmethod
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        pass


class UnifiedTaskQueue:
    """
    Unified task queue that automatically selects between PostgreSQL and Redis.

    Priority:
    1. PostgreSQL (if USE_POSTGRESQL=true)
    2. Redis (fallback)
    """

    def __init__(self):
        self.use_postgresql = os.environ.get('USE_POSTGRESQL', 'true').lower() == 'true'
        self.backend_name = None
        self.backend: Optional[TaskQueueBackend] = None

        self._initialize_backend()

    def _initialize_backend(self):
        """Initialize the appropriate backend"""
        if self.use_postgresql:
            try:
                from orchestrator.a2a.postgres_queue import get_postgres_queue
                self.backend = get_postgres_queue()
                self.backend_name = 'postgresql'
                logger.info("✅ Using PostgreSQL task queue (primary backend)")
                return
            except Exception as e:
                logger.warning(f"PostgreSQL not available: {e}")
                logger.info("Falling back to Redis...")

        # Fallback to Redis
        try:
            from orchestrator.a2a.task_queue import get_task_queue as get_redis_queue
            self.backend = get_redis_queue()
            self.backend_name = 'redis'
            logger.info("✅ Using Redis task queue (secondary backend)")
        except Exception as e:
            logger.error(f"Neither PostgreSQL nor Redis available: {e}")
            raise RuntimeError(
                "No task queue backend available. "
                "Set USE_POSTGRESQL=true with PostgreSQL configured, "
                "or set REDIS_URL for Redis backend."
            )

    def enqueue_consumer_triage(
        self,
        source_repo: str,
        consumer_repo: str,
        change_event: Dict[str, Any],
        consumer_config: Dict[str, Any]
    ) -> str:
        """
        Enqueue a consumer triage task.

        Args:
            source_repo: Source repository
            consumer_repo: Consumer repository
            change_event: Change event data
            consumer_config: Consumer configuration

        Returns:
            Task ID
        """
        if self.backend_name == 'postgresql':
            return self.backend.enqueue_task(
                skill_name='trigger_consumer_triage',
                task_type='consumer_triage',
                source_repo=source_repo,
                target_repo=consumer_repo,
                change_event=change_event,
                relationship_config=consumer_config
            )
        else:  # Redis
            from orchestrator.a2a.tasks import execute_consumer_triage_sync
            return self.backend.enqueue_task(
                execute_consumer_triage_sync,
                source_repo=source_repo,
                consumer_repo=consumer_repo,
                change_event=change_event,
                consumer_config=consumer_config
            )

    def enqueue_template_triage(
        self,
        template_repo: str,
        derivative_repo: str,
        change_event: Dict[str, Any],
        derivative_config: Dict[str, Any]
    ) -> str:
        """
        Enqueue a template triage task.

        Args:
            template_repo: Template repository
            derivative_repo: Derivative repository
            change_event: Change event data
            derivative_config: Derivative configuration

        Returns:
            Task ID
        """
        if self.backend_name == 'postgresql':
            return self.backend.enqueue_task(
                skill_name='trigger_template_triage',
                task_type='template_triage',
                source_repo=template_repo,
                target_repo=derivative_repo,
                change_event=change_event,
                relationship_config=derivative_config
            )
        else:  # Redis
            from orchestrator.a2a.tasks import execute_template_triage_sync
            return self.backend.enqueue_task(
                execute_template_triage_sync,
                template_repo=template_repo,
                derivative_repo=derivative_repo,
                change_event=change_event,
                derivative_config=derivative_config
            )

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a task.

        Args:
            task_id: Task ID

        Returns:
            Task status dictionary
        """
        return self.backend.get_task_status(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled successfully
        """
        return self.backend.cancel_task(task_id)

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.backend.get_queue_stats()
        stats['backend'] = self.backend_name
        return stats

    def get_backend_name(self) -> str:
        """Get the name of the active backend"""
        return self.backend_name


# Global unified queue instance
_global_unified_queue: Optional[UnifiedTaskQueue] = None


def get_unified_queue() -> UnifiedTaskQueue:
    """Get the global unified task queue instance"""
    global _global_unified_queue
    if _global_unified_queue is None:
        _global_unified_queue = UnifiedTaskQueue()
    return _global_unified_queue
