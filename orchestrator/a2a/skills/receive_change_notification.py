"""
Skill: receive_change_notification (EVENT)

Primary entry point for change notifications from source repositories.
Triggers async triage analysis for all dependent repositories.
"""
import logging
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata
from orchestrator.a2a.task_queue import get_task_queue
from orchestrator.a2a.tasks import execute_consumer_triage_sync, execute_template_triage_sync, get_relationships_config

logger = logging.getLogger(__name__)


class ReceiveChangeNotificationSkill(BaseSkill):
    """
    Receive change notification from a source repository and orchestrate impact analysis.
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="receive_change_notification",
            display_name="Receive Change Notification",
            description="Process incoming change notifications and trigger impact analysis for dependent repositories",
            category=SkillCategory.EVENT,
            input_schema={
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "string",
                        "description": "Source repository (owner/name)"
                    },
                    "commit_sha": {
                        "type": "string",
                        "description": "Commit SHA"
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Commit message"
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name"
                    },
                    "changed_files": {
                        "type": "array",
                        "description": "List of changed files with patterns/keywords"
                    },
                    "pattern_summary": {
                        "type": "object",
                        "description": "Summary of detected patterns"
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "Event timestamp"
                    }
                },
                "required": ["source_repo", "commit_sha", "commit_message", "branch"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["accepted", "no_relationships"]
                    },
                    "source_repo": {"type": "string"},
                    "consumers_scheduled": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "derivatives_scheduled": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "total_dependents": {"type": "integer"}
                }
            },
            requires_auth=False,
            is_async=True
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process change notification and schedule triage tasks.

        Args:
            input_data: Change event data

        Returns:
            Status with scheduled tasks
        """
        source_repo = input_data['source_repo']
        logger.info(f"Received change notification from {source_repo}")

        # Load relationships
        config = get_relationships_config()

        if source_repo not in config['relationships']:
            logger.info(f"No relationships configured for {source_repo}")
            return {
                "status": "no_relationships",
                "source_repo": source_repo,
                "consumers_scheduled": [],
                "derivatives_scheduled": [],
                "total_dependents": 0
            }

        repo_config = config['relationships'][source_repo]
        task_queue = get_task_queue()

        consumers_scheduled = []
        derivatives_scheduled = []

        # Schedule consumer triage tasks
        if 'consumers' in repo_config:
            for consumer in repo_config['consumers']:
                task_id = task_queue.enqueue_task(
                    execute_consumer_triage_sync,
                    source_repo=source_repo,
                    consumer_repo=consumer['repo'],
                    change_event=input_data,
                    consumer_config=consumer
                )
                consumers_scheduled.append({
                    "repo": consumer['repo'],
                    "task_id": task_id
                })
                logger.info(f"Scheduled consumer triage for {consumer['repo']}: {task_id}")

        # Schedule template triage tasks
        if 'derivatives' in repo_config:
            for derivative in repo_config['derivatives']:
                task_id = task_queue.enqueue_task(
                    execute_template_triage_sync,
                    template_repo=source_repo,
                    derivative_repo=derivative['repo'],
                    change_event=input_data,
                    derivative_config=derivative
                )
                derivatives_scheduled.append({
                    "repo": derivative['repo'],
                    "task_id": task_id
                })
                logger.info(f"Scheduled template triage for {derivative['repo']}: {task_id}")

        return {
            "status": "accepted",
            "source_repo": source_repo,
            "consumers_scheduled": consumers_scheduled,
            "derivatives_scheduled": derivatives_scheduled,
            "total_dependents": len(consumers_scheduled) + len(derivatives_scheduled)
        }
