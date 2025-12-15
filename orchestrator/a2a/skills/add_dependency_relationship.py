"""
Skill: add_dependency_relationship (ACTION)

Add or update dependency relationships in the configuration.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata

logger = logging.getLogger(__name__)


class AddDependencyRelationshipSkill(BaseSkill):
    """
    Add or update dependency relationships.

    NOTE: This modifies the relationships.json file.
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="add_dependency_relationship",
            display_name="Add Dependency Relationship",
            description="Add or update dependency relationships in configuration",
            category=SkillCategory.ACTION,
            input_schema={
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "string",
                        "description": "Source repository (owner/name)"
                    },
                    "target_repo": {
                        "type": "string",
                        "description": "Target repository (owner/name)"
                    },
                    "relationship_type": {
                        "type": "string",
                        "enum": ["api_consumer", "template_fork"],
                        "description": "Type of relationship"
                    },
                    "relationship_config": {
                        "type": "object",
                        "description": "Relationship configuration (interface_files, triggers, concerns, etc.)"
                    }
                },
                "required": ["source_repo", "target_repo", "relationship_type", "relationship_config"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                    "relationship": {"type": "object"}
                }
            },
            requires_auth=True,
            is_async=False
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add or update a dependency relationship.

        Args:
            input_data: Relationship data

        Returns:
            Status and updated relationship
        """
        source_repo = input_data['source_repo']
        target_repo = input_data['target_repo']
        relationship_type = input_data['relationship_type']
        relationship_config = input_data['relationship_config']

        logger.info(f"Adding {relationship_type} relationship: {source_repo} -> {target_repo}")

        # Load existing config
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "relationships.json"
        with open(config_path) as f:
            config = json.load(f)

        # Ensure source repo exists in config
        if source_repo not in config['relationships']:
            config['relationships'][source_repo] = {
                "type": "service_provider",
                "consumers": [],
                "derivatives": []
            }

        # Add relationship
        relationship = {
            "repo": target_repo,
            "relationship_type": relationship_type,
            **relationship_config
        }

        if relationship_type == 'api_consumer':
            # Check if consumer already exists
            consumers = config['relationships'][source_repo].get('consumers', [])
            existing_idx = None
            for idx, consumer in enumerate(consumers):
                if consumer['repo'] == target_repo:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                consumers[existing_idx] = relationship
                message = f"Updated existing consumer relationship"
            else:
                consumers.append(relationship)
                config['relationships'][source_repo]['consumers'] = consumers
                message = f"Added new consumer relationship"

        elif relationship_type == 'template_fork':
            # Check if derivative already exists
            derivatives = config['relationships'][source_repo].get('derivatives', [])
            existing_idx = None
            for idx, derivative in enumerate(derivatives):
                if derivative['repo'] == target_repo:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                derivatives[existing_idx] = relationship
                message = f"Updated existing template relationship"
            else:
                derivatives.append(relationship)
                config['relationships'][source_repo]['derivatives'] = derivatives
                message = f"Added new template relationship"

        # Save updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"{message}: {source_repo} -> {target_repo}")

        return {
            "status": "success",
            "message": message,
            "relationship": relationship
        }
