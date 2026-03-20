"""User CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table


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
@click.argument("user_id")
@click.option("--name", help="New display name")
@click.option("--email", help="New email")
def user_edit(user_id: str, name: str | None, email: str | None):
    """Edit a user."""
    payload = {}
    if name:
        payload["name"] = name
    if email:
        payload["email"] = email
    data = api_put(f"/users/{user_id}", payload)
    print_success("User updated.")
    print_detail(data)


@user.command("delete")
@click.argument("user_id")
@click.confirmation_option(prompt="Are you sure you want to delete this user?")
def user_delete(user_id: str):
    """Delete a user."""
    api_delete(f"/users/{user_id}")
    print_success("User deleted.")


@user.command("show")
@click.argument("user_id")
def user_show(user_id: str):
    """Show details of a user."""
    data = api_get(f"/users/{user_id}")
    print_detail(data)


@user.command("grant")
@click.argument("user_id")
@click.option("--group", "group_id", required=True, help="Group ID to grant access to")
def user_grant(user_id: str, group_id: str):
    """Grant a user access to a group."""
    api_post(f"/groups/{group_id}/members", {"user_id": user_id})
    print_success("Access granted.")


@user.command("revoke")
@click.argument("user_id")
@click.option("--group", "group_id", required=True, help="Group ID to revoke access from")
def user_revoke(user_id: str, group_id: str):
    """Revoke a user's access from a group."""
    api_delete(f"/groups/{group_id}/members/{user_id}")
    print_success("Access revoked.")
