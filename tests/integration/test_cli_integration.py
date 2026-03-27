"""Integration tests for CLI -> API -> DB flow."""

import asyncio
import json
import os
import tempfile
import threading
import time

import pytest
import uvicorn
from click.testing import CliRunner

from mob.cli.main import cli


def _get_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def api_server(tmp_path):
    """Start a real API server for integration tests."""
    db_path = tmp_path / "test.db"
    port = _get_free_port()

    os.environ["MOB_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["MOB_API_PORT"] = str(port)
    os.environ["MOB_API_BASE_URL"] = f"http://localhost:{port}"

    # Reset database singletons
    import mob.database as db_mod
    db_mod._engine = None
    db_mod._session_factory = None

    from mob.api.app import create_app
    app = create_app()

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to start
    import httpx
    for _ in range(50):
        try:
            resp = httpx.get(f"http://localhost:{port}/health")
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.1)

    yield port

    server.should_exit = True
    thread.join(timeout=5)

    # Cleanup env
    for key in ["MOB_DATABASE_URL", "MOB_API_PORT", "MOB_API_BASE_URL"]:
        os.environ.pop(key, None)
    db_mod._engine = None
    db_mod._session_factory = None


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_dir(tmp_path, api_server):
    config_file = tmp_path / "mob_config.json"
    config = {"api_base_url": f"http://localhost:{api_server}"}
    config_file.write_text(json.dumps(config))
    os.environ["MOB_CONFIG_FILE"] = str(config_file)
    os.environ["MOB_API_BASE_URL"] = f"http://localhost:{api_server}"
    yield
    os.environ.pop("MOB_CONFIG_FILE", None)
    os.environ.pop("MOB_API_BASE_URL", None)


def test_config_set_and_get(runner, tmp_path):
    config_file = tmp_path / "cfg.json"
    os.environ["MOB_CONFIG_FILE"] = str(config_file)

    result = runner.invoke(cli, ["config", "set", "api_host", "myhost"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["config", "get", "api_host"])
    assert result.exit_code == 0
    assert "myhost" in result.output

    os.environ.pop("MOB_CONFIG_FILE", None)


def test_configs_list(runner, tmp_path):
    config_file = tmp_path / "cfg2.json"
    os.environ["MOB_CONFIG_FILE"] = str(config_file)

    runner.invoke(cli, ["config", "set", "debug", "true"])
    result = runner.invoke(cli, ["configs"])
    assert result.exit_code == 0

    os.environ.pop("MOB_CONFIG_FILE", None)


@pytest.mark.integration
def test_org_create_list_show_delete(runner, config_dir):
    # Create
    result = runner.invoke(cli, ["org", "create", "--identifier", "int-org", "--name", "Integration Org"])
    assert result.exit_code == 0
    assert "int-org" in result.output

    # List
    result = runner.invoke(cli, ["orgs"])
    assert result.exit_code == 0

    # Show - extract org_id from create output
    # Get orgs via API to find the ID
    from mob.config import get_settings
    import httpx
    resp = httpx.get(f"{get_settings().api_base_url}/api/v1/organizations")
    orgs = resp.json()
    org_id = next(o["id"] for o in orgs if o["identifier"] == "int-org")

    result = runner.invoke(cli, ["org", "show", org_id])
    assert result.exit_code == 0
    assert "int-org" in result.output

    # Edit
    result = runner.invoke(cli, ["org", "edit", org_id, "--name", "Updated Org"])
    assert result.exit_code == 0

    # Delete
    result = runner.invoke(cli, ["org", "delete", org_id, "--yes"])
    assert result.exit_code == 0


@pytest.mark.integration
def test_domain_lifecycle(runner, config_dir):
    # Create org first
    runner.invoke(cli, ["org", "create", "--identifier", "dom-int-org", "--name", "Dom Int Org"])

    from mob.config import get_settings
    import httpx
    resp = httpx.get(f"{get_settings().api_base_url}/api/v1/organizations")
    org_id = next(o["id"] for o in resp.json() if o["identifier"] == "dom-int-org")

    # Create domain
    result = runner.invoke(cli, ["domain", "create", "--identifier", "eng", "--name", "Engineering", "--org", org_id])
    assert result.exit_code == 0
    assert "dom-int-org-eng" in result.output

    # List domains
    result = runner.invoke(cli, ["domains", "--org", org_id])
    assert result.exit_code == 0


@pytest.mark.integration
def test_user_lifecycle(runner, config_dir):
    # Create
    result = runner.invoke(cli, ["user", "create", "--email", "int@test.com", "--name", "Int User"])
    assert result.exit_code == 0

    from mob.config import get_settings
    import httpx
    resp = httpx.get(f"{get_settings().api_base_url}/api/v1/users")
    user_id = next(u["id"] for u in resp.json() if u["email"] == "int@test.com")

    # Show
    result = runner.invoke(cli, ["user", "show", user_id])
    assert result.exit_code == 0

    # Edit
    result = runner.invoke(cli, ["user", "edit", user_id, "--name", "Updated User"])
    assert result.exit_code == 0

    # List
    result = runner.invoke(cli, ["users"])
    assert result.exit_code == 0

    # Delete
    result = runner.invoke(cli, ["user", "delete", user_id, "--yes"])
    assert result.exit_code == 0


@pytest.mark.integration
def test_group_lifecycle(runner, config_dir):
    runner.invoke(cli, ["org", "create", "--identifier", "grp-int-org", "--name", "Grp Int Org"])

    from mob.config import get_settings
    import httpx
    resp = httpx.get(f"{get_settings().api_base_url}/api/v1/organizations")
    org_id = next(o["id"] for o in resp.json() if o["identifier"] == "grp-int-org")

    result = runner.invoke(cli, ["group", "create", "--name", "devs", "--org", org_id])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["groups", "--org", org_id])
    assert result.exit_code == 0


