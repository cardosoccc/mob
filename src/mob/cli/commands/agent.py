"""Agent CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table
from mob.cli.resolver import agent_filters, resolve_ref


@click.command("agents")
@agent_filters
def agents(domain_id: str | None):
    """List agents."""
    params = {}
    if domain_id:
        params["domain_id"] = domain_id
    data = api_get("/agents", params=params)
    print_table(data, columns=["id", "name", "agent_template", "domain_id", "created_at"])


@click.group("agent")
def agent():
    """Manage agents."""
    pass


@agent.command("create")
@click.option("--name", required=True, help="Agent name")
@click.option("--template", "agent_template", required=True, help="Docker image for the agent")
@click.option("--domain", "domain_id", required=True, help="Domain ID")
@click.option("--system-prompt", help="System prompt for the agent")
@click.option("--model-endpoint", help="Model endpoint URL")
@click.option("--skill", "skill_ids", multiple=True, help="Skill IDs to attach")
def agent_create(
    name: str,
    agent_template: str,
    domain_id: str,
    system_prompt: str | None,
    model_endpoint: str | None,
    skill_ids: tuple[str, ...],
):
    """Create an agent."""
    payload = {
        "name": name,
        "agent_template": agent_template,
        "domain_id": domain_id,
        "skill_ids": list(skill_ids),
    }
    if system_prompt:
        payload["system_prompt"] = system_prompt
    if model_endpoint:
        payload["model_endpoint"] = model_endpoint
    data = api_post("/agents", payload)
    print_success(f"Agent '{name}' created.")
    print_detail(data)


@agent.command("edit")
@click.argument("ref")
@agent_filters
@click.option("--name", help="New agent name")
@click.option("--template", "agent_template", help="New Docker image")
@click.option("--system-prompt", help="New system prompt")
@click.option("--model-endpoint", help="New model endpoint URL")
def agent_edit(
    ref: str,
    domain_id: str | None,
    name: str | None,
    agent_template: str | None,
    system_prompt: str | None,
    model_endpoint: str | None,
):
    """Edit an agent. REF is a name or position number."""
    agent_id = resolve_ref("agent", ref, domain_id=domain_id)
    payload = {}
    if name:
        payload["name"] = name
    if agent_template:
        payload["agent_template"] = agent_template
    if system_prompt:
        payload["system_prompt"] = system_prompt
    if model_endpoint:
        payload["model_endpoint"] = model_endpoint
    data = api_put(f"/agents/{agent_id}", payload)
    print_success("Agent updated.")
    print_detail(data)


@agent.command("delete")
@click.argument("ref")
@agent_filters
@click.confirmation_option(prompt="Are you sure you want to delete this agent?")
def agent_delete(ref: str, domain_id: str | None):
    """Delete an agent. REF is a name or position number."""
    agent_id = resolve_ref("agent", ref, domain_id=domain_id)
    api_delete(f"/agents/{agent_id}")
    print_success("Agent deleted.")


@agent.command("show")
@click.argument("ref")
@agent_filters
def agent_show(ref: str, domain_id: str | None):
    """Show details of an agent. REF is a name or position number."""
    agent_id = resolve_ref("agent", ref, domain_id=domain_id)
    data = api_get(f"/agents/{agent_id}")
    print_detail(data)


@agent.command("run")
@click.argument("ref")
@agent_filters
@click.option("--task", "task_id", help="Task ID to associate with the run")
@click.option("--name", "run_name", help="Custom name for the run (default: agent-name + random suffix)")
def agent_run_cmd(ref: str, domain_id: str | None, task_id: str | None, run_name: str | None):
    """Run an instance of an agent. REF is a name or position number."""
    agent_id = resolve_ref("agent", ref, domain_id=domain_id)
    payload = {"agent_id": agent_id}
    if task_id:
        payload["task_id"] = task_id
    if run_name:
        payload["name"] = run_name
    data = api_post("/agent-runs", payload)
    print_success(f"Agent run '{data['name']}' created (state: {data['state']}).")
    print_detail(data)
