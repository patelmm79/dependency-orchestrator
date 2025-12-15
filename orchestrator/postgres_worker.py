#!/usr/bin/env python3
"""
PostgreSQL Worker for async task processing

Similar to RQ worker but uses PostgreSQL queue instead of Redis.
Polls for tasks, executes them, and updates status.
"""
import os
import time
import socket
import logging
import signal
import sys
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
if not os.environ.get('ANTHROPIC_API_KEY'):
    logger.error("ANTHROPIC_API_KEY environment variable not set")
    sys.exit(1)

if not os.environ.get('GITHUB_TOKEN'):
    logger.error("GITHUB_TOKEN environment variable not set")
    sys.exit(1)

# Import after env check
from orchestrator.a2a.postgres_queue import get_postgres_queue
from orchestrator.a2a.tasks import execute_consumer_triage, execute_template_triage


class PostgresWorker:
    """
    Worker that polls PostgreSQL queue and executes tasks.
    """

    def __init__(self, worker_id: Optional[str] = None, poll_interval: int = 2):
        """
        Initialize PostgreSQL worker.

        Args:
            worker_id: Unique worker identifier (default: hostname-pid)
            poll_interval: Seconds to wait between polls
        """
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}"
        self.poll_interval = poll_interval
        self.queue = get_postgres_queue()
        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        logger.info(f"✅ PostgreSQL Worker initialized: {self.worker_id}")
        logger.info(f"Polling interval: {self.poll_interval}s")

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received shutdown signal {signum}, stopping worker...")
        self.running = False

    async def _execute_task(self, task: dict) -> dict:
        """
        Execute a task based on its type.

        Args:
            task: Task data from queue

        Returns:
            Task result
        """
        task_type = task['task_type']
        logger.info(f"Executing {task_type}: {task['source_repo']} -> {task['target_repo']}")

        if task_type == 'consumer_triage':
            return await execute_consumer_triage(
                source_repo=task['source_repo'],
                consumer_repo=task['target_repo'],
                change_event=task['change_event'],
                consumer_config=task['relationship_config']
            )
        elif task_type == 'template_triage':
            return await execute_template_triage(
                template_repo=task['source_repo'],
                derivative_repo=task['target_repo'],
                change_event=task['change_event'],
                derivative_config=task['relationship_config']
            )
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    def run(self):
        """
        Main worker loop: poll for tasks and execute them.
        """
        logger.info("🚀 Worker started, polling for tasks...")

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # Get next task from queue
                task = self.queue.get_next_task(self.worker_id)

                if task is None:
                    # No tasks available, sleep and continue
                    time.sleep(self.poll_interval)
                    consecutive_errors = 0  # Reset error counter on successful poll
                    continue

                task_id = task['task_id']
                logger.info(f"📥 Picked up task: {task_id}")

                try:
                    # Execute task
                    import asyncio
                    result = asyncio.run(self._execute_task(task))

                    # Update status to finished
                    self.queue.update_task_status(
                        task_id=task_id,
                        status='finished',
                        result=result
                    )

                    logger.info(f"✅ Task {task_id} completed successfully")
                    consecutive_errors = 0

                except Exception as task_error:
                    # Task execution failed
                    logger.error(f"❌ Task {task_id} failed: {task_error}", exc_info=True)

                    # Update status to failed
                    self.queue.update_task_status(
                        task_id=task_id,
                        status='failed',
                        error=str(task_error)
                    )

                    consecutive_errors = 0  # Reset counter, task failure is different from system error

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break

            except Exception as e:
                # System error (database connection, etc.)
                consecutive_errors += 1
                logger.error(f"Worker error ({consecutive_errors}/{max_consecutive_errors}): {e}", exc_info=True)

                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, shutting down worker")
                    break

                # Exponential backoff
                backoff = min(30, 2 ** consecutive_errors)
                logger.info(f"Backing off for {backoff}s...")
                time.sleep(backoff)

        logger.info("👋 Worker stopped")
        self.queue.close()


if __name__ == "__main__":
    # Get configuration from environment
    worker_id = os.environ.get('WORKER_ID')
    poll_interval = int(os.environ.get('POLL_INTERVAL', '2'))

    # Create and run worker
    worker = PostgresWorker(worker_id=worker_id, poll_interval=poll_interval)
    worker.run()