@pytest.mark.integration
def test_skill_lifecycle(runner, config_dir):
    result = runner.invoke(cli, ["skill", "create", "--name", "int-skill", "--description", "Test skill"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["skills"])
    assert result.exit_code == 0


@pytest.mark.integration
def test_agent_lifecycle(runner, config_dir):
    runner.invoke(cli, ["org", "create", "--identifier", "ag-int-org", "--name", "Agent Int Org"])

    from mob.config import get_settings
    import httpx
    base = get_settings().api_base_url
    resp = httpx.get(f"{base}/api/v1/organizations")
    org_id = next(o["id"] for o in resp.json() if o["identifier"] == "ag-int-org")

    # Get the default domain
    resp = httpx.get(f"{base}/api/v1/domains", params={"organization_id": org_id})
    domain_id = resp.json()[0]["id"]

    # Create agent
    result = runner.invoke(cli, [
        "agent", "create",
        "--name", "int-agent",
        "--template", "test:latest",
        "--domain", domain_id,
        "--system-prompt", "You are a test agent.",
    ])
    assert result.exit_code == 0

    resp = httpx.get(f"{base}/api/v1/agents", params={"domain_id": domain_id})
    agent_id = next(a["id"] for a in resp.json() if a["name"] == "int-agent")

    # Show
    result = runner.invoke(cli, ["agent", "show", agent_id])
    assert result.exit_code == 0

    # List
    result = runner.invoke(cli, ["agents", "--domain", domain_id])
    assert result.exit_code == 0

    # Run
    result = runner.invoke(cli, ["agent", "run", agent_id])
    assert result.exit_code == 0

    # Edit
    result = runner.invoke(cli, ["agent", "edit", agent_id, "--name", "updated-agent"])
    assert result.exit_code == 0

    # Delete
    result = runner.invoke(cli, ["agent", "delete", agent_id, "--yes"])
    assert result.exit_code == 0


@pytest.mark.integration
def test_session_lifecycle(runner, config_dir):
    """Test sessions list and session commands."""
    runner.invoke(cli, ["org", "create", "--identifier", "ar-int-org", "--name", "AR Int Org"])

    from mob.config import get_settings
    import httpx
    base = get_settings().api_base_url
    resp = httpx.get(f"{base}/api/v1/organizations")
    org_id = next(o["id"] for o in resp.json() if o["identifier"] == "ar-int-org")

    resp = httpx.get(f"{base}/api/v1/domains", params={"organization_id": org_id})
    domain_id = resp.json()[0]["id"]

    # Create agent
    runner.invoke(cli, [
        "agent", "create",
        "--name", "ar-test-agent",
        "--template", "test:latest",
        "--domain", domain_id,
    ])

    resp = httpx.get(f"{base}/api/v1/agents", params={"domain_id": domain_id})
    agent_id = next(a["id"] for a in resp.json() if a["name"] == "ar-test-agent")

    # Create session with custom name
    result = runner.invoke(cli, ["agent", "run", agent_id, "--name", "my-test-run"])
    assert result.exit_code == 0
    assert "my-test-run" in result.output

    # Create session with auto-generated name
    result = runner.invoke(cli, ["agent", "run", agent_id])
    assert result.exit_code == 0
    assert "ar-test-agent-" in result.output

    # List sessions
    result = runner.invoke(cli, ["sessions"])
    assert result.exit_code == 0
    assert "my-test-run" in result.output

    # List with --agent filter (using agent name)
    result = runner.invoke(cli, ["sessions", "--agent", agent_id])
    assert result.exit_code == 0

    # Show by name
    result = runner.invoke(cli, ["session", "show", "my-test-run"])
    assert result.exit_code == 0
    assert "my-test-run" in result.output

    # Stop by name
    result = runner.invoke(cli, ["session", "stop", "my-test-run"])
    assert result.exit_code == 0
    assert "stopped" in result.output.lower()


@pytest.mark.integration
def test_user_grant_revoke(runner, config_dir):
    runner.invoke(cli, ["org", "create", "--identifier", "grant-org", "--name", "Grant Org"])

    from mob.config import get_settings
    import httpx
    base = get_settings().api_base_url

    resp = httpx.get(f"{base}/api/v1/organizations")
    org_id = next(o["id"] for o in resp.json() if o["identifier"] == "grant-org")

    # Create user and group
    runner.invoke(cli, ["user", "create", "--email", "grant@test.com", "--name", "Grant User"])
    runner.invoke(cli, ["group", "create", "--name", "grant-group", "--org", org_id])

    resp = httpx.get(f"{base}/api/v1/users")
    user_id = next(u["id"] for u in resp.json() if u["email"] == "grant@test.com")

    resp = httpx.get(f"{base}/api/v1/groups", params={"organization_id": org_id})
    group_id = next(g["id"] for g in resp.json() if g["name"] == "grant-group")

    # Grant
    result = runner.invoke(cli, ["user", "grant", user_id, "--group", group_id])
    assert result.exit_code == 0

    # Revoke
    result = runner.invoke(cli, ["user", "revoke", user_id, "--group", group_id])
    assert result.exit_code == 0
