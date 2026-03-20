"""Unit tests for agent run API endpoints."""

import pytest


@pytest.fixture
async def agent(client):
    org_resp = await client.post("/api/v1/organizations", json={
        "identifier": "run-org",
        "name": "Run Org",
    })
    org = org_resp.json()
    dom_resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "runs",
        "name": "Runs",
        "organization_id": org["id"],
    })
    domain = dom_resp.json()
    agent_resp = await client.post("/api/v1/agents", json={
        "name": "run-test-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    return agent_resp.json()


@pytest.mark.asyncio
async def test_create_agent_run(client, agent):
    resp = await client.post("/api/v1/agent-runs", json={"agent_id": agent["id"]})
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == agent["id"]
    assert data["state"] == "pending"


@pytest.mark.asyncio
async def test_list_agent_runs(client, agent):
    await client.post("/api/v1/agent-runs", json={"agent_id": agent["id"]})
    resp = await client.get("/api/v1/agent-runs", params={"agent_id": agent["id"]})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_agent_run(client, agent):
    create_resp = await client.post("/api/v1/agent-runs", json={"agent_id": agent["id"]})
    run_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/agent-runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["state"] == "pending"


@pytest.mark.asyncio
async def test_stop_agent_run(client, agent):
    create_resp = await client.post("/api/v1/agent-runs", json={"agent_id": agent["id"]})
    run_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/agent-runs/{run_id}/stop")
    assert resp.status_code == 200
    assert resp.json()["state"] == "failed"
    assert resp.json()["error_message"] == "Stopped by user"


@pytest.mark.asyncio
async def test_stop_finished_run(client, agent):
    create_resp = await client.post("/api/v1/agent-runs", json={"agent_id": agent["id"]})
    run_id = create_resp.json()["id"]
    # First stop it
    await client.post(f"/api/v1/agent-runs/{run_id}/stop")
    # Try stopping again (already in terminal state)
    resp = await client.post(f"/api/v1/agent-runs/{run_id}/stop")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_run_with_task(client, agent):
    task_resp = await client.post("/api/v1/tasks", json={
        "instruction": "Do something",
        "agent_id": agent["id"],
    })
    task_id = task_resp.json()["id"]

    resp = await client.post("/api/v1/agent-runs", json={
        "agent_id": agent["id"],
        "task_id": task_id,
    })
    assert resp.status_code == 201
    assert resp.json()["task_id"] == task_id
