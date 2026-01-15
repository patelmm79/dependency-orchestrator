"""
Dev-Nexus A2A Client

This client integrates with dev-nexus via A2A protocol to:
- Query repository dependencies (get_deployment_info skill)
- Update relationships (update_dependency_info skill)
- Post lessons learned from triage analysis
- Retrieve cross-repo pattern insights

Authentication:
- Public skills (get_deployment_info): No authentication required
- Protected skills (update_dependency_info): Requires Google OAuth2 ID token (Workload Identity)
"""

import logging
import httpx
import os
import time
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)


class DevNexusClient:
    """Client for interacting with dev-nexus via A2A protocol"""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize dev-nexus A2A client

        Args:
            base_url: Base URL of dev-nexus service (e.g., https://dev-nexus-xxx.run.app)
                     If None, dev-nexus integration is disabled
        """
        self.base_url = base_url
        self.enabled = base_url is not None and base_url != ""
        self._workload_identity_token_cache = None
        self._token_cache_time = 0
        self._token_cache_duration = 3300  # 55 minutes (ID tokens valid for 1 hour)

        if self.enabled:
            logger.info(f"Dev-nexus A2A integration enabled: {base_url}")
        else:
            logger.info("Dev-nexus integration disabled (no URL configured)")

    async def _get_workload_identity_token(self) -> Optional[str]:
        """
        Get Google ID token for Cloud Run Workload Identity authentication.

        This token is used to authenticate to protected dev-nexus A2A skills.
        Cloud Run automatically provides this via Workload Identity.

        See: https://cloud.google.com/run/docs/securing/service-identity
        """
        if not self.enabled:
            return None

        try:
            # Check cache (valid for ~55 minutes)
            now = time.time()
            if self._workload_identity_token_cache and (now - self._token_cache_time) < self._token_cache_duration:
                return self._workload_identity_token_cache

            # Cloud Run provides metadata endpoint automatically
            # Can also use environment variable for explicit configuration
            token_url = os.getenv(
                "GOOGLE_IDENTITY_ENDPOINT",
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
            )

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    token_url,
                    headers={"Metadata-Flavor": "Google"},
                    params={"audience": self.base_url}
                )

                if response.status_code == 200:
                    token = response.text
                    self._workload_identity_token_cache = token
                    self._token_cache_time = now
                    logger.debug("Retrieved Workload Identity token")
                    return token
                else:
                    logger.warning(f"Failed to get Workload Identity token: HTTP {response.status_code}")
                    return None

        except Exception as e:
            logger.warning(f"Error getting Workload Identity token (running locally?): {e}")
            # This is expected when running locally without Workload Identity
            return None

    async def call_a2a_skill(
        self,
        skill_name: str,
        input_data: Dict,
        requires_auth: bool = False
    ) -> Optional[Dict]:
        """
        Execute an A2A skill on dev-nexus.

        Args:
            skill_name: Name of the A2A skill to execute
            input_data: Input data for the skill
            requires_auth: Whether the skill requires authentication

        Returns:
            Skill response data or None if failed
        """
        if not self.enabled:
            logger.warning("Dev-nexus not configured, skipping A2A skill call")
            return None

        try:
            headers = {"Content-Type": "application/json"}

            # Add authentication if required
            if requires_auth:
                token = await self._get_workload_identity_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                else:
                    logger.warning(f"Skipping authenticated skill '{skill_name}': no Workload Identity token available")
                    return None

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/a2a/execute",
                    json={
                        "skill_name": skill_name,
                        "input_data": input_data
                    },
                    headers=headers
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"A2A skill '{skill_name}' executed successfully")
                    return result.get("data", result)
                else:
                    logger.warning(
                        f"A2A skill '{skill_name}' failed: HTTP {response.status_code}\n{response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error calling A2A skill '{skill_name}': {e}")
            return None

    # ========================================================================
    # A2A Skills (via dev-nexus)
    # ========================================================================

    async def get_repository_dependencies(self, repo: str) -> Optional[Dict]:
        """
        Query dev-nexus for current repository dependencies.

        Uses the public 'get_deployment_info' A2A skill (no authentication required).
        Returns consumers, derivatives, and external dependencies with confidence scores.

        Args:
            repo: Repository name (e.g., "owner/repo")

        Returns:
            Dict with:
            - consumers: List of consuming repositories
            - derivatives: List of derivative repositories
            - external_dependencies: List of external packages
            Or None if failed
        """
        if not self.enabled:
            return None

        response = await self.call_a2a_skill(
            skill_name="get_deployment_info",
            input_data={
                "repository": repo,
                "include_lessons": True,
                "include_history": False
            },
            requires_auth=False  # Public skill
        )

        if response:
            return {
                "consumers": response.get("consumers", []),
                "derivatives": response.get("derivatives", []),
                "external_dependencies": response.get("external_dependencies", []),
                "metadata": response.get("metadata", {})
            }
        return None

    async def update_dependency_relationship(
        self,
        source_repo: str,
        target_repo: str,
        relationship_type: str,
        config: Dict
    ) -> Optional[Dict]:
        """
        Update dependency relationship in dev-nexus.

        Uses the protected 'update_dependency_info' A2A skill (requires Workload Identity).

        Args:
            source_repo: Source repository (provider)
            target_repo: Target repository (consumer/derivative)
            relationship_type: "api_consumer" or "template_fork"
            config: Relationship configuration dict

        Returns:
            Response from skill or None if failed
        """
        if not self.enabled:
            return None

        response = await self.call_a2a_skill(
            skill_name="update_dependency_info",
            input_data={
                "source_repo": source_repo,
                "target_repo": target_repo,
                "relationship_type": relationship_type,
                "metadata": {
                    "interface_files": config.get("interface_files", []),
                    "change_triggers": config.get("change_triggers", []),
                    "urgency_mapping": config.get("urgency_mapping", {}),
                    "shared_concerns": config.get("shared_concerns", []),
                    "divergent_concerns": config.get("divergent_concerns", []),
                    "sync_strategy": config.get("sync_strategy", "sync_on_conflict_free")
                }
            },
            requires_auth=True  # Protected skill
        )

        return response

    # ========================================================================
    # Legacy Methods (kept for backward compatibility)
    # ========================================================================

    async def get_deployment_patterns(self, repo: str) -> Optional[Dict]:
        """
        Query dev-nexus for deployment patterns of a repository.

        DEPRECATED: Use get_repository_dependencies() instead.
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
        Query dev-nexus for code patterns of a repository.

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
