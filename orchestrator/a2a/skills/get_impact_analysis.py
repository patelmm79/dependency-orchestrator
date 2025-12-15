"""
Skill: get_impact_analysis (QUERY)

Synchronously query impact of specific changes on a target repository.
"""
import logging
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata
from orchestrator.a2a.tasks import execute_consumer_triage, execute_template_triage, get_relationships_config

logger = logging.getLogger(__name__)


class GetImpactAnalysisSkill(BaseSkill):
    """
    Get synchronous impact analysis for a specific change on a target repository.
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="get_impact_analysis",
            display_name="Get Impact Analysis",
            description="Synchronously analyze impact of changes on a specific dependent repository",
            category=SkillCategory.QUERY,
            input_schema={
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "string",
                        "description": "Source repository (owner/name)"
                    },
                    "target_repo": {
                        "type": "string",
                        "description": "Target repository to analyze"
                    },
                    "change_event": {
                        "type": "object",
                        "description": "Change event data"
                    },
                    "relationship_type": {
                        "type": "string",
                        "enum": ["consumer", "template"],
                        "description": "Type of relationship"
                    }
                },
                "required": ["source_repo", "target_repo", "change_event", "relationship_type"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "requires_action": {"type": "boolean"},
                    "urgency": {"type": "string"},
                    "impact_summary": {"type": "string"},
                    "affected_files": {"type": "array"},
                    "recommended_changes": {"type": "string"},
                    "confidence": {"type": "number"},
                    "reasoning": {"type": "string"}
                }
            },
            requires_auth=False,
            is_async=False
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute impact analysis synchronously.

        Args:
            input_data: Analysis request data

        Returns:
            Triage result
        """
        source_repo = input_data['source_repo']
        target_repo = input_data['target_repo']
        relationship_type = input_data['relationship_type']

        logger.info(f"Impact analysis: {source_repo} -> {target_repo} ({relationship_type})")

        # Load relationships config
        config = get_relationships_config()
        repo_config = config['relationships'].get(source_repo, {})

        # Find target config
        target_config = None
        if relationship_type == 'consumer' and 'consumers' in repo_config:
            for consumer in repo_config['consumers']:
                if consumer['repo'] == target_repo:
                    target_config = consumer
                    break
        elif relationship_type == 'template' and 'derivatives' in repo_config:
            for derivative in repo_config['derivatives']:
                if derivative['repo'] == target_repo:
                    target_config = derivative
                    break

        if not target_config:
            return {
                "requires_action": False,
                "urgency": "none",
                "impact_summary": "Relationship not found in configuration",
                "affected_files": [],
                "recommended_changes": "",
                "confidence": 0.0,
                "reasoning": f"No {relationship_type} relationship found between {source_repo} and {target_repo}"
            }

        # Execute appropriate triage
        if relationship_type == 'consumer':
            result = await execute_consumer_triage(
                source_repo=source_repo,
                consumer_repo=target_repo,
                change_event=input_data['change_event'],
                consumer_config=target_config
            )
        else:
            result = await execute_template_triage(
                template_repo=source_repo,
                derivative_repo=target_repo,
                change_event=input_data['change_event'],
                derivative_config=target_config
            )

        return result
