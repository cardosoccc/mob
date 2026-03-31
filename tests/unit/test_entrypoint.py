"""Tests for agent entrypoint model routing."""

import os
from unittest.mock import patch

import pytest


class TestBuildModel:
    """Test _build_model() litellm: prefix routing."""

    def test_litellm_prefix_returns_openai_model(self):
        """litellm:model-name should create an OpenAIModel pointing at the proxy."""
        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://mob-litellm:4000/v1",
            "LITELLM_API_KEY": "sk-test-key",
        }):
            # Re-import to pick up patched env vars
            import importlib
            import mob.agent.entrypoint as ep
            importlib.reload(ep)

            result = ep._build_model("litellm:claude-sonnet")

            from pydantic_ai.models.openai import OpenAIChatModel
            assert isinstance(result, OpenAIChatModel)
            assert result.model_name == "claude-sonnet"

    def test_litellm_prefix_uses_configured_base_url(self):
        """litellm: prefix should use LITELLM_BASE_URL env var."""
        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://custom-proxy:9000/v1",
            "LITELLM_API_KEY": "sk-custom",
        }):
            import importlib
            import mob.agent.entrypoint as ep
            importlib.reload(ep)

            result = ep._build_model("litellm:gpt-4o")

            from pydantic_ai.models.openai import OpenAIChatModel
            assert isinstance(result, OpenAIChatModel)
            assert result.model_name == "gpt-4o"

    def test_non_litellm_prefix_passes_through(self):
        """Non-litellm endpoints should be returned as-is."""
        import mob.agent.entrypoint as ep

        result = ep._build_model("anthropic:claude-sonnet-4-20250514")
        assert result == "anthropic:claude-sonnet-4-20250514"

    def test_openai_prefix_passes_through(self):
        """openai: endpoints should be returned as-is."""
        import mob.agent.entrypoint as ep

        result = ep._build_model("openai:gpt-4o")
        assert result == "openai:gpt-4o"
