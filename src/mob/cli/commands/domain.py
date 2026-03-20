"""Domain CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table


@click.command("domains")
@click.option("--org", "organization_id", help="Filter by organization ID")
def domains(organization_id: str | None):
    """List domains."""
    params = {}
    if organization_id:
        params["organization_id"] = organization_id
    data = api_get("/domains", params=params)
    print_table(data, columns=["id", "identifier", "name", "organization_id", "created_at"])


@click.group("domain")
def domain():
    """Manage domains."""
    pass


@domain.command("create")
@click.option("--identifier", required=True, help="Domain identifier suffix")
@click.option("--name", required=True, help="Display name")
@click.option("--org", "organization_id", required=True, help="Organization ID")
def domain_create(identifier: str, name: str, organization_id: str):
    """Create a domain."""
    data = api_post("/domains", {
        "identifier_suffix": identifier,
        "name": name,
        "organization_id": organization_id,
    })
    print_success(f"Domain '{data['identifier']}' created.")
    print_detail(data)


@domain.command("edit")
@click.argument("domain_id")
@click.option("--name", help="New display name")
def domain_edit(domain_id: str, name: str | None):
    """Edit a domain."""
    payload = {}
    if name:
        payload["name"] = name
    data = api_put(f"/domains/{domain_id}", payload)
    print_success("Domain updated.")
    print_detail(data)


@domain.command("delete")
@click.argument("domain_id")
@click.confirmation_option(prompt="Are you sure you want to delete this domain?")
def domain_delete(domain_id: str):
    """Delete a domain."""
    api_delete(f"/domains/{domain_id}")
    print_success("Domain deleted.")


@domain.command("show")
@click.argument("domain_id")
def domain_show(domain_id: str):
    """Show details of a domain."""
    data = api_get(f"/domains/{domain_id}")
    print_detail(data)
