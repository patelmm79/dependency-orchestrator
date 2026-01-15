#!/usr/bin/env python3
"""
Dependency Orchestrator - Unified A2A + Legacy Webhook Service

This version provides:
1. A2A protocol endpoints (/.well-known/agent.json, /a2a/*)
2. Legacy webhook endpoints (/api/webhook/*, /api/test/*, /api/relationships)

Stateless architecture: Uses FastAPI BackgroundTasks for async processing.
No database or task queue required - fully compatible with simple deployments.
"""

import os
import json
import logging
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import anthropic
from github import Github

# Import triage agents
from orchestrator.agents.consumer_triage import ConsumerTriageAgent
from orchestrator.agents.template_triage import TemplateTriageAgent

# Import dev-nexus client
from orchestrator.clients.dev_nexus_client import DevNexusClient

# Import A2A components
from orchestrator.a2a.server import create_a2a_app, register_all_skills

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register all A2A skills at startup
register_all_skills()

# Create unified app with A2A endpoints
app = create_a2a_app()
app.title = "Dependency Orchestrator (A2A + Legacy)"
app.description = "Unified dependency orchestration service with A2A protocol and legacy webhook support"
app.version = "2.0.0"

# API Key Authentication Setup (shared with A2A)
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
ORCHESTRATOR_API_KEY = os.environ.get('ORCHESTRATOR_API_KEY')
REQUIRE_AUTH = os.environ.get('REQUIRE_AUTH', 'false').lower() == 'true'

if REQUIRE_AUTH and not ORCHESTRATOR_API_KEY:
    logger.warning("REQUIRE_AUTH=true but ORCHESTRATOR_API_KEY not set. Authentication will fail!")


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Verify the API key from request header"""
    if not REQUIRE_AUTH:
        return True

    if not api_key or not ORCHESTRATOR_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if not secrets.compare_digest(api_key, ORCHESTRATOR_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    return True


# Initialize clients
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

if not ANTHROPIC_API_KEY:
    logger.error("ANTHROPIC_API_KEY environment variable not set")
    raise ValueError("ANTHROPIC_API_KEY is required")

if not GITHUB_TOKEN:
    logger.error("GITHUB_TOKEN environment variable not set")
    raise ValueError("GITHUB_TOKEN is required")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
github_client = Github(GITHUB_TOKEN)

# Initialize dev-nexus client (optional integration)
DEV_NEXUS_URL = os.environ.get('DEV_NEXUS_URL')
dev_nexus_client = DevNexusClient(base_url=DEV_NEXUS_URL)

# Load relationships configuration
config_path = Path(__file__).parent.parent / "config" / "relationships.json"
with open(config_path) as f:
    RELATIONSHIPS_CONFIG = json.load(f)


class ChangeEvent(BaseModel):
    """Incoming change notification from a repository"""
    source_repo: str
    commit_sha: str
    commit_message: str
    branch: str
    changed_files: List[Dict]
    pattern_summary: Dict
    timestamp: str


class TriageResult(BaseModel):
    """Result from a triage agent analysis"""
    requires_action: bool
    urgency: str
    impact_summary: str
    affected_files: List[str]
    recommended_changes: str
    confidence: float
    reasoning: str


# ============================================================================
# LEGACY ENDPOINTS (for backward compatibility)
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint (public, no auth required)"""
    return {
        "service": "Dependency Orchestrator",
        "status": "healthy",
        "version": "2.0.0",
        "mode": "unified_a2a_legacy",
        "authentication_required": REQUIRE_AUTH,
        "a2a_enabled": True,
        "endpoints": {
            "agent_card": "/.well-known/agent.json",
            "a2a_health": "/a2a/health",
            "a2a_skills": "/a2a/skills",
            "a2a_execute": "/a2a/execute",
            "legacy_webhook": "/api/webhook/change-notification",
            "legacy_relationships": "/api/relationships"
        }
    }


@app.get("/health")
async def health():
    """Simple health check endpoint for Cloud Run (public, no auth required)"""
    return {"status": "healthy"}


@app.get("/api/relationships", dependencies=[Depends(verify_api_key)])
async def get_relationships():
    """Get all configured relationships"""
    return RELATIONSHIPS_CONFIG


@app.get("/api/relationships/{repo_owner}/{repo_name}", dependencies=[Depends(verify_api_key)])
async def get_repo_relationships(repo_owner: str, repo_name: str):
    """Get relationships for a specific repository"""
    repo_full_name = f"{repo_owner}/{repo_name}"

    if repo_full_name not in RELATIONSHIPS_CONFIG['relationships']:
        raise HTTPException(status_code=404, detail="Repository not found in relationships")

    return RELATIONSHIPS_CONFIG['relationships'][repo_full_name]


# ============================================================================
# BACKGROUND TASK PROCESSORS (for async triage)
# ============================================================================

async def process_consumer_relationship(event: ChangeEvent, consumer_config: Dict, source_config: Dict):
    """Process API consumer dependency relationship in the background"""
    try:
        logger.info(f"Processing consumer relationship: {event.source_repo} -> {consumer_config['repo']}")

        # Initialize consumer triage agent
        agent = ConsumerTriageAgent(
            anthropic_client=anthropic_client,
            github_client=github_client,
            dev_nexus_client=dev_nexus_client
        )

        # Run triage analysis
        result = await agent.analyze(
            source_repo=event.source_repo,
            consumer_repo=consumer_config['repo'],
            change_event=event.dict(),
            consumer_config=consumer_config
        )

        logger.info(f"Triage result for {consumer_config['repo']}: action_required={result['requires_action']}, urgency={result['urgency']}")

        # Post lesson learned to dev-nexus
        if dev_nexus_client.enabled and result.get('reasoning'):
            await dev_nexus_client.post_lesson_learned(
                repo=event.source_repo,
                lesson=f"Consumer impact analysis: {result['impact_summary']}",
                source_commit=event.commit_sha,
                confidence=result.get('confidence', 0.8),
                category="consumer_triage"
            )

    except Exception as e:
        logger.error(f"Error processing consumer relationship: {e}", exc_info=True)


