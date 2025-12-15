"""
A2A Protocol Server

Exposes A2A-compliant endpoints for agent-to-agent communication.
"""
import os
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import secrets

from orchestrator.a2a.registry import get_registry
from orchestrator.a2a.base import SkillCategory

logger = logging.getLogger(__name__)


# API Key Authentication (required for mutation operations)
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
ORCHESTRATOR_API_KEY = os.environ.get('ORCHESTRATOR_API_KEY')
REQUIRE_AUTH = os.environ.get('REQUIRE_AUTH', 'false').lower() == 'true'


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


# Pydantic models for A2A protocol
class SkillExecutionRequest(BaseModel):
    """Request to execute a skill"""
    skill_name: str
    input_data: Dict[str, Any]


class SkillExecutionResponse(BaseModel):
    """Response from skill execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    task_id: Optional[str] = None


def create_a2a_app() -> FastAPI:
    """
    Create and configure the A2A FastAPI application.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Dependency Orchestrator A2A Agent",
        description="A2A-compliant agent for dependency orchestration and impact analysis",
        version="2.0.0"
    )

    registry = get_registry()

    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """
        Serve AgentCard for A2A protocol discovery.

        The AgentCard describes this agent's capabilities and available skills.
        """
        skills_metadata = registry.get_all_metadata()

        # Build skills list for AgentCard
        skills = []
        for skill_name, metadata in skills_metadata.items():
            skills.append({
                "name": metadata.name,
                "display_name": metadata.display_name,
                "description": metadata.description,
                "category": metadata.category.value,
                "input_schema": metadata.input_schema,
                "output_schema": metadata.output_schema,
                "requires_auth": metadata.requires_auth,
                "is_async": metadata.is_async
            })

        agent_card = {
            "agent": {
                "name": "dependency-orchestrator",
                "display_name": "Dependency Orchestrator",
                "description": "AI-powered dependency orchestration agent that coordinates impact analysis across repository relationships",
                "version": "2.0.0",
                "vendor": "patelmm79",
                "capabilities": [
                    "dependency_tracking",
                    "impact_analysis",
                    "consumer_triage",
                    "template_sync",
                    "async_orchestration"
                ]
            },
            "skills": skills,
            "endpoints": {
                "execute_skill": "/a2a/execute",
                "list_skills": "/a2a/skills",
                "health": "/a2a/health"
            },
            "authentication": {
                "required": REQUIRE_AUTH,
                "methods": ["api_key"],
                "header": "X-API-Key"
            }
        }

        return agent_card

    @app.get("/a2a/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "agent": "dependency-orchestrator",
            "version": "2.0.0",
            "skills_registered": len(registry.list_skills())
        }

    @app.get("/a2a/skills")
    async def list_skills(category: Optional[str] = None):
        """
        List available skills, optionally filtered by category.

        Args:
            category: Optional category filter (event, query, action, management)

        Returns:
            List of skill metadata
        """
        skill_category = None
        if category:
            try:
                skill_category = SkillCategory(category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

        skills = registry.list_skills(category=skill_category)
        return {
            "skills": [
                {
                    "name": skill.name,
                    "display_name": skill.display_name,
                    "description": skill.description,
                    "category": skill.category.value,
                    "requires_auth": skill.requires_auth,
                    "is_async": skill.is_async
                }
                for skill in skills
            ]
        }

    @app.post("/a2a/execute")
    async def execute_skill(
        request: SkillExecutionRequest,
        authenticated: bool = Depends(verify_api_key)
    ) -> SkillExecutionResponse:
        """
        Execute a skill with provided input.

        Args:
            request: Skill execution request
            authenticated: Authentication result (injected)

        Returns:
            Skill execution result
        """
        skill_name = request.skill_name
        input_data = request.input_data

        logger.info(f"Executing skill: {skill_name}")

        # Get skill from registry
        skill = registry.get_skill(skill_name)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

        # Check authentication requirement
        metadata = skill.get_metadata()
        if metadata.requires_auth and not authenticated:
            raise HTTPException(status_code=401, detail="This skill requires authentication")

        # Execute skill
        try:
            result = await skill.execute(input_data)

            # Check if result has task_id (async operation)
            task_id = result.get('task_id') if isinstance(result, dict) else None

            return SkillExecutionResponse(
                success=True,
                data=result,
                task_id=task_id
            )

        except Exception as e:
            logger.error(f"Error executing skill {skill_name}: {e}", exc_info=True)
            return SkillExecutionResponse(
                success=False,
                error=str(e)
            )

    return app


def register_all_skills():
    """
    Register all available skills with the registry.

    This should be called at startup.
    """
    from orchestrator.a2a.skills import (
        ReceiveChangeNotificationSkill,
        GetImpactAnalysisSkill,
        GetDependenciesSkill,
        GetOrchestrationStatusSkill,
        TriggerConsumerTriageSkill,
        TriggerTemplateTriageSkill,
        AddDependencyRelationshipSkill,
    )
    from orchestrator.a2a.registry import register_skill

    # Register all skills
    register_skill(ReceiveChangeNotificationSkill())
    register_skill(GetImpactAnalysisSkill())
    register_skill(GetDependenciesSkill())
    register_skill(GetOrchestrationStatusSkill())
    register_skill(TriggerConsumerTriageSkill())
    register_skill(TriggerTemplateTriageSkill())
    register_skill(AddDependencyRelationshipSkill())

    logger.info("All A2A skills registered")


# Create the app instance
register_all_skills()
app = create_a2a_app()
