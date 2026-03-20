"""Unit tests for group API endpoints."""

import pytest


@pytest.fixture
async def org(client):
    resp = await client.post("/api/v1/organizations", json={
        "identifier": "grp-org",
        "name": "Group Org",
    })
    return resp.json()


@pytest.mark.asyncio
async def test_create_group(client, org):
    resp = await client.post("/api/v1/groups", json={
        "name": "engineers",
        "organization_id": org["id"],
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "engineers"


@pytest.mark.asyncio
async def test_list_groups(client, org):
    await client.post("/api/v1/groups", json={
        "name": "list-group",
        "organization_id": org["id"],
    })
    resp = await client.get("/api/v1/groups", params={"organization_id": org["id"]})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_group(client, org):
    create_resp = await client.post("/api/v1/groups", json={
        "name": "get-group",
        "organization_id": org["id"],
    })
    group_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/groups/{group_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_group(client, org):
    create_resp = await client.post("/api/v1/groups", json={
        "name": "upd-group",
        "organization_id": org["id"],
    })
    group_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/groups/{group_id}", json={"name": "updated-group"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-group"


@pytest.mark.asyncio
async def test_delete_group(client, org):
    create_resp = await client.post("/api/v1/groups", json={
        "name": "del-group",
        "organization_id": org["id"],
    })
    group_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/groups/{group_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_add_member_to_group(client, org):
    group_resp = await client.post("/api/v1/groups", json={
        "name": "member-group",
        "organization_id": org["id"],
    })
    group_id = group_resp.json()["id"]

    user_resp = await client.post("/api/v1/users", json={
        "email": "member@example.com",
        "name": "Member",
    })
    user_id = user_resp.json()["id"]

    resp = await client.post(f"/api/v1/groups/{group_id}/members", json={"user_id": user_id})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_add_member_duplicate(client, org):
    group_resp = await client.post("/api/v1/groups", json={
        "name": "dup-member-group",
        "organization_id": org["id"],
    })
    group_id = group_resp.json()["id"]

    user_resp = await client.post("/api/v1/users", json={
        "email": "dupmember@example.com",
        "name": "Dup Member",
    })
    user_id = user_resp.json()["id"]

    await client.post(f"/api/v1/groups/{group_id}/members", json={"user_id": user_id})
    resp = await client.post(f"/api/v1/groups/{group_id}/members", json={"user_id": user_id})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_member_from_group(client, org):
    group_resp = await client.post("/api/v1/groups", json={
        "name": "rm-member-group",
        "organization_id": org["id"],
    })
    group_id = group_resp.json()["id"]

    user_resp = await client.post("/api/v1/users", json={
        "email": "rmmember@example.com",
        "name": "Remove Member",
    })
    user_id = user_resp.json()["id"]

    await client.post(f"/api/v1/groups/{group_id}/members", json={"user_id": user_id})
    resp = await client.delete(f"/api/v1/groups/{group_id}/members/{user_id}")
    assert resp.status_code == 204
