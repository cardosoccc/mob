"""Agent CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table


@click.command("agents")
@click.option("--domain", "domain_id", help="Filter by domain ID")
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
@click.argument("agent_id")
@click.option("--name", help="New agent name")
@click.option("--template", "agent_template", help="New Docker image")
@click.option("--system-prompt", help="New system prompt")
@click.option("--model-endpoint", help="New model endpoint URL")
def agent_edit(
    agent_id: str,
    name: str | None,
    agent_template: str | None,
    system_prompt: str | None,
    model_endpoint: str | None,
):
    """Edit an agent."""
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
@click.argument("agent_id")
@click.confirmation_option(prompt="Are you sure you want to delete this agent?")
def agent_delete(agent_id: str):
    """Delete an agent."""
    api_delete(f"/agents/{agent_id}")
    print_success("Agent deleted.")


@agent.command("show")
@click.argument("agent_id")
def agent_show(agent_id: str):
    """Show details of an agent."""
    data = api_get(f"/agents/{agent_id}")
    print_detail(data)


@agent.command("run")
@click.argument("agent_id")
@click.option("--task", "task_id", help="Task ID to associate with the run")
def agent_run(agent_id: str, task_id: str | None):
    """Run an instance of an agent."""
    payload = {"agent_id": agent_id}
    if task_id:
        payload["task_id"] = task_id
    data = api_post("/agent-runs", payload)
    print_success(f"Agent run '{data['id']}' created (state: {data['state']}).")
    print_detail(data)


@agent.command("stop")
@click.argument("run_id")
def agent_stop(run_id: str):
    """Stop a running agent instance."""
    data = api_post(f"/agent-runs/{run_id}/stop")
    print_success(f"Agent run '{run_id}' stopped.")
    print_detail(data)


@agent.command("logs")
@click.argument("run_id")
def agent_logs(run_id: str):
    """Show logs of an agent run."""
    # Get the agent run to find pod name
    run_data = api_get(f"/agent-runs/{run_id}")
    pod_name = run_data.get("pod_name")
    if not pod_name:
        click.echo("No pod associated with this run yet.")
        return
    click.echo(f"Logs for pod {pod_name}:")
    click.echo("(Kubernetes log streaming requires direct k8s access)")


@agent.command("attach")
@click.argument("run_id")
def agent_attach(run_id: str):
    """Attach to an agent's pod."""
    run_data = api_get(f"/agent-runs/{run_id}")
    pod_name = run_data.get("pod_name")
    if not pod_name:
        click.echo("No pod associated with this run yet.")
        return
    click.echo(f"Attaching to pod {pod_name}...")
    click.echo("(Interactive attach requires direct k8s access)")


@agent.command("send")
@click.argument("agent_id")
@click.option("--run", "run_id", required=True, help="Agent run ID")
@click.option("--message", required=True, help="Message to send to the agent")
def agent_send(agent_id: str, run_id: str, message: str):
    """Send a message to a running agent."""
    data = api_post(f"/agents/{agent_id}/send", {"message": message, "run_id": run_id})
    if data:
        print_detail(data)
    else:
        print_success("Message sent.")
