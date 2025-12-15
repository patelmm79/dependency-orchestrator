"""
Base classes for A2A skills
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    """A2A skill categories"""
    EVENT = "event"
    QUERY = "query"
    ACTION = "action"
    MANAGEMENT = "management"


class SkillMetadata(BaseModel):
    """Metadata for an A2A skill"""
    name: str = Field(..., description="Unique skill identifier")
    display_name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="What this skill does")
    category: SkillCategory = Field(..., description="Skill category")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for input")
    output_schema: Dict[str, Any] = Field(..., description="JSON schema for output")
    requires_auth: bool = Field(default=False, description="Whether skill requires authentication")
    is_async: bool = Field(default=False, description="Whether skill executes asynchronously")


class BaseSkill(ABC):
    """
    Abstract base class for all A2A skills.

    Each skill must implement:
    - get_metadata(): Return skill metadata
    - execute(): Perform the skill operation
    """

    @abstractmethod
    def get_metadata(self) -> SkillMetadata:
        """Return metadata describing this skill"""
        pass

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the skill with provided input.

        Args:
            input_data: Input matching the skill's input_schema

        Returns:
            Output matching the skill's output_schema
        """
        pass

    def validate_input(self, input_data: Dict[str, Any]) -> None:
        """
        Validate input against the skill's input schema.
        Override to add custom validation.
        """
        # TODO: Add JSON schema validation
        pass


class SkillExecutionResult(BaseModel):
    """Result of skill execution"""
    success: bool = Field(..., description="Whether execution succeeded")
    data: Optional[Dict[str, Any]] = Field(None, description="Result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    task_id: Optional[str] = Field(None, description="Task ID for async operations")
