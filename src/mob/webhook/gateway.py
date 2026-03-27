"""Webhook gateway - routes inbound platform messages to agent pods.

Runs as a separate service on port 8082. Receives webhooks from WhatsApp and
Telegram, translates platform-specific formats to MOB's message format, and
forwards to the appropriate agent pod.
"""

import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mob.webhook")

AGENT_HTTP_PORT = 8081
_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Webhook gateway started")
    yield
    await _http_client.aclose()
    logger.info("Webhook gateway stopped")


app = FastAPI(title="MOB Webhook Gateway", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "webhook-gateway"}


# ─── Pod resolution ─────────────────────────────────────────────

async def _get_pod_ip(session_id: str) -> str:
    """Look up agent pod IP for a session via K8s API."""
    try:
        from kubernetes import client as k8s_client, config as k8s_config
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()

        v1 = k8s_client.CoreV1Api()
        namespace = os.environ.get("MOB_KUBERNETES_NAMESPACE", "mob")
        cr_name = f"s-{session_id[:8]}"
        pod_name = f"mob-agent-{cr_name}"

        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        pod_ip = pod.status.pod_ip
        if not pod_ip:
            raise HTTPException(502, f"Pod {pod_name} has no IP assigned")
        return pod_ip
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve pod for session {session_id}: {e}")
        raise HTTPException(502, f"Cannot resolve agent pod: {e}")


async def _forward_to_agent(session_id: str, message: str) -> str:
    """Forward a message to the agent pod and return its response."""
    pod_ip = await _get_pod_ip(session_id)
    url = f"http://{pod_ip}:{AGENT_HTTP_PORT}/message"

    try:
        resp = await _http_client.post(url, json={"message": message})
        resp.raise_for_status()
        return resp.json().get("response", "")
    except httpx.TimeoutException:
        raise HTTPException(504, "Agent pod timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Agent error: {e.response.text}")
    except Exception as e:
        raise HTTPException(502, f"Failed to reach agent: {e}")


# ─── Telegram ───────────────────────────────────────────────────

@app.post("/webhooks/telegram/{session_id}")
async def telegram_webhook(
    session_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Handle inbound Telegram webhook updates."""
    # Verify secret token if configured
    expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(403, "Invalid secret token")

    body = await request.json()
    logger.info(f"Telegram webhook for session {session_id}: {json.dumps(body)[:200]}")

    # Extract message text from Telegram update
    message_obj = body.get("message") or body.get("edited_message") or {}
    text = message_obj.get("text", "")
    if not text:
        # Non-text messages (photos, stickers, etc.) — acknowledge but skip
        return {"ok": True}

    chat_id = message_obj.get("chat", {}).get("id")
    from_user = message_obj.get("from", {}).get("first_name", "User")

    try:
        agent_response = await _forward_to_agent(session_id, text)
    except HTTPException:
        # Respond 200 to Telegram to prevent retries, log the error
        logger.error(f"Failed to forward message to agent for session {session_id}")
        return {"ok": True}

    # Send reply back to Telegram
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if bot_token and chat_id:
        try:
            await _http_client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": agent_response},
            )
        except Exception:
            logger.exception("Failed to send Telegram reply")

    return {"ok": True}


# ─── WhatsApp ───────────────────────────────────────────────────

@app.get("/webhooks/whatsapp/{session_id}")
async def whatsapp_verify(
    session_id: str,
    request: Request,
):
    """Handle WhatsApp webhook verification (GET request from Meta)."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")

    if mode == "subscribe" and token == verify_token:
        logger.info(f"WhatsApp webhook verified for session {session_id}")
        return PlainTextResponse(content=challenge)

    raise HTTPException(403, "Verification failed")


@app.post("/webhooks/whatsapp/{session_id}")
async def whatsapp_webhook(
    session_id: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
):
    """Handle inbound WhatsApp webhook notifications."""
    body_bytes = await request.body()

    # Verify signature if app secret is configured
    app_secret = os.environ.get("WHATSAPP_APP_SECRET")
    if app_secret:
        if not x_hub_signature_256:
            raise HTTPException(403, "Missing signature")
        expected = "sha256=" + hmac.new(
            app_secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(403, "Invalid signature")

    body = json.loads(body_bytes)
    logger.info(f"WhatsApp webhook for session {session_id}: {json.dumps(body)[:200]}")

    # Extract messages from WhatsApp Cloud API format
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                if msg.get("type") != "text":
                    continue

                text = msg.get("text", {}).get("body", "")
                from_number = msg.get("from", "")

                if not text:
                    continue

                try:
                    agent_response = await _forward_to_agent(session_id, text)
                except HTTPException:
                    logger.error(f"Failed to forward WhatsApp message to agent for session {session_id}")
                    continue

                # Send reply back via WhatsApp Cloud API
                phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
                access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
                if phone_number_id and access_token:
                    try:
                        await _http_client.post(
                            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
                            headers={"Authorization": f"Bearer {access_token}"},
                            json={
                                "messaging_product": "whatsapp",
                                "to": from_number,
                                "type": "text",
                                "text": {"body": agent_response},
                            },
                        )
                    except Exception:
                        logger.exception("Failed to send WhatsApp reply")

    # Always return 200 to prevent Meta from retrying
    return {"status": "ok"}


def main():
    port = int(os.environ.get("WEBHOOK_PORT", "8082"))
    logger.info("Starting webhook gateway on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
