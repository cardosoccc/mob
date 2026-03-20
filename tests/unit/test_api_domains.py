"""Unit tests for domain API endpoints."""

import pytest


@pytest.fixture
async def org(client):
    resp = await client.post("/api/v1/organizations", json={
        "identifier": "dom-org",
        "name": "Domain Org",
    })
    return resp.json()


@pytest.mark.asyncio
async def test_create_domain(client, org):
    resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "engineering",
        "name": "Engineering",
        "organization_id": org["id"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["identifier"] == "dom-org-engineering"
    assert data["name"] == "Engineering"


@pytest.mark.asyncio
async def test_create_domain_duplicate(client, org):
    await client.post("/api/v1/domains", json={
        "identifier_suffix": "dup-dom",
        "name": "Dup",
        "organization_id": org["id"],
    })
    resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "dup-dom",
        "name": "Dup 2",
        "organization_id": org["id"],
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_domains(client, org):
    resp = await client.get("/api/v1/domains", params={"organization_id": org["id"]})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_domain(client, org):
    create_resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "get-dom",
        "name": "Get Domain",
        "organization_id": org["id"],
    })
    domain_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/domains/{domain_id}")
    assert resp.status_code == 200
    assert resp.json()["identifier"] == "dom-org-get-dom"


@pytest.mark.asyncio
async def test_update_domain(client, org):
    create_resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "upd-dom",
        "name": "Original",
        "organization_id": org["id"],
    })
    domain_id = create_resp.json()["id"]

    resp = await client.put(f"/api/v1/domains/{domain_id}", json={"name": "Updated Domain"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Domain"


@pytest.mark.asyncio
async def test_delete_domain(client, org):
    create_resp = await client.post("/api/v1/domains", json={
        "identifier_suffix": "del-dom",
        "name": "Delete Domain",
        "organization_id": org["id"],
    })
    domain_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/domains/{domain_id}")
    assert resp.status_code == 204
