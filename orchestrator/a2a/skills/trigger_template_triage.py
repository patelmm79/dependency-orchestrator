"""
Skill: trigger_template_triage (ACTION)

Manually trigger template triage analysis.
"""
import logging
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata
from orchestrator.a2a.task_queue import get_task_queue
from orchestrator.a2a.tasks import execute_template_triage_sync, get_relationships_config

logger = logging.getLogger(__name__)


class TriggerTemplateTriageSkill(BaseSkill):
    """
    Manually trigger template triage analysis (async).
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="trigger_template_triage",
            display_name="Trigger Template Triage",
            description="Manually trigger async template sync analysis",
            category=SkillCategory.ACTION,
            input_schema={
                "type": "object",
                "properties": {
                    "template_repo": {
                        "type": "string",
                        "description": "Template repository (owner/name)"
                    },
                    "derivative_repo": {
                        "type": "string",
                        "description": "Derivative repository to analyze"
                    },
                    "change_event": {
                        "type": "object",
                        "description": "Change event data"
                    }
                },
                "required": ["template_repo", "derivative_repo", "change_event"]
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
        Trigger template triage analysis.

        Args:
            input_data: Triage request data

        Returns:
            Task ID and status
        """
        template_repo = input_data['template_repo']
        derivative_repo = input_data['derivative_repo']

        logger.info(f"Manually triggering template triage: {template_repo} -> {derivative_repo}")

        # Load config and find derivative relationship
        config = get_relationships_config()
        repo_config = config['relationships'].get(template_repo, {})

        derivative_config = None
        for derivative in repo_config.get('derivatives', []):
            if derivative['repo'] == derivative_repo:
                derivative_config = derivative
                break

        if not derivative_config:
            return {
                "status": "error",
                "task_id": None,
                "message": f"No derivative relationship found between {template_repo} and {derivative_repo}"
            }

        # Enqueue task
        task_queue = get_task_queue()
        task_id = task_queue.enqueue_task(
            execute_template_triage_sync,
            template_repo=template_repo,
            derivative_repo=derivative_repo,
            change_event=input_data['change_event'],
            derivative_config=derivative_config
        )

        logger.info(f"Template triage task enqueued: {task_id}")

        return {
            "status": "enqueued",
            "task_id": task_id,
            "message": f"Template sync analysis scheduled for {derivative_repo}"
        }
