"""MOB adapter for OpenClaw agent runtime.

Exposes the standard MOB agent contract (GET /health, POST /message on :8081)
and translates to/from OpenClaw's SDK interface.
"""

import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mob.agent.openclaw")

_state: str = "starting"
_lock = asyncio.Lock()

SESSION_ID = os.environ.get("SESSION_ID", "unknown")
AGENT_NAME = os.environ.get("AGENT_NAME", "unnamed")
SYSTEM_PROMPT = os.environ.get("AGENT_SYSTEM_PROMPT", "You are a helpful assistant.")
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT", "anthropic:claude-sonnet-4-6-20260320")


def _patch_annotation(state: str) -> None:
    """Patch pod annotation for state reporting."""
    try:
        from k8s import patch_own_annotation
        patch_own_annotation(state)
    except Exception:
        logger.debug("Could not patch annotation (not in K8s?)")


class MessageRequest(BaseModel):
    message: str = Field(..., max_length=32000)


class MessageResponse(BaseModel):
    response: str
    state: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _state
    _state = "idle"
    _patch_annotation("idle")
    logger.info("OpenClaw adapter for %s (%s) ready", AGENT_NAME, SESSION_ID)
    yield
    _state = "finished"
    _patch_annotation("finished")


app = FastAPI(title=f"MOB OpenClaw Adapter: {AGENT_NAME}", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "state": _state}


@app.post("/message", response_model=MessageResponse)
async def message(req: MessageRequest):
    global _state

    async with _lock:
        if _state != "idle":
            return JSONResponse(
                status_code=409,
                content={"error": f"Agent is not ready (state: {_state})", "state": _state},
            )
        _state = "busy"
        _patch_annotation("busy")

    try:
        # Call OpenClaw via subprocess
        result = await asyncio.to_thread(
            subprocess.run,
            ["openclaw", "--print", "--model", MODEL_ENDPOINT, "--system-prompt", SYSTEM_PROMPT, req.message],
            capture_output=True,
            text=True,
            timeout=120,
        )
        response_text = result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
        _state = "idle"
        _patch_annotation("idle")
        return MessageResponse(response=response_text, state=_state)
    except subprocess.TimeoutExpired:
        _state = "idle"
        _patch_annotation("idle")
        return JSONResponse(status_code=504, content={"error": "OpenClaw call timed out", "state": _state})
    except Exception:
        logger.exception("OpenClaw call failed")
        _state = "idle"
        _patch_annotation("idle")
        return JSONResponse(status_code=502, content={"error": "Internal error", "state": _state})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
