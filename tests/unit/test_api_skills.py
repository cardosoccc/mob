"""Unit tests for skill API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_skill(client):
    resp = await client.post("/api/v1/skills", json={
        "name": "code-review",
        "description": "Reviews code for quality",
        "skills_md": "# Code Review\nReview code for quality.",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "code-review"
    assert data["description"] == "Reviews code for quality"


@pytest.mark.asyncio
async def test_create_skill_duplicate(client):
    await client.post("/api/v1/skills", json={"name": "dup-skill"})
    resp = await client.post("/api/v1/skills", json={"name": "dup-skill"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_skills(client):
    await client.post("/api/v1/skills", json={"name": "list-skill"})
    resp = await client.get("/api/v1/skills")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_skill(client):
    create_resp = await client.post("/api/v1/skills", json={"name": "get-skill"})
    skill_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/skills/{skill_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-skill"


@pytest.mark.asyncio
async def test_update_skill(client):
    create_resp = await client.post("/api/v1/skills", json={"name": "upd-skill"})
    skill_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/skills/{skill_id}", json={
        "name": "updated-skill",
        "description": "Updated",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-skill"


@pytest.mark.asyncio
async def test_delete_skill(client):
    create_resp = await client.post("/api/v1/skills", json={"name": "del-skill"})
    skill_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/skills/{skill_id}")
    assert resp.status_code == 204
