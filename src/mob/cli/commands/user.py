"""User CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table
from mob.cli.resolver import resolve_ref


@click.command("users")
def users():
    """List users."""
    data = api_get("/users")
    print_table(data, columns=["id", "email", "name", "created_at"])


@click.group("user")
def user():
    """Manage users."""
    pass


@user.command("create")
@click.option("--email", required=True, help="User email")
@click.option("--name", required=True, help="User display name")
def user_create(email: str, name: str):
    """Create a user."""
    data = api_post("/users", {"email": email, "name": name})
    print_success(f"User '{email}' created.")
    print_detail(data)


@user.command("edit")
@click.argument("ref")
@click.option("--name", help="New display name")
@click.option("--email", help="New email")
def user_edit(ref: str, name: str | None, email: str | None):
    """Edit a user. REF is an email or position number."""
    user_id = resolve_ref("user", ref)
    payload = {}
    if name:
        payload["name"] = name
    if email:
        payload["email"] = email
    data = api_put(f"/users/{user_id}", payload)
    print_success("User updated.")
    print_detail(data)


@user.command("delete")
@click.argument("ref")
@click.confirmation_option(prompt="Are you sure you want to delete this user?")
def user_delete(ref: str):
    """Delete a user. REF is an email or position number."""
    user_id = resolve_ref("user", ref)
    api_delete(f"/users/{user_id}")
    print_success("User deleted.")


@user.command("show")
@click.argument("ref")
def user_show(ref: str):
    """Show details of a user. REF is an email or position number."""
    user_id = resolve_ref("user", ref)
    data = api_get(f"/users/{user_id}")
    print_detail(data)


@user.command("grant")
@click.argument("ref")
@click.option("--group", "group_id", required=True, help="Group ID to grant access to")
def user_grant(ref: str, group_id: str):
    """Grant a user access to a group. REF is an email or position number."""
    user_id = resolve_ref("user", ref)
    api_post(f"/groups/{group_id}/members", {"user_id": user_id})
    print_success("Access granted.")


@user.command("revoke")
@click.argument("ref")
@click.option("--group", "group_id", required=True, help="Group ID to revoke access from")
def user_revoke(ref: str, group_id: str):
    """Revoke a user's access from a group. REF is an email or position number."""
    user_id = resolve_ref("user", ref)
    api_delete(f"/groups/{group_id}/members/{user_id}")
    print_success("Access revoked.")
