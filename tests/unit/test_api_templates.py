"""Unit tests for template API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_template(client):
    resp = await client.post("/api/v1/templates", json={
        "name": "test-pydantic",
        "image": "mob-agent-pydantic:latest",
        "runtime": "pydantic-ai",
        "description": "Base pydantic-ai agent",
        "capabilities": ["chat"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-pydantic"
    assert data["image"] == "mob-agent-pydantic:latest"
    assert data["runtime"] == "pydantic-ai"
    assert data["capabilities"] == ["chat"]


@pytest.mark.asyncio
async def test_create_template_duplicate(client):
    await client.post("/api/v1/templates", json={
        "name": "dup-template",
        "image": "img:latest",
        "runtime": "pydantic-ai",
    })
    resp = await client.post("/api/v1/templates", json={
        "name": "dup-template",
        "image": "img:latest",
        "runtime": "pydantic-ai",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_templates(client):
    await client.post("/api/v1/templates", json={
        "name": "list-tmpl",
        "image": "img:latest",
        "runtime": "pi",
    })
    resp = await client.get("/api/v1/templates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_template(client):
    create_resp = await client.post("/api/v1/templates", json={
        "name": "get-tmpl",
        "image": "img:latest",
        "runtime": "openclaw",
    })
    template_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/templates/{template_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-tmpl"


@pytest.mark.asyncio
async def test_update_template(client):
    create_resp = await client.post("/api/v1/templates", json={
        "name": "upd-tmpl",
        "image": "img:v1",
        "runtime": "pydantic-ai",
    })
    template_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/templates/{template_id}", json={
        "image": "img:v2",
        "capabilities": ["whatsapp", "telegram"],
    })
    assert resp.status_code == 200
    assert resp.json()["image"] == "img:v2"
    assert resp.json()["capabilities"] == ["whatsapp", "telegram"]


@pytest.mark.asyncio
async def test_delete_template(client):
    create_resp = await client.post("/api/v1/templates", json={
        "name": "del-tmpl",
        "image": "img:latest",
        "runtime": "pi",
    })
    template_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/templates/{template_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    resp = await client.get("/api/v1/templates/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_template_with_resource_limits(client):
    resp = await client.post("/api/v1/templates", json={
        "name": "resource-tmpl",
        "image": "img:latest",
        "runtime": "pi",
        "resource_cpu_limit": "2000m",
        "resource_memory_limit": "2Gi",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["resource_cpu_limit"] == "2000m"
    assert data["resource_memory_limit"] == "2Gi"
