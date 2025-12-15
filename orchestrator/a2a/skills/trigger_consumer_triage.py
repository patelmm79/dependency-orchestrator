"""
Skill: trigger_consumer_triage (ACTION)

Manually trigger consumer triage analysis.
"""
import logging
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata
from orchestrator.a2a.task_queue import get_task_queue
from orchestrator.a2a.tasks import execute_consumer_triage_sync, get_relationships_config

logger = logging.getLogger(__name__)


class TriggerConsumerTriageSkill(BaseSkill):
    """
    Manually trigger consumer triage analysis (async).
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="trigger_consumer_triage",
            display_name="Trigger Consumer Triage",
            description="Manually trigger async consumer triage analysis",
            category=SkillCategory.ACTION,
            input_schema={
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "string",
                        "description": "Source repository (owner/name)"
                    },
                    "consumer_repo": {
                        "type": "string",
                        "description": "Consumer repository to analyze"
                    },
                    "change_event": {
                        "type": "object",
                        "description": "Change event data"
                    }
                },
                "required": ["source_repo", "consumer_repo", "change_event"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "task_id": {"type": "string"},
                    "message": {"type": "string"}
                }
            },
            requires_auth=True,
            is_async=True
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger consumer triage analysis.

        Args:
            input_data: Triage request data

        Returns:
            Task ID and status
        """
        source_repo = input_data['source_repo']
        consumer_repo = input_data['consumer_repo']

        logger.info(f"Manually triggering consumer triage: {source_repo} -> {consumer_repo}")

        # Load config and find consumer relationship
        config = get_relationships_config()
        repo_config = config['relationships'].get(source_repo, {})

        consumer_config = None
        for consumer in repo_config.get('consumers', []):
            if consumer['repo'] == consumer_repo:
                consumer_config = consumer
                break

        if not consumer_config:
            return {
                "status": "error",
                "task_id": None,
                "message": f"No consumer relationship found between {source_repo} and {consumer_repo}"
            }

        # Enqueue task
        task_queue = get_task_queue()
        task_id = task_queue.enqueue_task(
            execute_consumer_triage_sync,
            source_repo=source_repo,
            consumer_repo=consumer_repo,
            change_event=input_data['change_event'],
            consumer_config=consumer_config
        )

        logger.info(f"Consumer triage task enqueued: {task_id}")

        return {
            "status": "enqueued",
            "task_id": task_id,
            "message": f"Consumer triage analysis scheduled for {consumer_repo}"
        }
