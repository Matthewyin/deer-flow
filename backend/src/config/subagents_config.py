"""Configuration for subagents."""

from pydantic import BaseModel, Field


class SubagentsConfig(BaseModel):
    """Configuration for subagents feature."""

    enabled: bool = Field(default=True, description="Whether subagents are enabled")
