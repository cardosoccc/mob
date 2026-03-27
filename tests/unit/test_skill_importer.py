"""Unit tests for skill importer."""

import os
import tempfile

import pytest

from mob.cli.skill_importer import load_skill_from_path, parse_skill_md


def test_parse_skill_md_minimal():
    content = """---
name: test-skill
description: A test skill.
---

# Test Skill

Do the thing.
"""
    result = parse_skill_md(content)
    assert result["name"] == "test-skill"
    assert result["description"] == "A test skill."
    assert "# Test Skill" in result["skill_md"]


def test_parse_skill_md_full():
    content = """---
name: pdf-processing
description: Extract PDF text, fill forms, merge files.
license: Apache-2.0
compatibility: Requires Python 3.11+
metadata:
  author: example-org
  version: "1.0"
allowed-tools: Bash(git:*) Read
---

# PDF Processing

Step-by-step instructions here.
"""
    result = parse_skill_md(content)
    assert result["name"] == "pdf-processing"
    assert result["description"] == "Extract PDF text, fill forms, merge files."
    assert result["license"] == "Apache-2.0"
    assert result["compatibility"] == "Requires Python 3.11+"
    assert result["metadata_json"] == {"author": "example-org", "version": "1.0"}
    assert result["allowed_tools"] == "Bash(git:*) Read"
    assert "Step-by-step" in result["skill_md"]


def test_parse_skill_md_no_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill_md("# Just markdown\nNo frontmatter here.")


def test_parse_skill_md_missing_name():
    with pytest.raises(ValueError, match="name"):
        parse_skill_md("---\ndescription: No name\n---\nBody")


def test_parse_skill_md_missing_description():
    with pytest.raises(ValueError, match="description"):
        parse_skill_md("---\nname: no-desc\n---\nBody")


def test_load_skill_from_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = os.path.join(tmpdir, "SKILL.md")
        with open(skill_path, "w") as f:
            f.write("---\nname: dir-skill\ndescription: From dir.\n---\nBody.")

        result = load_skill_from_path(tmpdir)
        assert result["name"] == "dir-skill"


def test_load_skill_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nname: file-skill\ndescription: From file.\n---\nBody.")
        f.flush()
        try:
            result = load_skill_from_path(f.name)
            assert result["name"] == "file-skill"
        finally:
            os.unlink(f.name)


def test_load_skill_directory_no_skill_md():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError, match="No SKILL.md"):
            load_skill_from_path(tmpdir)


def test_load_skill_nonexistent_path():
    with pytest.raises(FileNotFoundError, match="Path not found"):
        load_skill_from_path("/nonexistent/path/xyz")
