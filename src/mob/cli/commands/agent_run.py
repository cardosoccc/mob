"""Agent run CLI commands."""

import click

from mob.cli.client import api_get, api_post
from mob.cli.output import print_detail, print_success, print_table
from mob.cli.resolver import agent_filters, resolve_ref


def _resolve_agent_filter(agent_ref: str | None, domain_id: str | None) -> str | None:
    """Resolve optional --agent filter to agent_id, or return None."""
    if agent_ref:
        return resolve_ref("agent", agent_ref, domain_id=domain_id)
    return None


@click.command("agent-runs")
@click.option("--agent", "agent_ref", help="Filter by agent (name or position)")
@agent_filters
@click.option("--state", help="Filter by state (pending, starting, idle, busy, finished, failed)")
def agent_runs(agent_ref: str | None, domain_id: str | None, state: str | None):
    """List agent runs."""
    params = {}
    if agent_ref:
        agent_id = resolve_ref("agent", agent_ref, domain_id=domain_id)
        params["agent_id"] = agent_id
    if state:
        params["state"] = state
    data = api_get("/agent-runs", params=params)
    print_table(data, columns=["id", "name", "agent_id", "state", "pod_name", "created_at"])


@click.group("agent-run")
def agent_run():
    """Manage agent runs."""
    pass


@agent_run.command("show")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def agent_run_show(ref: str, agent_ref: str | None, domain_id: str | None):
    """Show details of an agent run. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_get(f"/agent-runs/{run_id}")
    print_detail(data)


@agent_run.command("stop")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def agent_run_stop(ref: str, agent_ref: str | None, domain_id: str | None):
    """Stop a running agent instance. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_post(f"/agent-runs/{run_id}/stop")
    print_success("Agent run stopped.")
    print_detail(data)


@agent_run.command("logs")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.option("--tail", default=100, help="Number of log lines")
def agent_run_logs(ref: str, agent_ref: str | None, domain_id: str | None, tail: int):
    """Show logs of an agent run. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    data = api_get(f"/agent-runs/{run_id}/logs", params={"tail": tail})
    status = data.get("status", {})
    if status:
        click.echo(f"State: {status.get('state', 'unknown')}")
        if status.get("podName"):
            click.echo(f"Pod: {status['podName']}")
        if status.get("errorMessage"):
            click.echo(f"Error: {status['errorMessage']}")
    else:
        click.echo("No live status available (K8s may not be configured).")


@agent_run.command("attach")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
def agent_run_attach(ref: str, agent_ref: str | None, domain_id: str | None):
    """Attach to an agent run's pod (not yet implemented). REF is a name or position number."""
    click.echo("Error: Interactive attach is not yet implemented.", err=True)
    click.echo("It requires websocket streaming support.", err=True)
    raise SystemExit(1)


@agent_run.command("send")
@click.argument("ref")
@click.option("--agent", "agent_ref", help="Scope by agent (name or position)")
@agent_filters
@click.option("--message", required=True, help="Message to send")
def agent_run_send(ref: str, agent_ref: str | None, domain_id: str | None, message: str):
    """Send a message to a running agent. REF is a name or position number."""
    agent_id = _resolve_agent_filter(agent_ref, domain_id)
    run_id = resolve_ref("agent_run", ref, agent_id=agent_id)
    api_post(f"/agent-runs/{run_id}/send", {"message": message})
    print_success("Message sent.")
