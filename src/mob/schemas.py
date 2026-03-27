"""Pydantic schemas for API request/response."""

from datetime import datetime

import json

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Organization ───────────────────────────────────────────────

class OrganizationCreate(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    id: str
    identifier: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Domain ─────────────────────────────────────────────────────

class DomainCreate(BaseModel):
    identifier_suffix: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    name: str = Field(..., min_length=1, max_length=255)
    organization_id: str


class DomainUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class DomainResponse(BaseModel):
    id: str
    identifier: str
    name: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── User ───────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = Field(None, min_length=1, max_length=255)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    keycloak_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Group ──────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    organization_id: str


class GroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class GroupResponse(BaseModel):
    id: str
    name: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GroupMemberAdd(BaseModel):
    user_id: str


# ─── Template ────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    image: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    runtime: str = Field(..., min_length=1, max_length=50)
    capabilities: list[str] | None = None
    resource_cpu_limit: str | None = Field(None, max_length=20)
    resource_memory_limit: str | None = Field(None, max_length=20)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    image: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    runtime: str | None = Field(None, min_length=1, max_length=50)
    capabilities: list[str] | None = None
    resource_cpu_limit: str | None = Field(None, max_length=20)
    resource_memory_limit: str | None = Field(None, max_length=20)


class TemplateResponse(BaseModel):
    id: str
    name: str
    image: str
    description: str | None
    runtime: str
    capabilities: list[str] | None = None
    resource_cpu_limit: str | None
    resource_memory_limit: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("capabilities", mode="before")
    @classmethod
    def _parse_capabilities(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


# ─── Agent ──────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str | None = None
    agent_template: str = Field(..., min_length=1, max_length=500)
    model_endpoint: str | None = None
    domain_id: str
    skill_ids: list[str] = Field(default_factory=list)
    env_defaults: dict[str, str] | None = None
    custom_config: dict[str, str] | None = None


class AgentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    system_prompt: str | None = None
    agent_template: str | None = Field(None, min_length=1, max_length=500)
    model_endpoint: str | None = None
    skill_ids: list[str] | None = None
    env_defaults: dict[str, str] | None = None
    custom_config: dict[str, str] | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    system_prompt: str | None
    agent_template: str
    model_endpoint: str | None
    domain_id: str
    env_defaults: dict[str, str] | None = None
    custom_config: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("env_defaults", "custom_config", mode="before")
    @classmethod
    def _parse_json_str(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


# ─── Session ───────────────────────────────────────────────────

class SessionCreate(BaseModel):
    agent_id: str
    task_id: str | None = None
    name: str | None = Field(None, min_length=1, max_length=255, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    env_overrides: dict[str, str] | None = None


class SessionResponse(BaseModel):
    id: str
    name: str
    agent_id: str
    state: str
    pod_name: str | None
    task_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Task ───────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    instruction: str = Field(..., min_length=1)
    definition_of_done: str | None = None
    agent_id: str


class TaskResponse(BaseModel):
    id: str
    instruction: str
    definition_of_done: str | None
    agent_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Skill ──────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    description: str = Field(..., min_length=1, max_length=1024)
    skill_md: str | None = None
    license: str | None = Field(None, max_length=255)
    compatibility: str | None = Field(None, max_length=500)
    metadata_json: dict[str, str] | None = None
    allowed_tools: str | None = Field(None, max_length=500)


class SkillUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    description: str | None = Field(None, min_length=1, max_length=1024)
    skill_md: str | None = None
    license: str | None = Field(None, max_length=255)
    compatibility: str | None = Field(None, max_length=500)
    metadata_json: dict[str, str] | None = None
    allowed_tools: str | None = Field(None, max_length=500)


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str | None
    skill_md: str | None
    license: str | None
    compatibility: str | None
    metadata_json: dict[str, str] | None = None
    allowed_tools: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("metadata_json", mode="before")
    @classmethod
    def _parse_metadata(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


# ─── Session Send Message ──────────────────────────────────────

class SessionSendMessage(BaseModel):
    message: str = Field(..., min_length=1)
