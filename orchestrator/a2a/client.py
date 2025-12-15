"""
A2A Protocol Client

Client for communicating with other A2A-compliant agents.
"""
import logging
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)


class A2AClient:
    """
    Client for communicating with A2A-compliant agents.

    Supports skill execution, AgentCard discovery, and health checks.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize A2A client.

        Args:
            base_url: Base URL of the target agent
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.agent_card: Optional[Dict[str, Any]] = None
        self._session = requests.Session()

        if api_key:
            self._session.headers['X-API-Key'] = api_key

        logger.info(f"A2A client initialized for {base_url}")

    def discover_agent(self) -> Dict[str, Any]:
        """
        Discover agent capabilities by fetching AgentCard.

        Returns:
            AgentCard data

        Raises:
            requests.RequestException: If discovery fails
        """
        url = f"{self.base_url}/.well-known/agent.json"
        logger.info(f"Discovering agent at {url}")

        response = self._session.get(url, timeout=10)
        response.raise_for_status()

        self.agent_card = response.json()
        logger.info(f"Discovered agent: {self.agent_card.get('agent', {}).get('display_name')}")

        return self.agent_card

    def health_check(self) -> Dict[str, Any]:
        """
        Check agent health.

        Returns:
            Health status data

        Raises:
            requests.RequestException: If health check fails
        """
        if not self.agent_card:
            self.discover_agent()

        health_endpoint = self.agent_card.get('endpoints', {}).get('health', '/a2a/health')
        url = f"{self.base_url}{health_endpoint}"

        response = self._session.get(url, timeout=10)
        response.raise_for_status()

        return response.json()

    def list_skills(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        List available skills on the agent.

        Args:
            category: Optional category filter

        Returns:
            List of skills

        Raises:
            requests.RequestException: If request fails
        """
        if not self.agent_card:
            self.discover_agent()

        list_endpoint = self.agent_card.get('endpoints', {}).get('list_skills', '/a2a/skills')
        url = f"{self.base_url}{list_endpoint}"

        params = {'category': category} if category else {}
        response = self._session.get(url, params=params, timeout=10)
        response.raise_for_status()

        return response.json()

    def execute_skill(
        self,
        skill_name: str,
        input_data: Dict[str, Any],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Execute a skill on the remote agent.

        Args:
            skill_name: Name of the skill to execute
            input_data: Input data for the skill
            timeout: Request timeout in seconds

        Returns:
            Skill execution result

        Raises:
            requests.RequestException: If request fails
            ValueError: If skill execution fails
        """
        if not self.agent_card:
            self.discover_agent()

        execute_endpoint = self.agent_card.get('endpoints', {}).get('execute_skill', '/a2a/execute')
        url = f"{self.base_url}{execute_endpoint}"

        payload = {
            "skill_name": skill_name,
            "input_data": input_data
        }

        logger.info(f"Executing skill '{skill_name}' on {self.base_url}")

        response = self._session.post(url, json=payload, timeout=timeout)
        response.raise_for_status()

        result = response.json()

        if not result.get('success'):
            error = result.get('error', 'Unknown error')
            logger.error(f"Skill execution failed: {error}")
            raise ValueError(f"Skill execution failed: {error}")

        logger.info(f"Skill '{skill_name}' executed successfully")
        return result.get('data', {})


class DevNexusA2AClient(A2AClient):
    """
    Specialized A2A client for dev-nexus agent.

    Provides convenience methods for dev-nexus-specific skills.
    """

    def query_architecture(self, repo: str, query: str) -> Dict[str, Any]:
        """
        Query architecture knowledge for a repository.

        Args:
            repo: Repository name
            query: Query string

        Returns:
            Architecture query results
        """
        return self.execute_skill(
            skill_name="query_architecture",
            input_data={
                "repo": repo,
                "query": query
            }
        )

    def post_lesson_learned(
        self,
        repo: str,
        lesson: str,
        source_commit: Optional[str] = None,
        confidence: float = 0.8,
        category: str = "general"
    ) -> Dict[str, Any]:
        """
        Post a lesson learned to dev-nexus.

        Args:
            repo: Repository name
            lesson: Lesson learned text
            source_commit: Optional commit SHA
            confidence: Confidence score (0.0-1.0)
            category: Lesson category

        Returns:
            Lesson post result
        """
        return self.execute_skill(
            skill_name="post_lesson",
            input_data={
                "repo": repo,
                "lesson": lesson,
                "source_commit": source_commit,
                "confidence": confidence,
                "category": category
            }
        )
