"""Group CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table


@click.command("groups")
@click.option("--org", "organization_id", help="Filter by organization ID")
def groups(organization_id: str | None):
    """List groups."""
    params = {}
    if organization_id:
        params["organization_id"] = organization_id
    data = api_get("/groups", params=params)
    print_table(data, columns=["id", "name", "organization_id", "created_at"])


@click.group("group")
def group():
    """Manage groups."""
    pass


@group.command("create")
@click.option("--name", required=True, help="Group name")
@click.option("--org", "organization_id", required=True, help="Organization ID")
def group_create(name: str, organization_id: str):
    """Create a group."""
    data = api_post("/groups", {"name": name, "organization_id": organization_id})
    print_success(f"Group '{name}' created.")
    print_detail(data)


@group.command("edit")
@click.argument("group_id")
@click.option("--name", help="New group name")
def group_edit(group_id: str, name: str | None):
    """Edit a group."""
    payload = {}
    if name:
        payload["name"] = name
    data = api_put(f"/groups/{group_id}", payload)
    print_success("Group updated.")
    print_detail(data)


@group.command("delete")
@click.argument("group_id")
@click.confirmation_option(prompt="Are you sure you want to delete this group?")
def group_delete(group_id: str):
    """Delete a group."""
    api_delete(f"/groups/{group_id}")
    print_success("Group deleted.")


@group.command("show")
@click.argument("group_id")
def group_show(group_id: str):
    """Show details of a group."""
    data = api_get(f"/groups/{group_id}")
    print_detail(data)
