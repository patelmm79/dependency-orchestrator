"""
Skill: get_orchestration_status (QUERY)

Get status of async orchestration tasks.
"""
import logging
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata
from orchestrator.a2a.task_queue import get_task_queue

logger = logging.getLogger(__name__)


class GetOrchestrationStatusSkill(BaseSkill):
    """
    Query status of async orchestration tasks.
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="get_orchestration_status",
            display_name="Get Orchestration Status",
            description="Get status and results of async orchestration tasks",
            category=SkillCategory.QUERY,
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to query"
                    }
                },
                "required": ["task_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["queued", "started", "finished", "failed", "not_found"]
                    },
                    "created_at": {"type": "string"},
                    "started_at": {"type": "string"},
                    "ended_at": {"type": "string"},
                    "result": {"type": "object"},
                    "error": {"type": "string"}
                }
            },
            requires_auth=False,
            is_async=False
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get task status and results.

        Args:
            input_data: Query with task_id

        Returns:
            Task status and result data
        """
        task_id = input_data['task_id']
        logger.info(f"Querying status for task {task_id}")

        task_queue = get_task_queue()
        status = task_queue.get_task_status(task_id)

        return status
