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


def _build_payload_from_yaml(yaml_path: str) -> dict:
    """Parse YAML file and resolve domain/skill names to UUIDs."""
    from mob.cli.yaml_loader import load_agent_yaml

    spec = load_agent_yaml(yaml_path)

    # Resolve domain identifier to UUID
    domain_id = resolve_ref("domain", spec.domain)

    # Resolve skill names to UUIDs
    skill_ids = []
    if spec.skills:
        for skill_name in spec.skills:
            skill_ids.append(resolve_ref("skill", skill_name))

    payload = {
        "name": spec.name,
        "agent_template": spec.agent_template,
        "domain_id": domain_id,
        "skill_ids": skill_ids,
    }
    if spec.system_prompt:
        payload["system_prompt"] = spec.system_prompt
    if spec.model_endpoint:
        payload["model_endpoint"] = spec.model_endpoint
    if spec.env:
        payload["env_defaults"] = spec.env
    if spec.custom:
        payload["custom_config"] = spec.custom
    if spec.resource_cpu_limit:
        payload["resource_cpu_limit"] = spec.resource_cpu_limit
    if spec.resource_memory_limit:
        payload["resource_memory_limit"] = spec.resource_memory_limit
    return payload


@agent.command("create")
@click.option("--name", help="Agent name")
@click.option("--template", "agent_template", help="Docker image for the agent")
@click.option("--domain", "domain_id", help="Domain ID")
@click.option("--system-prompt", help="System prompt for the agent")
@click.option("--model-endpoint", help="Model endpoint URL")
@click.option("--skill", "skill_ids", multiple=True, help="Skill IDs to attach")
@click.option("--cpu-limit", "resource_cpu_limit", help="CPU resource limit (e.g. 2000m)")
@click.option("--memory-limit", "resource_memory_limit", help="Memory resource limit (e.g. 2Gi)")
@click.option("--file", "yaml_file", type=click.Path(exists=True), help="YAML definition file")
def agent_create(
    name: str | None,
    agent_template: str | None,
    domain_id: str | None,
    system_prompt: str | None,
    model_endpoint: str | None,
    skill_ids: tuple[str, ...],
    resource_cpu_limit: str | None,
    resource_memory_limit: str | None,
    yaml_file: str | None,
):
    """Create an agent from flags or a YAML file."""
    if yaml_file:
        payload = _build_payload_from_yaml(yaml_file)
    else:
        if not name or not agent_template or not domain_id:
            raise click.ClickException("--name, --template, and --domain are required (or use --file)")
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
        if resource_cpu_limit:
            payload["resource_cpu_limit"] = resource_cpu_limit
        if resource_memory_limit:
            payload["resource_memory_limit"] = resource_memory_limit

    data = api_post("/agents", payload)
    print_success(f"Agent '{data['name']}' created.")
    print_detail(data)


@agent.command("apply")
@click.argument("yaml_file", type=click.Path(exists=True))
def agent_apply(yaml_file: str):
    """Create or update an agent from a YAML definition file."""
    payload = _build_payload_from_yaml(yaml_file)
    agent_name = payload["name"]
    domain_id = payload["domain_id"]

    # Check if agent already exists (by name scoped to domain)
    existing = api_get("/agents", params={"domain_id": domain_id})
    match = [a for a in existing if a.get("name") == agent_name]

    if match:
        agent_id = match[0]["id"]
        data = api_put(f"/agents/{agent_id}", payload)
        print_success(f"Agent '{agent_name}' updated.")
    else:
        data = api_post("/agents", payload)
        print_success(f"Agent '{agent_name}' created.")
    print_detail(data)


@agent.command("edit")
@click.argument("ref")
@agent_filters
@click.option("--name", help="New agent name")
@click.option("--template", "agent_template", help="New Docker image")
@click.option("--system-prompt", help="New system prompt")
@click.option("--model-endpoint", help="New model endpoint URL")
@click.option("--cpu-limit", "resource_cpu_limit", help="CPU resource limit (e.g. 2000m)")
@click.option("--memory-limit", "resource_memory_limit", help="Memory resource limit (e.g. 2Gi)")
def agent_edit(
    ref: str,
    domain_id: str | None,
    name: str | None,
    agent_template: str | None,
    system_prompt: str | None,
    model_endpoint: str | None,
    resource_cpu_limit: str | None,
    resource_memory_limit: str | None,
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
    if resource_cpu_limit:
        payload["resource_cpu_limit"] = resource_cpu_limit
    if resource_memory_limit:
        payload["resource_memory_limit"] = resource_memory_limit
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
@click.option("--env", "env_overrides", multiple=True, help="Env override KEY=VALUE (repeatable)")
def agent_run_cmd(
    ref: str,
    domain_id: str | None,
    task_id: str | None,
    run_name: str | None,
    env_overrides: tuple[str, ...],
):
    """Run an instance of an agent. REF is a name or position number."""
    agent_id = resolve_ref("agent", ref, domain_id=domain_id)
    payload = {"agent_id": agent_id}
    if task_id:
        payload["task_id"] = task_id
    if run_name:
        payload["name"] = run_name
    if env_overrides:
        overrides = {}
        for item in env_overrides:
            if "=" not in item:
                raise click.ClickException(f"Invalid --env format: '{item}' (expected KEY=VALUE)")
            key, value = item.split("=", 1)
            overrides[key] = value
        payload["env_overrides"] = overrides
    data = api_post("/sessions", payload)
    print_success(f"Session '{data['name']}' created (state: {data['state']}).")
    print_detail(data)
