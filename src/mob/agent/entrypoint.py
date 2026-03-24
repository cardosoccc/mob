"""Default pydantic-ai agent entrypoint for MOB.

Runs a FastAPI server on port 8081 that receives messages, processes them
with an LLM via pydantic-ai, and reports state via Kubernetes pod annotations.
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_ai import Agent

from mob.agent.k8s import patch_own_annotation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mob.agent")

# Agent state
_state: str = "starting"
_lock = asyncio.Lock()

# Environment configuration
AGENT_RUN_ID = os.environ.get("AGENT_RUN_ID", "unknown")
AGENT_NAME = os.environ.get("AGENT_NAME", "unnamed")
SYSTEM_PROMPT = os.environ.get("AGENT_SYSTEM_PROMPT", "You are a helpful AI assistant.")
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT", "openai:gpt-4o")


def _build_agent() -> Agent:
    """Build the pydantic-ai agent from environment configuration."""
    return Agent(
        MODEL_ENDPOINT,
        instructions=SYSTEM_PROMPT,
    )


ai_agent = _build_agent()


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    response: str
    state: str


class ErrorResponse(BaseModel):
    error: str
    state: str


class HealthResponse(BaseModel):
    status: str
    state: str
    agent_run_id: str
    agent_name: str


def _set_state(new_state: str) -> None:
    """Update internal state and patch pod annotation."""
    global _state
    _state = new_state
    try:
        patch_own_annotation(new_state)
    except Exception:
        logger.exception(f"Failed to patch annotation to {new_state}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Set agent to idle on startup, finished on shutdown."""
    _set_state("idle")
    logger.info(f"Agent {AGENT_NAME} ({AGENT_RUN_ID}) ready")
    yield
    # Graceful shutdown
    _set_state("finished")
    logger.info("Agent shutting down gracefully")


app = FastAPI(title=f"MOB Agent: {AGENT_NAME}", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        state=_state,
        agent_run_id=AGENT_RUN_ID,
        agent_name=AGENT_NAME,
    )


@app.post("/message", response_model=MessageResponse, responses={409: {"model": ErrorResponse}})
async def message(req: MessageRequest):
    global _state

    async with _lock:
        if _state == "busy":
            return ErrorResponse(
                error="Agent is busy processing another message",
                state=_state,
            )
        if _state not in ("idle",):
            return ErrorResponse(
                error=f"Agent is not ready (state: {_state})",
                state=_state,
            )
        _set_state("busy")

    try:
        result = await ai_agent.run(req.message)
        response_text = str(result.output)
        _set_state("idle")
        return MessageResponse(response=response_text, state=_state)
    except Exception as e:
        logger.exception("LLM call failed")
        _set_state("idle")
        return MessageResponse(response=f"Error processing message: {e}", state=_state)


def _handle_sigterm(*_args):
    """Handle SIGTERM for graceful shutdown."""
    logger.info("Received SIGTERM")
    _set_state("finished")
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, _handle_sigterm)
    logger.info(f"Starting agent {AGENT_NAME} (run: {AGENT_RUN_ID})")
    logger.info(f"Model: {MODEL_ENDPOINT}")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


if __name__ == "__main__":
    main()
