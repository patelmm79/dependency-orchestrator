"""
A2A Task Execution - Wrapper functions for triage agents

These functions provide a uniform interface for executing consumer and template
triage analysis from A2A skills.
"""

import json
import logging
from typing import Any, Dict
from pathlib import Path
import os
import anthropic
from github import Github

from orchestrator.agents.consumer_triage import ConsumerTriageAgent
from orchestrator.agents.template_triage import TemplateTriageAgent

logger = logging.getLogger(__name__)

# Lazy-loaded dev-nexus client to avoid circular imports
_dev_nexus_client = None


def get_dev_nexus_client():
    """Get dev-nexus client lazily to avoid circular imports"""
    global _dev_nexus_client
    if _dev_nexus_client is None:
        from orchestrator.clients.dev_nexus_client import DevNexusClient
        dev_nexus_url = os.environ.get('DEV_NEXUS_URL')
        _dev_nexus_client = DevNexusClient(base_url=dev_nexus_url)
    return _dev_nexus_client


def get_relationships_config() -> Dict:
    """Load relationships configuration from config file"""
    config_path = Path(__file__).parent.parent / "config" / "relationships.json"
    with open(config_path) as f:
        return json.load(f)


def _get_clients():
    """Get initialized Anthropic and GitHub clients"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable not set")

    anthropic_client = anthropic.Anthropic(api_key=api_key)
    github_client = Github(github_token)

    return anthropic_client, github_client


async def execute_consumer_triage(
    source_repo: str,
    consumer_repo: str,
    change_event: Dict[str, Any],
    consumer_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute consumer triage analysis synchronously.

    Args:
        source_repo: Source repository (owner/name)
        consumer_repo: Consumer repository (owner/name)
        change_event: Change event with commit_sha, commit_message, changed_files, branch
        consumer_config: Consumer relationship configuration

    Returns:
        Triage result with requires_action, urgency, impact_summary, etc.
    """
    try:
        anthropic_client, github_client = _get_clients()
        dev_nexus_client = get_dev_nexus_client()

        agent = ConsumerTriageAgent(
            anthropic_client=anthropic_client,
            github_client=github_client,
            dev_nexus_client=dev_nexus_client if dev_nexus_client.enabled else None
        )

        result = await agent.analyze(
            source_repo=source_repo,
            consumer_repo=consumer_repo,
            change_event=change_event,
            consumer_config=consumer_config
        )

        return result

    except Exception as e:
        logger.error(f"Error executing consumer triage: {e}", exc_info=True)
        return {
            "requires_action": False,
            "urgency": "low",
            "impact_summary": f"Analysis failed: {str(e)}",
            "affected_files": [],
            "recommended_changes": "",
            "confidence": 0.0,
            "reasoning": str(e)
        }


async def execute_template_triage(
    template_repo: str,
    derivative_repo: str,
    change_event: Dict[str, Any],
    derivative_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute template triage analysis synchronously.

    Args:
        template_repo: Template repository (owner/name)
        derivative_repo: Derivative/fork repository (owner/name)
        change_event: Change event with commit_sha, commit_message, changed_files, branch
        derivative_config: Derivative relationship configuration

    Returns:
        Triage result with requires_action, urgency, impact_summary, etc.
    """
    try:
        anthropic_client, github_client = _get_clients()
        dev_nexus_client = get_dev_nexus_client()

        agent = TemplateTriageAgent(
            anthropic_client=anthropic_client,
            github_client=github_client,
            dev_nexus_client=dev_nexus_client if dev_nexus_client.enabled else None
        )

        result = await agent.analyze(
            template_repo=template_repo,
            derivative_repo=derivative_repo,
            change_event=change_event,
            derivative_config=derivative_config
        )

        return result

    except Exception as e:
        logger.error(f"Error executing template triage: {e}", exc_info=True)
        return {
            "requires_action": False,
            "urgency": "low",
            "impact_summary": f"Analysis failed: {str(e)}",
            "affected_files": [],
            "recommended_changes": "",
            "confidence": 0.0,
            "reasoning": str(e)
        }
