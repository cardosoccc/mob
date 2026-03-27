"""Tests for send_message mode-based routing (local vs dev)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mob.services.sessions import (
    _get_free_port,
    _send_via_port_forward,
)


def test_get_free_port_returns_int():
    port = _get_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535


def test_get_free_port_returns_different_ports():
    ports = {_get_free_port() for _ in range(5)}
    # At least some should differ (extremely unlikely all same)
    assert len(ports) >= 2


@pytest.mark.asyncio
async def test_send_via_port_forward_success():
    """Port-forward subprocess is started, message sent through tunnel, process cleaned up."""
    mock_proc = AsyncMock()
    mock_proc.returncode = None  # process still running after sleep
    mock_proc.terminate = MagicMock()
    mock_proc.wait = AsyncMock()
    mock_proc.stderr = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"reply": "hello back"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("mob.services.sessions.get_settings") as mock_settings,
        patch("mob.services.sessions._get_free_port", return_value=12345),
        patch("mob.services.sessions._get_http_client", return_value=mock_client),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_settings.return_value.kubernetes_namespace = "mob"

        result = await _send_via_port_forward("test-pod", "hello", {})

    assert result == {"reply": "hello back"}
    mock_client.post.assert_called_once_with(
        "http://127.0.0.1:12345/message",
        json={"message": "hello"},
        headers={},
    )
    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()


@pytest.mark.asyncio
async def test_send_via_port_forward_process_fails():
    """Port-forward exits immediately — raises ServiceError."""
    from mob.services import ServiceError

    mock_proc = AsyncMock()
    mock_proc.returncode = 1  # process exited
    mock_stderr = AsyncMock()
    mock_stderr.read = AsyncMock(return_value=b"error: pod not found")
    mock_proc.stderr = mock_stderr
    mock_proc.terminate = MagicMock()
    mock_proc.wait = AsyncMock()

    with (
        patch("mob.services.sessions.get_settings") as mock_settings,
        patch("mob.services.sessions._get_free_port", return_value=12345),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_settings.return_value.kubernetes_namespace = "mob"

        with pytest.raises(ServiceError, match="Port-forward failed"):
            await _send_via_port_forward("test-pod", "hello", {})

    mock_proc.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_send_via_port_forward_agent_busy():
    """Agent returns 409 — raises ServiceError with busy message."""
    from mob.services import ServiceError

    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.terminate = MagicMock()
    mock_proc.wait = AsyncMock()
    mock_proc.stderr = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 409
    mock_response.json.return_value = {"error": "Agent is busy"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch("mob.services.sessions.get_settings") as mock_settings,
        patch("mob.services.sessions._get_free_port", return_value=12345),
        patch("mob.services.sessions._get_http_client", return_value=mock_client),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_settings.return_value.kubernetes_namespace = "mob"

        with pytest.raises(ServiceError, match="Agent is busy"):
            await _send_via_port_forward("test-pod", "hello", {})
