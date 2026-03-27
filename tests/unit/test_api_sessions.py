"""Unit tests for session API endpoints."""

from unittest.mock import patch

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
async def test_create_session(client, agent):
    resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == agent["id"]
    assert data["state"] == "pending"
    assert data["name"].startswith("run-test-agent-")
    assert len(data["name"]) == len("run-test-agent-") + 8


@pytest.mark.asyncio
async def test_create_session_with_name(client, agent):
    resp = await client.post("/api/v1/sessions", json={
        "agent_id": agent["id"],
        "name": "my-custom-run",
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "my-custom-run"


@pytest.mark.asyncio
async def test_create_session_duplicate_name(client, agent):
    await client.post("/api/v1/sessions", json={
        "agent_id": agent["id"],
        "name": "unique-run",
    })
    resp = await client.post("/api/v1/sessions", json={
        "agent_id": agent["id"],
        "name": "unique-run",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_sessions(client, agent):
    await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    resp = await client.get("/api/v1/sessions", params={"agent_id": agent["id"]})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_sessions_filter_by_state(client, agent):
    await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    # All new sessions are "pending"
    resp = await client.get("/api/v1/sessions", params={"state": "pending"})
    assert resp.status_code == 200
    assert all(r["state"] == "pending" for r in resp.json())

    resp = await client.get("/api/v1/sessions", params={"state": "idle"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_list_sessions_invalid_state(client, agent):
    resp = await client.get("/api/v1/sessions", params={"state": "bogus"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_to_session(client, agent):
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/sessions/{session_id}/send", json={"message": "hello"})
    # Without K8s, agent is not running — returns 409
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_session(client, agent):
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["state"] == "pending"


@pytest.mark.asyncio
async def test_stop_session(client, agent):
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/sessions/{session_id}/stop")
    assert resp.status_code == 200
    assert resp.json()["state"] == "failed"
    assert resp.json()["error_message"] == "Stopped by user"


@pytest.mark.asyncio
async def test_stop_finished_session(client, agent):
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]
    # First stop it
    await client.post(f"/api/v1/sessions/{session_id}/stop")
    # Try stopping again (already in terminal state)
    resp = await client.post(f"/api/v1/sessions/{session_id}/stop")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_session_with_task(client, agent):
    task_resp = await client.post("/api/v1/tasks", json={
        "instruction": "Do something",
        "agent_id": agent["id"],
    })
    task_id = task_resp.json()["id"]

    resp = await client.post("/api/v1/sessions", json={
        "agent_id": agent["id"],
        "task_id": task_id,
    })
    assert resp.status_code == 201
    assert resp.json()["task_id"] == task_id


# ─── State enrichment tests ───────────────────────────────────


def _make_cr_statuses(session_id, state="Idle", pod_name=None, error_message=None):
    """Build a mock CR statuses dict for a single session."""
    cr_name = f"s-{session_id[:8]}"
    status = {"state": state}
    if pod_name:
        status["podName"] = pod_name
    if error_message:
        status["errorMessage"] = error_message
    return {cr_name: status}


@pytest.mark.asyncio
async def test_list_enriches_state_from_k8s(client, agent):
    """List endpoint returns live CR state instead of stale DB state."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]
    cr_statuses = _make_cr_statuses(session_id, "Idle", pod_name="mob-agent-s-test")

    with patch("mob.services.sessions._list_cr_statuses_sync", return_value=cr_statuses):
        resp = await client.get("/api/v1/sessions")

    assert resp.status_code == 200
    sessions = resp.json()
    matched = [r for r in sessions if r["id"] == session_id]
    assert len(matched) == 1
    assert matched[0]["state"] == "idle"
    assert matched[0]["pod_name"] == "mob-agent-s-test"


@pytest.mark.asyncio
async def test_list_degrades_gracefully_without_k8s(client, agent):
    """When K8s is unavailable, list returns DB state unchanged."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    with patch("mob.services.sessions._list_cr_statuses_sync", return_value=None):
        resp = await client.get("/api/v1/sessions")

    assert resp.status_code == 200
    matched = [r for r in resp.json() if r["id"] == session_id]
    assert matched[0]["state"] == "pending"


@pytest.mark.asyncio
async def test_list_marks_orphaned_sessions_as_failed(client, agent):
    """Non-terminal sessions with no matching CR are marked as failed."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    # K8s available but no CRs exist
    with patch("mob.services.sessions._list_cr_statuses_sync", return_value={}):
        resp = await client.get("/api/v1/sessions")

    matched = [r for r in resp.json() if r["id"] == session_id]
    assert matched[0]["state"] == "failed"
    assert matched[0]["error_message"] == "CR not found"


@pytest.mark.asyncio
async def test_list_does_not_enrich_terminal_sessions(client, agent):
    """Sessions in terminal state are not enriched from K8s."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    # Stop the session (terminal state: failed)
    await client.post(f"/api/v1/sessions/{session_id}/stop")

    # Even with K8s returning different state, terminal sessions are untouched
    cr_statuses = _make_cr_statuses(session_id, "Idle")
    with patch("mob.services.sessions._list_cr_statuses_sync", return_value=cr_statuses):
        resp = await client.get("/api/v1/sessions")

    matched = [r for r in resp.json() if r["id"] == session_id]
    assert matched[0]["state"] == "failed"


@pytest.mark.asyncio
async def test_list_state_filter_works_with_enrichment(client, agent):
    """State filter works against enriched state, not stale DB state."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]
    cr_statuses = _make_cr_statuses(session_id, "Idle")

    with patch("mob.services.sessions._list_cr_statuses_sync", return_value=cr_statuses):
        # Filter for idle — should find the enriched session
        resp = await client.get("/api/v1/sessions", params={"state": "idle"})
        assert resp.status_code == 200
        assert any(r["id"] == session_id for r in resp.json())

        # Filter for pending — should NOT find it (it's now idle)
        resp = await client.get("/api/v1/sessions", params={"state": "pending"})
        assert resp.status_code == 200
        assert not any(r["id"] == session_id for r in resp.json())


@pytest.mark.asyncio
async def test_list_case_mapping(client, agent):
    """CR title-case states are normalized to DB lowercase in responses."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    for cr_state, expected in [("Starting", "starting"), ("Busy", "busy"), ("Idle", "idle")]:
        cr_statuses = _make_cr_statuses(session_id, cr_state)
        with patch("mob.services.sessions._list_cr_statuses_sync", return_value=cr_statuses):
            resp = await client.get("/api/v1/sessions")
        matched = [r for r in resp.json() if r["id"] == session_id]
        assert matched[0]["state"] == expected, f"Expected {expected} for CR state {cr_state}"


@pytest.mark.asyncio
async def test_get_single_session_enriches_state(client, agent):
    """GET /sessions/{id} returns enriched live state."""
    from mob.services.sessions import _CR_NOT_FOUND

    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    status = {"state": "Idle", "podName": "mob-agent-s-test"}
    with patch("mob.services.sessions._get_single_cr_status_sync", return_value=status):
        resp = await client.get(f"/api/v1/sessions/{session_id}")

    assert resp.status_code == 200
    assert resp.json()["state"] == "idle"
    assert resp.json()["pod_name"] == "mob-agent-s-test"


@pytest.mark.asyncio
async def test_get_single_session_degrades_without_k8s(client, agent):
    """GET /sessions/{id} falls back to DB state when K8s unavailable."""
    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    with patch("mob.services.sessions._get_single_cr_status_sync", return_value=None):
        resp = await client.get(f"/api/v1/sessions/{session_id}")

    assert resp.status_code == 200
    assert resp.json()["state"] == "pending"


@pytest.mark.asyncio
async def test_get_single_session_orphaned_cr(client, agent):
    """GET /sessions/{id} marks orphaned sessions as failed."""
    from mob.services.sessions import _CR_NOT_FOUND

    create_resp = await client.post("/api/v1/sessions", json={"agent_id": agent["id"]})
    session_id = create_resp.json()["id"]

    with patch("mob.services.sessions._get_single_cr_status_sync", return_value=_CR_NOT_FOUND):
        resp = await client.get(f"/api/v1/sessions/{session_id}")

    assert resp.status_code == 200
    assert resp.json()["state"] == "failed"
    assert resp.json()["error_message"] == "CR not found"
