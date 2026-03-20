"""Unit tests for agent API endpoints."""

import pytest


@pytest.fixture
async def domain(client):
    org_resp = await client.post("/api/v1/organizations", json={
        "identifier": "agent-org",
        "name": "Agent Org",
    })
    org = org_resp.json()
    dom_resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "agents",
        "name": "Agents",
        "organization_id": org["id"],
    })
    return dom_resp.json()


@pytest.mark.asyncio
async def test_create_agent(client, domain):
    resp = await client.post("/api/v1/agents", json={
        "name": "my-agent",
        "agent_template": "ghcr.io/my/agent:v1",
        "domain_id": domain["id"],
        "system_prompt": "You are a helpful assistant.",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-agent"
    assert data["agent_template"] == "ghcr.io/my/agent:v1"
    assert data["system_prompt"] == "You are a helpful assistant."


@pytest.mark.asyncio
async def test_list_agents(client, domain):
    await client.post("/api/v1/agents", json={
        "name": "list-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    resp = await client.get("/api/v1/agents", params={"domain_id": domain["id"]})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_agent(client, domain):
    create_resp = await client.post("/api/v1/agents", json={
        "name": "get-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    agent_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-agent"


@pytest.mark.asyncio
async def test_update_agent(client, domain):
    create_resp = await client.post("/api/v1/agents", json={
        "name": "upd-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    agent_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/agents/{agent_id}", json={
        "name": "updated-agent",
        "system_prompt": "New prompt",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-agent"


@pytest.mark.asyncio
async def test_delete_agent(client, domain):
    create_resp = await client.post("/api/v1/agents", json={
        "name": "del-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    agent_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_agent_with_skills(client, domain):
    skill_resp = await client.post("/api/v1/skills", json={
        "name": "code-gen",
        "description": "Generates code",
    })
    skill_id = skill_resp.json()["id"]

    resp = await client.post("/api/v1/agents", json={
        "name": "skilled-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
        "skill_ids": [skill_id],
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_send_message_to_agent(client, domain):
    agent_resp = await client.post("/api/v1/agents", json={
        "name": "msg-agent",
        "agent_template": "test:latest",
        "domain_id": domain["id"],
    })
    agent_id = agent_resp.json()["id"]

    run_resp = await client.post("/api/v1/agent-runs", json={"agent_id": agent_id})
    run_id = run_resp.json()["id"]

    resp = await client.post(f"/api/v1/agents/{agent_id}/send", json={
        "message": "Hello agent!",
        "run_id": run_id,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
