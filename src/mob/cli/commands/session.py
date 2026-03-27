"""Session CLI commands."""

import click

from mob.cli.client import api_get, api_post
from mob.cli.output import print_detail, print_success, print_table
from mob.cli.resolver import agent_filters, resolve_ref


def _resolve_agent_filter(agent_ref: str | None, domain_id: str | None) -> str | None:
    """Resolve optional --agent filter to agent_id, or return None."""
    if agent_ref:
        return resolve_ref("agent", agent_ref, domain_id=domain_id)
    return None


@click.command("sessions")
@click.option("--agent", "agent_ref", help="Filter by agent (name or position)")
@agent_filters
@click.option("--state", help="Filter by state (pending, starting, idle, busy, finished, failed)")
def sessions(agent_ref: str | None, domain_id: str | None, state: str | None):
    """List sessions."""
    params = {}
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    if agent_id:
        params["agent_id"] = agent_id
    if state:
        params["state"] = state
    data = api_get("/sessions", params=params)
    print_table(data, columns=["id", "name", "agent_id", "state", "pod_name", "created_at"])


@click.group("session")
def session():
    """Manage sessions."""
    pass


@session.command("show")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def session_show(ref: str, agent_ref: str | None, domain_id: str | None):
    """Show details of a session. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    session_id = resolve_ref("session", ref, agent_id=agent_id)
    data = api_get(f"/sessions/{session_id}")
    print_detail(data)


@session.command("stop")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def session_stop(ref: str, agent_ref: str | None, domain_id: str | None):
    """Stop a running session. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    session_id = resolve_ref("session", ref, agent_id=agent_id)
    data = api_post(f"/sessions/{session_id}/stop")
    print_success("Session stopped.")
    print_detail(data)


@session.command("logs")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.option("--tail", default=100, help="Number of log lines")
def session_logs(ref: str, agent_ref: str | None, domain_id: str | None, tail: int):
    """Show logs of a session. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    session_id = resolve_ref("session", ref, agent_id=agent_id)
    data = api_get(f"/sessions/{session_id}/logs", params={"tail": tail})
    status = data.get("status", {})
    if status:
        click.echo(f"State: {status.get('state', 'unknown')}")
        if status.get("podName"):
            click.echo(f"Pod: {status['podName']}")
        if status.get("errorMessage"):
            click.echo(f"Error: {status['errorMessage']}")
    else:
        click.echo("No live status available (K8s may not be configured).")
    logs = data.get("logs", [])
    if logs:
        click.echo("---")
        for line in logs:
            click.echo(line)


@session.command("send")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.option("--message", required=True, help="Message to send")
def session_send(ref: str, agent_ref: str | None, domain_id: str | None, message: str):
    """Send a message to a running agent. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    session_id = resolve_ref("session", ref, agent_id=agent_id)
    result = api_post(f"/sessions/{session_id}/send", {"message": message})
    if result and result.get("response"):
        click.echo(result["response"])
    else:
        print_success("Message sent.")
