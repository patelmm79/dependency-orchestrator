#!/usr/bin/env python3
"""
Orchestrator Service - Coordinates dependency notifications and triage agents
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import anthropic
from github import Github

# Import triage agents
from agents.consumer_triage import ConsumerTriageAgent
from agents.template_triage import TemplateTriageAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Architecture KB Orchestrator",
    description="Dependency notification and triage orchestration service",
    version="1.0.0"
)

# Initialize clients
anthropic_client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
github_client = Github(os.environ.get('GITHUB_TOKEN'))

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


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Architecture KB Orchestrator",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/api/relationships")
async def get_relationships():
    """Get all configured relationships"""
    return RELATIONSHIPS_CONFIG


@app.get("/api/relationships/{repo_owner}/{repo_name}")
async def get_repo_relationships(repo_owner: str, repo_name: str):
    """Get relationships for a specific repository"""
    repo_full_name = f"{repo_owner}/{repo_name}"

    if repo_full_name not in RELATIONSHIPS_CONFIG['relationships']:
        raise HTTPException(status_code=404, detail="Repository not found in relationships")

    return RELATIONSHIPS_CONFIG['relationships'][repo_full_name]


@app.post("/api/webhook/change-notification")
async def handle_change_notification(event: ChangeEvent, background_tasks: BackgroundTasks):
    """
    Handle incoming change notifications from repositories.
    This is called by GitHub Actions after pattern analysis.
    """
    logger.info(f"Received change notification from {event.source_repo}")

    # Check if this repo has any relationships
    if event.source_repo not in RELATIONSHIPS_CONFIG['relationships']:
        logger.info(f"No relationships configured for {event.source_repo}")
        return {"status": "no_relationships", "message": "No dependent repositories configured"}

    repo_config = RELATIONSHIPS_CONFIG['relationships'][event.source_repo]

    # Process consumers (API dependency relationships)
    consumer_tasks = []
    if 'consumers' in repo_config:
        for consumer in repo_config['consumers']:
            logger.info(f"Scheduling consumer triage for {consumer['repo']}")
            background_tasks.add_task(
                process_consumer_relationship,
                event,
                consumer,
                repo_config
            )
            consumer_tasks.append(consumer['repo'])

    # Process derivatives (template fork relationships)
    derivative_tasks = []
    if 'derivatives' in repo_config:
        for derivative in repo_config['derivatives']:
            logger.info(f"Scheduling template triage for {derivative['repo']}")
            background_tasks.add_task(
                process_template_relationship,
                event,
                derivative,
                repo_config
            )
            derivative_tasks.append(derivative['repo'])

    return {
        "status": "accepted",
        "source_repo": event.source_repo,
        "consumers_scheduled": consumer_tasks,
        "derivatives_scheduled": derivative_tasks,
        "total_dependents": len(consumer_tasks) + len(derivative_tasks)
    }


async def process_consumer_relationship(event: ChangeEvent, consumer_config: Dict, source_config: Dict):
    """Process API consumer dependency relationship"""
    try:
        logger.info(f"Processing consumer relationship: {event.source_repo} -> {consumer_config['repo']}")

        # Initialize consumer triage agent
        agent = ConsumerTriageAgent(
            anthropic_client=anthropic_client,
            github_client=github_client
        )

        # Run triage analysis
        result = await agent.analyze(
            source_repo=event.source_repo,
            consumer_repo=consumer_config['repo'],
            change_event=event.dict(),
            consumer_config=consumer_config
        )

        logger.info(f"Triage result for {consumer_config['repo']}: action_required={result['requires_action']}, urgency={result['urgency']}")

        # Take action based on result
        if result['requires_action']:
            await handle_triage_action(
                target_repo=consumer_config['repo'],
                result=result,
                relationship_type='consumer',
                source_repo=event.source_repo,
                event=event
            )

    except Exception as e:
        logger.error(f"Error processing consumer relationship: {e}", exc_info=True)


async def process_template_relationship(event: ChangeEvent, derivative_config: Dict, source_config: Dict):
    """Process template fork relationship"""
    try:
        logger.info(f"Processing template relationship: {event.source_repo} -> {derivative_config['repo']}")

        # Initialize template triage agent
        agent = TemplateTriageAgent(
            anthropic_client=anthropic_client,
            github_client=github_client
        )

        # Run triage analysis
        result = await agent.analyze(
            template_repo=event.source_repo,
            derivative_repo=derivative_config['repo'],
            change_event=event.dict(),
            derivative_config=derivative_config
        )

        logger.info(f"Triage result for {derivative_config['repo']}: action_required={result['requires_action']}, urgency={result['urgency']}")

        # Take action based on result
        if result['requires_action']:
            await handle_triage_action(
                target_repo=derivative_config['repo'],
                result=result,
                relationship_type='template',
                source_repo=event.source_repo,
                event=event
            )

    except Exception as e:
        logger.error(f"Error processing template relationship: {e}", exc_info=True)


async def handle_triage_action(
    target_repo: str,
    result: Dict,
    relationship_type: str,
    source_repo: str,
    event: ChangeEvent
):
    """
    Take action based on triage result (create issue, notify, etc.)
    """
    urgency = result['urgency']
    notification_settings = RELATIONSHIPS_CONFIG['notification_settings']['default_urgency_thresholds']

    action_config = notification_settings.get(urgency, notification_settings['medium'])

    # Determine action
    if action_config['action'] in ['create_issue_immediately', 'create_issue']:
        await create_github_issue(
            target_repo=target_repo,
            result=result,
            relationship_type=relationship_type,
            source_repo=source_repo,
            event=event,
            labels=action_config['labels']
        )

    # Send webhook notification if configured
    if action_config.get('notify_webhook'):
        await send_webhook_notification(
            target_repo=target_repo,
            result=result,
            source_repo=source_repo,
            urgency=urgency
        )


async def create_github_issue(
    target_repo: str,
    result: Dict,
    relationship_type: str,
    source_repo: str,
    event: ChangeEvent,
    labels: List[str]
):
    """Create a GitHub issue in the target repository"""
    try:
        repo = github_client.get_repo(target_repo)

        # Format issue title
        if relationship_type == 'consumer':
            title = f"⚠️ Dependency Update Required: {source_repo}"
        else:
            title = f"📋 Template Update Available: {source_repo}"

        # Format issue body
        body = f"""## Dependency Change Notification

