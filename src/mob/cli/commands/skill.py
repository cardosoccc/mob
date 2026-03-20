"""Skill CLI commands."""

import click

from mob.cli.client import api_delete, api_get, api_post, api_put
from mob.cli.output import print_detail, print_success, print_table


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
@click.option("--description", help="Skill description")
@click.option("--skills-md", help="SKILLS.md content")
@click.option("--references-path", help="Path to references folder")
def skill_create(name: str, description: str | None, skills_md: str | None, references_path: str | None):
    """Create a skill."""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if skills_md:
        payload["skills_md"] = skills_md
    if references_path:
        payload["references_path"] = references_path
    data = api_post("/skills", payload)
    print_success(f"Skill '{name}' created.")
    print_detail(data)


@skill.command("edit")
@click.argument("skill_id")
@click.option("--name", help="New skill name")
@click.option("--description", help="New description")
@click.option("--skills-md", help="New SKILLS.md content")
@click.option("--references-path", help="New references path")
def skill_edit(skill_id: str, name: str | None, description: str | None, skills_md: str | None, references_path: str | None):
    """Edit a skill."""
    payload = {}
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if skills_md:
        payload["skills_md"] = skills_md
    if references_path:
        payload["references_path"] = references_path
    data = api_put(f"/skills/{skill_id}", payload)
    print_success("Skill updated.")
    print_detail(data)


@skill.command("delete")
@click.argument("skill_id")
@click.confirmation_option(prompt="Are you sure you want to delete this skill?")
def skill_delete(skill_id: str):
    """Delete a skill."""
    api_delete(f"/skills/{skill_id}")
    print_success("Skill deleted.")
