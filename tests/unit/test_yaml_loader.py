"""Unit tests for YAML agent definition loader."""

import os
import tempfile

import pytest
from pydantic import ValidationError

from mob.cli.yaml_loader import AgentYaml, load_agent_yaml


def _write_yaml(content: str) -> str:
    """Write YAML content to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.write(fd, content.encode())
    os.close(fd)
    return path


def test_load_full_yaml():
    path = _write_yaml("""
name: assistant
agent_template: mob-agent-pydantic:latest
domain: dev
system_prompt: "You are helpful."
model_endpoint: "anthropic:claude-haiku-4-5-20251001"
skills:
  - code-review
  - testing
env:
  LLM_TIMEOUT: "120"
  ANTHROPIC_API_KEY: ""
custom:
  temperature: "0.7"
  max_tokens: "4096"
""")
    spec = load_agent_yaml(path)
    assert spec.name == "assistant"
    assert spec.agent_template == "mob-agent-pydantic:latest"
    assert spec.domain == "dev"
    assert spec.system_prompt == "You are helpful."
    assert spec.model_endpoint == "anthropic:claude-haiku-4-5-20251001"
    assert spec.skills == ["code-review", "testing"]
    assert spec.env == {"LLM_TIMEOUT": "120", "ANTHROPIC_API_KEY": ""}
    assert spec.custom == {"temperature": "0.7", "max_tokens": "4096"}
    os.unlink(path)


def test_load_minimal_yaml():
    path = _write_yaml("""
name: simple-agent
agent_template: python:3.11
domain: default
""")
    spec = load_agent_yaml(path)
    assert spec.name == "simple-agent"
    assert spec.agent_template == "python:3.11"
    assert spec.domain == "default"
    assert spec.system_prompt is None
    assert spec.model_endpoint is None
    assert spec.skills is None
    assert spec.env is None
    assert spec.custom is None
    os.unlink(path)


def test_load_yaml_missing_required_field():
    path = _write_yaml("""
agent_template: test:latest
domain: dev
""")
    with pytest.raises(ValidationError, match="name"):
        load_agent_yaml(path)
    os.unlink(path)


def test_load_yaml_missing_template():
    path = _write_yaml("""
name: test
domain: dev
""")
    with pytest.raises(ValidationError, match="agent_template"):
        load_agent_yaml(path)
    os.unlink(path)


def test_load_yaml_missing_domain():
    path = _write_yaml("""
name: test
agent_template: test:latest
""")
    with pytest.raises(ValidationError, match="domain"):
        load_agent_yaml(path)
    os.unlink(path)


def test_load_yaml_invalid_syntax():
    path = _write_yaml("{ invalid yaml [")
    with pytest.raises(Exception):
        load_agent_yaml(path)
    os.unlink(path)


def test_load_yaml_not_a_mapping():
    path = _write_yaml("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="Expected a YAML mapping"):
        load_agent_yaml(path)
    os.unlink(path)


def test_load_yaml_multiline_system_prompt():
    path = _write_yaml("""
name: researcher
agent_template: test:latest
domain: dev
system_prompt: |
  You are a research assistant.
  Be concise and cite sources.
  Always provide references.
""")
    spec = load_agent_yaml(path)
    assert "research assistant" in spec.system_prompt
    assert "cite sources" in spec.system_prompt
    os.unlink(path)


def test_agent_yaml_model_validation():
    """Test Pydantic model directly."""
    spec = AgentYaml(
        name="test",
        agent_template="img:latest",
        domain="dev",
        env={"KEY": "val"},
        custom={"temp": "0.5"},
    )
    assert spec.env == {"KEY": "val"}
    assert spec.custom == {"temp": "0.5"}
