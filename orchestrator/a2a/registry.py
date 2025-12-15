"""
Skills registry for A2A protocol
"""
import logging
from typing import Dict, List, Optional
from orchestrator.a2a.base import BaseSkill, SkillMetadata, SkillCategory

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Central registry for all A2A skills.

    Skills are registered at startup and can be queried by name or category.
    """

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._metadata_cache: Dict[str, SkillMetadata] = {}

    def register(self, skill: BaseSkill) -> None:
        """
        Register a new skill.

        Args:
            skill: Skill instance to register
        """
        metadata = skill.get_metadata()
        skill_name = metadata.name

        if skill_name in self._skills:
            logger.warning(f"Skill '{skill_name}' already registered, overwriting")

        self._skills[skill_name] = skill
        self._metadata_cache[skill_name] = metadata
        logger.info(f"Registered skill: {skill_name} ({metadata.category})")

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill instance or None if not found
        """
        return self._skills.get(name)

    def get_metadata(self, name: str) -> Optional[SkillMetadata]:
        """
        Get skill metadata by name.

        Args:
            name: Skill name

        Returns:
            Skill metadata or None if not found
        """
        return self._metadata_cache.get(name)

    def list_skills(self, category: Optional[SkillCategory] = None) -> List[SkillMetadata]:
        """
        List all registered skills, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of skill metadata
        """
        if category:
            return [
                metadata for metadata in self._metadata_cache.values()
                if metadata.category == category
            ]
        return list(self._metadata_cache.values())

    def get_all_metadata(self) -> Dict[str, SkillMetadata]:
        """
        Get all skill metadata as a dictionary.

        Returns:
            Dictionary mapping skill names to metadata
        """
        return self._metadata_cache.copy()

    def skill_exists(self, name: str) -> bool:
        """
        Check if a skill is registered.

        Args:
            name: Skill name

        Returns:
            True if skill exists
        """
        return name in self._skills


# Global registry instance
_global_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get the global skills registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def register_skill(skill: BaseSkill) -> None:
    """Register a skill in the global registry"""
    get_registry().register(skill)
