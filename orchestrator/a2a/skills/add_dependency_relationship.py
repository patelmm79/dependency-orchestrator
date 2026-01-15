"""
Skill: add_dependency_relationship (ACTION)

Add or update dependency relationships.

This skill updates relationships in dev-nexus via A2A protocol (primary),
with fallback to updating relationships.json locally.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_dev_nexus_client = None

def get_dev_nexus_client():
    """Get dev-nexus client lazily to avoid circular imports"""
    global _dev_nexus_client
    if _dev_nexus_client is None:
        from orchestrator.clients.dev_nexus_client import DevNexusClient
        import os
        dev_nexus_url = os.environ.get('DEV_NEXUS_URL')
        _dev_nexus_client = DevNexusClient(base_url=dev_nexus_url)
    return _dev_nexus_client


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

        Updates in dev-nexus via A2A protocol (primary).
        Falls back to relationships.json if dev-nexus unavailable.

        Args:
            input_data: Relationship data with:
                - source_repo: Source repository
                - target_repo: Target repository
                - relationship_type: "api_consumer" or "template_fork"
                - relationship_config: Configuration dict

        Returns:
            Status and updated relationship
        """
        source_repo = input_data['source_repo']
        target_repo = input_data['target_repo']
        relationship_type = input_data['relationship_type']
        relationship_config = input_data['relationship_config']

        logger.info(f"Adding {relationship_type} relationship: {source_repo} -> {target_repo}")

        synced_to_dev_nexus = False
        dev_nexus_error = None

        # Try to update in dev-nexus first (primary, requires Workload Identity)
        dev_nexus_client = get_dev_nexus_client()
        if dev_nexus_client.enabled:
            try:
                logger.info(f"Syncing relationship to dev-nexus: {source_repo} -> {target_repo}")
                result = await dev_nexus_client.update_dependency_relationship(
                    source_repo=source_repo,
                    target_repo=target_repo,
                    relationship_type=relationship_type,
                    config=relationship_config
                )

                if result:
                    synced_to_dev_nexus = True
                    logger.info(f"Successfully synced relationship to dev-nexus")
                else:
                    dev_nexus_error = "Failed to update dev-nexus (skill returned None)"
                    logger.warning(f"Failed to sync relationship to dev-nexus: {dev_nexus_error}")

            except Exception as e:
                dev_nexus_error = str(e)
                logger.warning(f"Error syncing to dev-nexus (will use local config): {e}")

        # Fallback: Update relationships.json locally
        try:
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
                "relationship": relationship,
                "synced_to_dev_nexus": synced_to_dev_nexus,
                "dev_nexus_error": dev_nexus_error if dev_nexus_error else None
            }

        except Exception as e:
            logger.error(f"Error updating relationships.json: {e}")
            return {
                "status": "error",
                "message": f"Failed to update relationships: {e}",
                "synced_to_dev_nexus": synced_to_dev_nexus,
                "dev_nexus_error": dev_nexus_error
            }
