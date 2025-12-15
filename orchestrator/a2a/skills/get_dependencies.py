"""
Skill: get_dependencies (QUERY)

Retrieve dependency graph for a repository.
"""
import logging
from typing import Any, Dict
from orchestrator.a2a.base import BaseSkill, SkillCategory, SkillMetadata
from orchestrator.a2a.tasks import get_relationships_config

logger = logging.getLogger(__name__)


class GetDependenciesSkill(BaseSkill):
    """
    Retrieve dependency graph for a repository.
    """

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="get_dependencies",
            display_name="Get Dependencies",
            description="Retrieve dependency relationships for a repository",
            category=SkillCategory.QUERY,
            input_schema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository name (owner/name)"
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "description": "Include full relationship metadata",
                        "default": False
                    }
                },
                "required": ["repo"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "consumers": {"type": "array"},
                    "derivatives": {"type": "array"},
                    "upstream_dependencies": {"type": "array"}
                }
            },
            requires_auth=False,
            is_async=False
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve dependency information for a repository.

        Args:
            input_data: Query with repo name

        Returns:
            Dependency graph data
        """
        repo = input_data['repo']
        include_metadata = input_data.get('include_metadata', False)

        logger.info(f"Retrieving dependencies for {repo}")

        config = get_relationships_config()
        relationships = config.get('relationships', {})

        # Get downstream dependencies (consumers/derivatives of this repo)
        repo_config = relationships.get(repo, {})
        consumers = repo_config.get('consumers', [])
        derivatives = repo_config.get('derivatives', [])

        # Get upstream dependencies (repos this one depends on)
        upstream = []
        for source_repo, source_config in relationships.items():
            if source_repo == repo:
                continue

            # Check if repo is a consumer
            for consumer in source_config.get('consumers', []):
                if consumer['repo'] == repo:
                    upstream.append({
                        'repo': source_repo,
                        'relationship_type': 'api_consumer',
                        'metadata': consumer if include_metadata else None
                    })

            # Check if repo is a derivative
            for derivative in source_config.get('derivatives', []):
                if derivative['repo'] == repo:
                    upstream.append({
                        'repo': source_repo,
                        'relationship_type': 'template_fork',
                        'metadata': derivative if include_metadata else None
                    })

        result = {
            "repo": repo,
            "consumers": [c if include_metadata else {'repo': c['repo']} for c in consumers],
            "derivatives": [d if include_metadata else {'repo': d['repo']} for d in derivatives],
            "upstream_dependencies": upstream
        }

        logger.info(f"Found {len(consumers)} consumers, {len(derivatives)} derivatives, {len(upstream)} upstream for {repo}")
        return result