async def process_template_relationship(event: ChangeEvent, derivative_config: Dict, source_config: Dict):
    """Process template fork relationship in the background"""
    try:
        logger.info(f"Processing template relationship: {event.source_repo} -> {derivative_config['repo']}")

        # Initialize template triage agent
        agent = TemplateTriageAgent(
            anthropic_client=anthropic_client,
            github_client=github_client,
            dev_nexus_client=dev_nexus_client
        )

        # Run triage analysis
        result = await agent.analyze(
            template_repo=event.source_repo,
            derivative_repo=derivative_config['repo'],
            change_event=event.dict(),
            derivative_config=derivative_config
        )

        logger.info(f"Triage result for {derivative_config['repo']}: action_required={result['requires_action']}, urgency={result['urgency']}")

        # Post lesson learned to dev-nexus
        if dev_nexus_client.enabled and result.get('reasoning'):
            await dev_nexus_client.post_lesson_learned(
                repo=event.source_repo,
                lesson=f"Template sync analysis: {result['impact_summary']}",
                source_commit=event.commit_sha,
                confidence=result.get('confidence', 0.8),
                category="template_triage"
            )

    except Exception as e:
        logger.error(f"Error processing template relationship: {e}", exc_info=True)


@app.post("/api/webhook/change-notification", dependencies=[Depends(verify_api_key)])
async def handle_change_notification(event: ChangeEvent, background_tasks: BackgroundTasks):
    """
    LEGACY endpoint: Handle incoming change notifications from repositories.
    This is called by GitHub Actions after pattern analysis.

    Uses BackgroundTasks for asynchronous processing (stateless, no task queue).
    """
    logger.info(f"[LEGACY] Received change notification from {event.source_repo}")

    # Check if this repo has any relationships
    if event.source_repo not in RELATIONSHIPS_CONFIG['relationships']:
        logger.info(f"No relationships configured for {event.source_repo}")
        return {"status": "no_relationships", "message": "No dependent repositories configured"}

    repo_config = RELATIONSHIPS_CONFIG['relationships'][event.source_repo]

    consumers_scheduled = []
    derivatives_scheduled = []

    # Schedule consumer triage tasks using BackgroundTasks
    if 'consumers' in repo_config:
        for consumer in repo_config['consumers']:
            background_tasks.add_task(
                process_consumer_relationship,
                event,
                consumer,
                repo_config
            )
            consumers_scheduled.append(consumer['repo'])
            logger.info(f"Scheduled consumer triage for {consumer['repo']}")

    # Schedule template triage tasks using BackgroundTasks
    if 'derivatives' in repo_config:
        for derivative in repo_config['derivatives']:
            background_tasks.add_task(
                process_template_relationship,
                event,
                derivative,
                repo_config
            )
            derivatives_scheduled.append(derivative['repo'])
            logger.info(f"Scheduled template triage for {derivative['repo']}")

    return {
        "status": "accepted",
        "source_repo": event.source_repo,
        "consumers_scheduled": consumers_scheduled,
        "derivatives_scheduled": derivatives_scheduled,
        "total_dependents": len(consumers_scheduled) + len(derivatives_scheduled)
    }


@app.post("/api/test/consumer-triage", dependencies=[Depends(verify_api_key)])
async def test_consumer_triage(
    source_repo: str,
    consumer_repo: str,
    test_changes: Dict
):
    """Test endpoint for consumer triage agent"""
    consumer_config = None

    # Find consumer config
    if source_repo in RELATIONSHIPS_CONFIG['relationships']:
        for consumer in RELATIONSHIPS_CONFIG['relationships'][source_repo].get('consumers', []):
            if consumer['repo'] == consumer_repo:
                consumer_config = consumer
                break

    if not consumer_config:
        raise HTTPException(status_code=404, detail="Consumer relationship not found")

    agent = ConsumerTriageAgent(
        anthropic_client=anthropic_client,
        github_client=github_client,
        dev_nexus_client=dev_nexus_client
    )

    result = await agent.analyze(
        source_repo=source_repo,
        consumer_repo=consumer_repo,
        change_event=test_changes,
        consumer_config=consumer_config
    )

    return result


@app.post("/api/test/template-triage", dependencies=[Depends(verify_api_key)])
async def test_template_triage(
    template_repo: str,
    derivative_repo: str,
    test_changes: Dict
):
    """Test endpoint for template triage agent"""
    derivative_config = None

    # Find derivative config
    if template_repo in RELATIONSHIPS_CONFIG['relationships']:
        for derivative in RELATIONSHIPS_CONFIG['relationships'][template_repo].get('derivatives', []):
            if derivative['repo'] == derivative_repo:
                derivative_config = derivative
                break

    if not derivative_config:
        raise HTTPException(status_code=404, detail="Template relationship not found")

    agent = TemplateTriageAgent(
        anthropic_client=anthropic_client,
        github_client=github_client,
        dev_nexus_client=dev_nexus_client
    )

    result = await agent.analyze(
        template_repo=template_repo,
        derivative_repo=derivative_repo,
        change_event=test_changes,
        derivative_config=derivative_config
    )

    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
