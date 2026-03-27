"""Template CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table
from mob.cli.resolver import resolve_ref


@click.command("templates")
def templates():
    """List agent templates."""
    data = api_get("/templates")
    print_table(data, columns=["id", "name", "image", "runtime", "capabilities", "created_at"])


@click.group("template")
def template():
    """Manage agent templates."""
    pass


@template.command("create")
@click.option("--name", required=True, help="Template name")
@click.option("--image", required=True, help="Docker image reference")
@click.option("--runtime", required=True, help="Agent runtime (e.g., pydantic-ai, pi, openclaw)")
@click.option("--description", help="Template description")
@click.option("--capabilities", help="Comma-separated list of capabilities")
@click.option("--cpu-limit", help="CPU limit (e.g., 2000m)")
@click.option("--memory-limit", help="Memory limit (e.g., 2Gi)")
def template_create(name, image, runtime, description, capabilities, cpu_limit, memory_limit):
    """Create an agent template."""
    payload = {"name": name, "image": image, "runtime": runtime}
    if description:
        payload["description"] = description
    if capabilities:
        payload["capabilities"] = [c.strip() for c in capabilities.split(",")]
    if cpu_limit:
        payload["resource_cpu_limit"] = cpu_limit
    if memory_limit:
        payload["resource_memory_limit"] = memory_limit
    data = api_post("/templates", payload)
    print_success(f"Template '{name}' created.")
    print_detail(data)


@template.command("show")
@click.argument("ref")
def template_show(ref):
    """Show details of a template. REF is a name or position number."""
    template_id = resolve_ref("template", ref)
    data = api_get(f"/templates/{template_id}")
    print_detail(data)


@template.command("edit")
@click.argument("ref")
@click.option("--name", help="New template name")
@click.option("--image", help="New Docker image reference")
@click.option("--runtime", help="New runtime")
@click.option("--description", help="New description")
@click.option("--capabilities", help="New comma-separated capabilities")
@click.option("--cpu-limit", help="New CPU limit")
@click.option("--memory-limit", help="New memory limit")
def template_edit(ref, name, image, runtime, description, capabilities, cpu_limit, memory_limit):
    """Edit a template. REF is a name or position number."""
    template_id = resolve_ref("template", ref)
    payload = {}
    if name:
        payload["name"] = name
    if image:
        payload["image"] = image
    if runtime:
        payload["runtime"] = runtime
    if description:
        payload["description"] = description
    if capabilities:
        payload["capabilities"] = [c.strip() for c in capabilities.split(",")]
    if cpu_limit:
        payload["resource_cpu_limit"] = cpu_limit
    if memory_limit:
        payload["resource_memory_limit"] = memory_limit
    data = api_put(f"/templates/{template_id}", payload)
    print_success("Template updated.")
    print_detail(data)


@template.command("delete")
@click.argument("ref")
@click.confirmation_option(prompt="Are you sure you want to delete this template?")
def template_delete(ref):
    """Delete a template. REF is a name or position number."""
    template_id = resolve_ref("template", ref)
    api_delete(f"/templates/{template_id}")
    print_success("Template deleted.")
