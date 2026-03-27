"""Unit tests for webhook gateway."""

import pytest
from unittest.mock import patch, AsyncMock

import httpx
from httpx import ASGITransport


@pytest.fixture
async def gateway_client():
    from mob.webhook.gateway import app
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_gateway_health(gateway_client):
    resp = await gateway_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "webhook-gateway"


@pytest.mark.asyncio
async def test_whatsapp_verify(gateway_client):
    with patch.dict("os.environ", {"WHATSAPP_VERIFY_TOKEN": "test-token"}):
        resp = await gateway_client.get(
            "/webhooks/whatsapp/test-session-id",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-token",
                "hub.challenge": "challenge123",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "challenge123"


@pytest.mark.asyncio
async def test_whatsapp_verify_fails(gateway_client):
    with patch.dict("os.environ", {"WHATSAPP_VERIFY_TOKEN": "correct-token"}):
        resp = await gateway_client.get(
            "/webhooks/whatsapp/test-session-id",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge123",
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_no_text(gateway_client):
    """Non-text Telegram messages should be acknowledged but skipped."""
    resp = await gateway_client.post(
        "/webhooks/telegram/test-session-id",
        json={
            "update_id": 123,
            "message": {
                "message_id": 1,
                "chat": {"id": 456},
                "from": {"id": 789, "first_name": "Test"},
                "sticker": {"file_id": "sticker123"},
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
