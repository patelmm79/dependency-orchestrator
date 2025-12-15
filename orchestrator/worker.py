#!/usr/bin/env python3
"""
RQ Worker for async task processing

This worker processes tasks from the Redis queue.
Run with: rq worker --url redis://localhost:6379/0
"""
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded
if not os.environ.get('ANTHROPIC_API_KEY'):
    logger.error("ANTHROPIC_API_KEY environment variable not set")
    raise ValueError("ANTHROPIC_API_KEY is required")

if not os.environ.get('GITHUB_TOKEN'):
    logger.error("GITHUB_TOKEN environment variable not set")
    raise ValueError("GITHUB_TOKEN is required")

logger.info("RQ Worker initialized and ready to process tasks")
logger.info(f"Redis URL: {os.environ.get('REDIS_URL', 'redis://localhost:6379/0')}")

# Import task functions so they're available to the worker
from orchestrator.a2a.tasks import (
    execute_consumer_triage_sync,
    execute_template_triage_sync
)

logger.info("Task functions imported successfully")