**Source Repository**: {source_repo}
**Commit**: {event.commit_sha[:7]}
**Branch**: {event.branch}
**Urgency**: {result['urgency'].upper()}
**Confidence**: {result['confidence']:.0%}

### Impact Summary
{result['impact_summary']}

### Commit Message
```
{event.commit_message}
```

### Recommended Changes
{result['recommended_changes']}

### Affected Files in This Repository
{chr(10).join(f"- `{f}`" for f in result['affected_files']) if result['affected_files'] else "No specific files identified"}

### Reasoning
{result['reasoning']}

---
*This issue was automatically created by the Architecture KB Orchestrator*
*Commit: [{event.commit_sha[:7]}](https://github.com/{source_repo}/commit/{event.commit_sha})*
"""

        # Create the issue
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels
        )

        logger.info(f"Created issue #{issue.number} in {target_repo}")

    except Exception as e:
        logger.error(f"Error creating GitHub issue: {e}", exc_info=True)


async def send_webhook_notification(
    target_repo: str,
    result: Dict,
    source_repo: str,
    urgency: str
):
    """Send notification via Discord/Slack webhook"""
    webhook_url = os.environ.get('WEBHOOK_URL')
    if not webhook_url:
        logger.warning("No webhook URL configured")
        return

    try:
        import requests

        # Format for Discord
        urgency_emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '📋',
            'low': 'ℹ️'
        }

        notification = {
            "content": f"{urgency_emoji.get(urgency, '📌')} **Dependency Alert**",
            "embeds": [{
                "title": f"Action Required: {target_repo}",
                "description": result['impact_summary'],
                "color": 15158332 if urgency == 'critical' else 16776960,  # Red or yellow
                "fields": [
                    {
                        "name": "Source Repository",
                        "value": source_repo,
                        "inline": True
                    },
                    {
                        "name": "Urgency",
                        "value": urgency.upper(),
                        "inline": True
                    },
                    {
                        "name": "Confidence",
                        "value": f"{result['confidence']:.0%}",
                        "inline": True
                    }
                ],
                "timestamp": datetime.now().isoformat()
            }]
        }

        response = requests.post(webhook_url, json=notification)
        response.raise_for_status()
        logger.info(f"Webhook notification sent for {target_repo}")

    except Exception as e:
        logger.error(f"Error sending webhook notification: {e}", exc_info=True)


@app.post("/api/test/consumer-triage")
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
        github_client=github_client
    )

    result = await agent.analyze(
        source_repo=source_repo,
        consumer_repo=consumer_repo,
        change_event=test_changes,
        consumer_config=consumer_config
    )

    return result


@app.post("/api/test/template-triage")
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
        github_client=github_client
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
