"""Import skills from AgentSkills.io SKILL.md files."""

import os
import re

import yaml


def parse_skill_md(content: str) -> dict:
    """Parse a SKILL.md file into frontmatter fields + body.

    Returns a dict with keys: name, description, skill_md, license,
    compatibility, metadata_json, allowed_tools.
    """
    # Extract YAML frontmatter between --- delimiters
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must contain YAML frontmatter between --- delimiters")

    frontmatter_str = match.group(1)
    body = match.group(2).strip()

    frontmatter = yaml.safe_load(frontmatter_str)
    if not isinstance(frontmatter, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    name = frontmatter.get("name")
    if not name:
        raise ValueError("SKILL.md frontmatter must include 'name'")

    description = frontmatter.get("description")
    if not description:
        raise ValueError("SKILL.md frontmatter must include 'description'")

    result = {
        "name": name,
        "description": description,
        "skill_md": body if body else None,
    }

    if "license" in frontmatter:
        result["license"] = frontmatter["license"]
    if "compatibility" in frontmatter:
        result["compatibility"] = frontmatter["compatibility"]
    if "metadata" in frontmatter:
        result["metadata_json"] = frontmatter["metadata"]
    if "allowed-tools" in frontmatter:
        result["allowed_tools"] = frontmatter["allowed-tools"]

    return result


def load_skill_from_path(path: str) -> dict:
    """Load a skill from a file path or directory path.

    If path is a directory, looks for SKILL.md inside it.
    If path is a file, reads it directly.
    """
    if os.path.isdir(path):
        skill_path = os.path.join(path, "SKILL.md")
        if not os.path.isfile(skill_path):
            raise FileNotFoundError(f"No SKILL.md found in {path}")
    elif os.path.isfile(path):
        skill_path = path
    else:
        raise FileNotFoundError(f"Path not found: {path}")

    with open(skill_path) as f:
        content = f.read()

    return parse_skill_md(content)
