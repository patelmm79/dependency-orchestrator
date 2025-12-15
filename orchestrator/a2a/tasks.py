"""
Background tasks for A2A async operations.

These functions are executed by RQ workers.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict
import anthropic
from github import Github

# Import triage agents
from orchestrator.agents.consumer_triage import ConsumerTriageAgent
from orchestrator.agents.template_triage import TemplateTriageAgent
from orchestrator.clients.dev_nexus_client import DevNexusClient

logger = logging.getLogger(__name__)


def get_clients():
    """Initialize and return API clients"""
    anthropic_client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    github_client = Github(os.environ.get('GITHUB_TOKEN'))
    dev_nexus_url = os.environ.get('DEV_NEXUS_URL')
    dev_nexus_client = DevNexusClient(base_url=dev_nexus_url)
    return anthropic_client, github_client, dev_nexus_client


def get_relationships_config():
    """Load relationships configuration"""
    config_path = Path(__file__).parent.parent.parent / "config" / "relationships.json"
    with open(config_path) as f:
        return json.load(f)


async def execute_consumer_triage(
    source_repo: str,
    consumer_repo: str,
    change_event: Dict,
    consumer_config: Dict
) -> Dict:
    """
    Execute consumer triage analysis.

    Args:
        source_repo: Source repository name
        consumer_repo: Consumer repository name
        change_event: Change event data
        consumer_config: Consumer configuration

    Returns:
        Triage result dictionary
    """
    logger.info(f"Executing consumer triage: {source_repo} -> {consumer_repo}")

    anthropic_client, github_client, dev_nexus_client = get_clients()

    agent = ConsumerTriageAgent(
        anthropic_client=anthropic_client,
        github_client=github_client,
        dev_nexus_client=dev_nexus_client
    )

    result = await agent.analyze(
        source_repo=source_repo,
        consumer_repo=consumer_repo,
        change_event=change_event,
        consumer_config=consumer_config
    )

    logger.info(f"Consumer triage completed: action_required={result['requires_action']}")
    return result


async def execute_template_triage(
    template_repo: str,
    derivative_repo: str,
    change_event: Dict,
    derivative_config: Dict
) -> Dict:
    """
    Execute template triage analysis.

    Args:
        template_repo: Template repository name
        derivative_repo: Derivative repository name
        change_event: Change event data
        derivative_config: Derivative configuration

    Returns:
        Triage result dictionary
    """
    logger.info(f"Executing template triage: {template_repo} -> {derivative_repo}")

    anthropic_client, github_client, dev_nexus_client = get_clients()

    agent = TemplateTriageAgent(
        anthropic_client=anthropic_client,
        github_client=github_client,
        dev_nexus_client=dev_nexus_client
    )

    result = await agent.analyze(
        template_repo=template_repo,
        derivative_repo=derivative_repo,
        change_event=change_event,
        derivative_config=derivative_config
    )

    logger.info(f"Template triage completed: action_required={result['requires_action']}")
    return result


def execute_consumer_triage_sync(
    source_repo: str,
    consumer_repo: str,
    change_event: Dict,
    consumer_config: Dict
) -> Dict:
    """
    Synchronous wrapper for execute_consumer_triage.
    Used by RQ workers which don't support async.
    """
    import asyncio
    return asyncio.run(execute_consumer_triage(
        source_repo, consumer_repo, change_event, consumer_config
    ))


def execute_template_triage_sync(
    template_repo: str,
    derivative_repo: str,
    change_event: Dict,
    derivative_config: Dict
) -> Dict:
    """
    Synchronous wrapper for execute_template_triage.
    Used by RQ workers which don't support async.
    """
    import asyncio
    return asyncio.run(execute_template_triage(
        template_repo, derivative_repo, change_event, derivative_config
    ))
