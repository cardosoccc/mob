"""Load and validate agent YAML definitions."""

import yaml
from pydantic import BaseModel, Field


class AgentYaml(BaseModel):
    """Schema for agent YAML definition files."""

    name: str = Field(..., min_length=1, max_length=255)
    agent_template: str = Field(..., min_length=1, max_length=500)
    domain: str  # identifier, resolved to UUID by CLI
    system_prompt: str | None = None
    model_endpoint: str | None = None
    skills: list[str] | None = None  # names, resolved to UUIDs by CLI
    env: dict[str, str] | None = None
    custom: dict[str, str] | None = None
    resource_cpu_limit: str | None = None
    resource_memory_limit: str | None = None


def load_agent_yaml(path: str) -> AgentYaml:
    """Parse and validate an agent YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping, got {type(data).__name__}")
    return AgentYaml(**data)
