"""Unit tests for organization API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_organization(client):
    resp = await client.post("/api/v1/organizations", json={
        "identifier": "acme",
        "name": "Acme Corp",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["identifier"] == "acme"
    assert data["name"] == "Acme Corp"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_organization_duplicate(client):
    await client.post("/api/v1/organizations", json={
        "identifier": "dup-org",
        "name": "Dup Org",
    })
    resp = await client.post("/api/v1/organizations", json={
        "identifier": "dup-org",
        "name": "Dup Org 2",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_organizations(client):
    await client.post("/api/v1/organizations", json={
        "identifier": "list-org",
        "name": "List Org",
    })
    resp = await client.get("/api/v1/organizations")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_organization(client):
    create_resp = await client.post("/api/v1/organizations", json={
        "identifier": "get-org",
        "name": "Get Org",
    })
    org_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["identifier"] == "get-org"


@pytest.mark.asyncio
async def test_get_organization_not_found(client):
    resp = await client.get("/api/v1/organizations/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_organization(client):
    create_resp = await client.post("/api/v1/organizations", json={
        "identifier": "upd-org",
        "name": "Original",
    })
    org_id = create_resp.json()["id"]

    resp = await client.put(f"/api/v1/organizations/{org_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_organization(client):
    create_resp = await client.post("/api/v1/organizations", json={
        "identifier": "del-org",
        "name": "Delete Org",
    })
    org_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/organizations/{org_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_organization_creates_default_domain(client):
    resp = await client.post("/api/v1/organizations", json={
        "identifier": "with-default",
        "name": "With Default",
    })
    org_id = resp.json()["id"]

    domains_resp = await client.get("/api/v1/domains", params={"organization_id": org_id})
    domains = domains_resp.json()
    assert len(domains) >= 1
    identifiers = [d["identifier"] for d in domains]
    assert "with-default-default" in identifiers
