"""Skill CLI commands."""

import json

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table
from mob.cli.resolver import resolve_ref


@click.command("skills")
def skills():
    """List skills."""
    data = api_get("/skills")
    print_table(data, columns=["id", "name", "description", "created_at"])


@click.group("skill")
def skill():
    """Manage skills."""
    pass


@skill.command("create")
@click.option("--name", required=True, help="Skill name")
@click.option("--description", required=True, help="Skill description")
@click.option("--skill-md", help="SKILL.md content")
@click.option("--license", "license_", help="License identifier")
@click.option("--compatibility", help="Compatibility string")
@click.option("--metadata-json", help="JSON string of metadata key-value pairs")
@click.option("--allowed-tools", help="Comma-separated allowed tools")
def skill_create(name: str, description: str, skill_md: str | None, license_: str | None, compatibility: str | None, metadata_json: str | None, allowed_tools: str | None):
    """Create a skill."""
    payload: dict = {"name": name, "description": description}
    if skill_md:
        payload["skill_md"] = skill_md
    if license_:
        payload["license"] = license_
    if compatibility:
        payload["compatibility"] = compatibility
    if metadata_json:
        payload["metadata_json"] = json.loads(metadata_json)
    if allowed_tools:
        payload["allowed_tools"] = allowed_tools
    data = api_post("/skills", payload)
    print_success(f"Skill '{name}' created.")
    print_detail(data)


@skill.command("edit")
@click.argument("ref")
@click.option("--name", help="New skill name")
@click.option("--description", help="New description")
@click.option("--skill-md", help="New SKILL.md content")
@click.option("--license", "license_", help="New license identifier")
@click.option("--compatibility", help="New compatibility string")
@click.option("--metadata-json", help="JSON string of metadata key-value pairs")
@click.option("--allowed-tools", help="New comma-separated allowed tools")
def skill_edit(ref: str, name: str | None, description: str | None, skill_md: str | None, license_: str | None, compatibility: str | None, metadata_json: str | None, allowed_tools: str | None):
    """Edit a skill. REF is a name or position number."""
    skill_id = resolve_ref("skill", ref)
    payload: dict = {}
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if skill_md:
        payload["skill_md"] = skill_md
    if license_:
        payload["license"] = license_
    if compatibility:
        payload["compatibility"] = compatibility
    if metadata_json:
        payload["metadata_json"] = json.loads(metadata_json)
    if allowed_tools:
        payload["allowed_tools"] = allowed_tools
    data = api_put(f"/skills/{skill_id}", payload)
    print_success("Skill updated.")
    print_detail(data)


@skill.command("delete")
@click.argument("ref")
@click.confirmation_option(prompt="Are you sure you want to delete this skill?")
def skill_delete(ref: str):
    """Delete a skill. REF is a name or position number."""
    skill_id = resolve_ref("skill", ref)
    api_delete(f"/skills/{skill_id}")
    print_success("Skill deleted.")


@skill.command("show")
@click.argument("ref")
def skill_show(ref: str):
    """Show details of a skill. REF is a name or position number."""
    skill_id = resolve_ref("skill", ref)
    data = api_get(f"/skills/{skill_id}")
    print_detail(data)


@skill.command("import")
@click.argument("path")
def skill_import(path: str):
    """Import a skill from a SKILL.md file or directory.

    PATH can be a directory containing SKILL.md or the file itself.
    If a skill with the same name exists, it will be updated.
    """
    from mob.cli.skill_importer import load_skill_from_path

    try:
        data = load_skill_from_path(path)
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e))

    # Check if skill already exists by listing and matching name
    existing = api_get("/skills")
    match = [s for s in existing if s.get("name") == data["name"]]

    if match:
        # Update existing skill
        skill_id = match[0]["id"]
        result = api_put(f"/skills/{skill_id}", data)
        print_success(f"Skill '{data['name']}' updated.")
    else:
        # Create new skill
        result = api_post("/skills", data)
        print_success(f"Skill '{data['name']}' imported.")
    print_detail(result)
