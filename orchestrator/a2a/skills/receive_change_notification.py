"""
Skill: receive_change_notification (EVENT)

Receive change notifications from source repositories.
Orchestration is handled at the HTTP/webhook layer with BackgroundTasks.
"""
import logging
import json
from typing import Any, Dict
from pathlib import Path
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata

logger = logging.getLogger(__name__)


def get_relationships_config() -> Dict:
    """Load relationships configuration"""
    config_path = Path(__file__).parent.parent.parent / "config" / "relationships.json"
    with open(config_path) as f:
        return json.load(f)


class ReceiveChangeNotificationSkill(BaseSkill):
    """
    Receive and validate change notifications from source repositories.

    Note: Actual orchestration/triage is handled at the HTTP layer with BackgroundTasks.
    This skill validates the notification and returns which dependents will be analyzed.
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="receive_change_notification",
            display_name="Receive Change Notification",
            description="Receive and validate change notifications - orchestration handled at HTTP layer",
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
                    "dependents": {
                        "type": "object",
                        "properties": {
                            "consumers": {"type": "array"},
                            "derivatives": {"type": "array"}
                        }
                    }
                }
            },
            requires_auth=False,
            is_async=False
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate change notification and return dependents that will be analyzed.

        Args:
            input_data: Change event data

        Returns:
            Validation result with dependents list
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
                "dependents": {
                    "consumers": [],
                    "derivatives": []
                }
            }

        repo_config = config['relationships'][source_repo]
        consumers = [c['repo'] for c in repo_config.get('consumers', [])]
        derivatives = [d['repo'] for d in repo_config.get('derivatives', [])]

        logger.info(f"Identified {len(consumers)} consumers and {len(derivatives)} derivatives for {source_repo}")

        return {
            "status": "accepted",
            "source_repo": source_repo,
            "dependents": {
                "consumers": consumers,
                "derivatives": derivatives
            }
        }
