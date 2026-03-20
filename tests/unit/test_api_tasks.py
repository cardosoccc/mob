"""Unit tests for task API endpoints."""

import pytest


@pytest.fixture
async def agent(client):
    org_resp = await client.post("/api/v1/organizations", json={
        "identifier": "task-org",
        "name": "Task Org",
    })
    org = org_resp.json()
    dom_resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "tasks",
        "name": "Tasks",
        "organization_id": org["id"],
    })
    domain = dom_resp.json()
    agent_resp = await client.post("/api/v1/agents", json={
        "name": "task-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    return agent_resp.json()


@pytest.mark.asyncio
async def test_create_task(client, agent):
    resp = await client.post("/api/v1/tasks", json={
        "instruction": "Write hello world",
        "definition_of_done": "Output says Hello World",
        "agent_id": agent["id"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["instruction"] == "Write hello world"
    assert data["definition_of_done"] == "Output says Hello World"


@pytest.mark.asyncio
async def test_list_tasks(client, agent):
    await client.post("/api/v1/tasks", json={
        "instruction": "List task",
        "agent_id": agent["id"],
    })
    resp = await client.get("/api/v1/tasks", params={"agent_id": agent["id"]})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_task(client, agent):
    create_resp = await client.post("/api/v1/tasks", json={
        "instruction": "Get task",
        "agent_id": agent["id"],
    })
    task_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["instruction"] == "Get task"
