"""
Dev-Nexus Knowledge Base Client

This client integrates with dev-nexus to:
- Query deployment patterns and architecture context
- Post lessons learned from triage analysis
- Retrieve cross-repo pattern insights
"""

import logging
import httpx
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)


class DevNexusClient:
    """Client for interacting with dev-nexus knowledge base"""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize dev-nexus client

        Args:
            base_url: Base URL of dev-nexus service (e.g., https://dev-nexus-xxx.run.app)
                     If None, dev-nexus integration is disabled
        """
        self.base_url = base_url
        self.enabled = base_url is not None and base_url != ""

        if self.enabled:
            logger.info(f"Dev-nexus integration enabled: {base_url}")
        else:
            logger.info("Dev-nexus integration disabled (no URL configured)")

    async def get_deployment_patterns(self, repo: str) -> Optional[Dict]:
        """
        Query dev-nexus for deployment patterns of a repository

        Args:
            repo: Repository name (e.g., "patelmm79/vllm-container-ngc")

        Returns:
            Dict with deployment patterns or None if unavailable
        """
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/kb/deployment/{repo}"
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Retrieved deployment patterns for {repo}")
                    return data
                elif response.status_code == 404:
                    logger.info(f"No deployment patterns found for {repo}")
                    return None
                else:
                    logger.warning(
                        f"Failed to get deployment patterns for {repo}: "
                        f"HTTP {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error querying dev-nexus for deployment patterns: {e}")
            return None

    async def get_patterns(self, repo: str) -> Optional[Dict]:
        """
        Query dev-nexus for code patterns of a repository

        Args:
            repo: Repository name

        Returns:
            Dict with code patterns or None if unavailable
        """
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/kb/patterns/{repo}"
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Retrieved patterns for {repo}")
                    return data
                elif response.status_code == 404:
                    logger.info(f"No patterns found for {repo}")
                    return None
                else:
                    logger.warning(
                        f"Failed to get patterns for {repo}: "
                        f"HTTP {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error querying dev-nexus for patterns: {e}")
            return None

    async def get_cross_repo_patterns(self, pattern_type: str) -> Optional[Dict]:
        """
        Query dev-nexus for similar patterns across repositories

        Args:
            pattern_type: Type of pattern (e.g., "gcp_deployment", "api_client")

        Returns:
            Dict with cross-repo pattern data or None if unavailable
        """
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/kb/cross-repo-patterns/{pattern_type}"
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Retrieved cross-repo patterns for {pattern_type}")
                    return data
                elif response.status_code == 404:
                    logger.info(f"No cross-repo patterns found for {pattern_type}")
                    return None
                else:
                    logger.warning(
                        f"Failed to get cross-repo patterns: "
                        f"HTTP {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error querying dev-nexus for cross-repo patterns: {e}")
            return None

    async def post_lesson_learned(
        self,
        repo: str,
        lesson: str,
        source_commit: Optional[str] = None,
        confidence: float = 0.8,
        category: str = "triage_analysis"
    ) -> bool:
        """
        Post a lesson learned to dev-nexus knowledge base

        Args:
            repo: Repository the lesson applies to
            lesson: Description of the lesson learned
            source_commit: Commit SHA that triggered this lesson (optional)
            confidence: Confidence score (0.0-1.0)
            category: Category of lesson (e.g., "triage_analysis", "deployment")

        Returns:
            True if posted successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            payload = {
                "repo": repo,
                "lesson": lesson,
                "source_commit": source_commit,
                "confidence": confidence,
                "category": category
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/kb/lessons-learned",
                    json=payload
                )

                if response.status_code in [200, 201]:
                    logger.info(f"Posted lesson learned for {repo}")
                    return True
                else:
                    logger.warning(
                        f"Failed to post lesson learned: "
                        f"HTTP {response.status_code}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error posting lesson learned to dev-nexus: {e}")
            return False

    async def get_architecture_context(self, repo: str) -> Optional[str]:
        """
        Get a formatted architecture context string for a repository

        This combines deployment patterns, lessons learned, and other context
        into a human-readable string suitable for inclusion in LLM prompts.

        Args:
            repo: Repository name

        Returns:
            Formatted context string or None if unavailable
        """
        if not self.enabled:
            return None

        try:
            # Get deployment patterns
            deployment = await self.get_deployment_patterns(repo)

            if not deployment:
                return None

            context_parts = []

            # Add deployment platform info
            if deployment.get('platform'):
                context_parts.append(
                    f"**Platform**: {deployment['platform']}"
                )

            # Add lessons learned
            if deployment.get('lessons_learned'):
                lessons = deployment['lessons_learned']
                if isinstance(lessons, list) and len(lessons) > 0:
                    recent_lessons = lessons[-3:]  # Last 3 lessons
                    lessons_text = "\n".join([
                        f"- {l.get('lesson', l)}"
                        for l in recent_lessons
                    ])
                    context_parts.append(
                        f"**Recent Lessons Learned**:\n{lessons_text}"
                    )

            # Add reusable components info
            if deployment.get('reusable_components'):
                components = deployment['reusable_components']
                if isinstance(components, list) and len(components) > 0:
                    context_parts.append(
                        f"**Reusable Components**: {len(components)} identified"
                    )

            if context_parts:
                return "\n\n".join(context_parts)
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting architecture context: {e}")
            return None
