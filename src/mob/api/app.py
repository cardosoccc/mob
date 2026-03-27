"""FastAPI application setup."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mob.api.routes import (
    agents,
    domains,
    groups,
    organizations,
    sessions,
    skills,
    tasks,
    users,
)
from mob.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="mob",
        description="AI Agent Orchestration Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["organizations"])
    app.include_router(domains.router, prefix="/api/v1/domains", tags=["domains"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(groups.router, prefix="/api/v1/groups", tags=["groups"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
