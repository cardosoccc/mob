"""Organization CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table


@click.command("orgs")
def orgs():
    """List organizations."""
    data = api_get("/organizations")
    print_table(data, columns=["id", "identifier", "name", "created_at"])


@click.group("org")
def org():
    """Manage organizations."""
    pass


@org.command("create")
@click.option("--identifier", required=True, help="Unique identifier for the organization")
@click.option("--name", required=True, help="Display name")
def org_create(identifier: str, name: str):
    """Create an organization."""
    data = api_post("/organizations", {"identifier": identifier, "name": name})
    print_success(f"Organization '{identifier}' created.")
    print_detail(data)


@org.command("edit")
@click.argument("org_id")
@click.option("--name", help="New display name")
def org_edit(org_id: str, name: str | None):
    """Edit an organization."""
    payload = {}
    if name:
        payload["name"] = name
    data = api_put(f"/organizations/{org_id}", payload)
    print_success("Organization updated.")
    print_detail(data)


@org.command("delete")
@click.argument("org_id")
@click.confirmation_option(prompt="Are you sure you want to delete this organization?")
def org_delete(org_id: str):
    """Delete an organization."""
    api_delete(f"/organizations/{org_id}")
    print_success("Organization deleted.")


@org.command("show")
@click.argument("org_id")
def org_show(org_id: str):
    """Show details of an organization."""
    data = api_get(f"/organizations/{org_id}")
    print_detail(data)
