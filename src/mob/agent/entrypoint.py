"""Default pydantic-ai agent entrypoint for MOB.

Runs a FastAPI server on port 8081 that receives messages, processes them
with an LLM via pydantic-ai, and reports state via Kubernetes pod annotations.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from mob.agent.k8s import patch_own_annotation_async

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mob.agent")

# Agent state
_state: str = "starting"
_lock = asyncio.Lock()

# Environment configuration
SESSION_ID = os.environ.get("SESSION_ID", "unknown")
AGENT_NAME = os.environ.get("AGENT_NAME", "unnamed")
SYSTEM_PROMPT = os.environ.get("AGENT_SYSTEM_PROMPT", "You are a helpful AI assistant.")
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT", "openai:gpt-4o")
AGENT_AUTH_TOKEN = os.environ.get("AGENT_AUTH_TOKEN", "")

# LLM call timeout in seconds
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "120"))

# Conversation history for multi-turn chat
_message_history: list | None = None

_ai_agent: Agent | None = None


def _get_agent() -> Agent:
    """Lazily build the pydantic-ai agent from environment configuration."""
    global _ai_agent
    if _ai_agent is None:
        _ai_agent = Agent(
            MODEL_ENDPOINT,
            instructions=SYSTEM_PROMPT,
        )
    return _ai_agent


class MessageRequest(BaseModel):
    message: str = Field(..., max_length=32000)


class MessageResponse(BaseModel):
    response: str
    state: str


def _verify_auth(authorization: str | None) -> None:
    """Verify bearer token if AGENT_AUTH_TOKEN is configured."""
    if not AGENT_AUTH_TOKEN:
        return
    if not authorization or authorization != f"Bearer {AGENT_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _set_state(new_state: str) -> None:
    """Update internal state and patch pod annotation (non-blocking)."""
    global _state
    _state = new_state
    try:
        await patch_own_annotation_async(new_state)
    except Exception:
        logger.exception("Failed to patch annotation to %s", new_state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Set agent to idle on startup, finished on shutdown."""
    await _set_state("idle")
    logger.info("Agent %s (%s) ready", AGENT_NAME, SESSION_ID)
    yield
    await _set_state("finished")
    logger.info("Agent shutting down gracefully")


app = FastAPI(title=f"MOB Agent: {AGENT_NAME}", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "state": _state}


@app.post("/message", response_model=MessageResponse)
async def message(req: MessageRequest, authorization: str | None = Header(default=None)):
    global _state, _message_history

    _verify_auth(authorization)

    async with _lock:
        if _state == "busy":
            return JSONResponse(
                status_code=409,
                content={"error": "Agent is busy processing another message", "state": _state},
            )
        if _state != "idle":
            return JSONResponse(
                status_code=409,
                content={"error": f"Agent is not ready (state: {_state})", "state": _state},
            )
        await _set_state("busy")

    try:
        result = await asyncio.wait_for(
            _get_agent().run(req.message, message_history=_message_history),
            timeout=LLM_TIMEOUT,
        )
        _message_history = result.all_messages()
        response_text = str(result.output)
        await _set_state("idle")
        return MessageResponse(response=response_text, state=_state)
    except asyncio.TimeoutError:
        logger.error("LLM call timed out after %ds", LLM_TIMEOUT)
        await _set_state("idle")
        return JSONResponse(
            status_code=504,
            content={"error": "LLM call timed out", "state": _state},
        )
    except Exception:
        logger.exception("LLM call failed")
        await _set_state("idle")
        return JSONResponse(
            status_code=502,
            content={"error": "Internal error processing message", "state": _state},
        )


def main():
    logger.info("Starting agent %s (run: %s)", AGENT_NAME, SESSION_ID)
    logger.info("Model: %s", MODEL_ENDPOINT)
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


if __name__ == "__main__":
    main()
