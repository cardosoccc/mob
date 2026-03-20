"""Unit tests for user API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_user(client):
    resp = await client.post("/api/v1/users", json={
        "email": "alice@example.com",
        "name": "Alice",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client):
    await client.post("/api/v1/users", json={"email": "dup@example.com", "name": "Dup"})
    resp = await client.post("/api/v1/users", json={"email": "dup@example.com", "name": "Dup 2"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_users(client):
    await client.post("/api/v1/users", json={"email": "list@example.com", "name": "List User"})
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_user(client):
    create_resp = await client.post("/api/v1/users", json={
        "email": "get@example.com", "name": "Get User",
    })
    user_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "get@example.com"


@pytest.mark.asyncio
async def test_update_user(client):
    create_resp = await client.post("/api/v1/users", json={
        "email": "upd@example.com", "name": "Original",
    })
    user_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/users/{user_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_user(client):
    create_resp = await client.post("/api/v1/users", json={
        "email": "del@example.com", "name": "Delete User",
    })
    user_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/users/{user_id}")
    assert resp.status_code == 204
