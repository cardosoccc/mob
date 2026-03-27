"""Unit tests for env CLI commands."""

import json

import pytest
from click.testing import CliRunner

from mob.cli.commands.env_cmd import env, envs


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setenv("MOB_CONFIG_FILE", str(config_file))
    return tmp_path


def _write_config(config_dir, config):
    """Write a config file."""
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(config))


def _read_config(config_dir):
    """Read config file back."""
    return json.loads((config_dir / "config.json").read_text())


# --- env set ---


def test_env_set_switches_environment(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {
            "local": {"mode": "local"},
            "dev": {"mode": "remote", "api_base_url": "http://localhost:8080"},
        },
    })
    result = CliRunner().invoke(env, ["set", "dev"])
    assert result.exit_code == 0
    assert "Switched to environment 'dev'" in result.output
    assert _read_config(config_dir)["env"] == "dev"


def test_env_set_rejects_invalid(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["set", "banana"])
    assert result.exit_code == 1
    assert "Invalid environment" in result.output


def test_env_set_rejects_unconfigured(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["set", "prd"])
    assert result.exit_code == 1
    assert "not configured" in result.output


# --- env show ---


def test_env_show_active(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {"local": {"mode": "local", "database_url": "sqlite:///test.db"}},
    })
    result = CliRunner().invoke(env, ["show"])
    assert result.exit_code == 0
    assert "Active environment:" in result.output
    assert "local" in result.output
    assert "mode:" in result.output


def test_env_show_specific(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {
            "local": {"mode": "local"},
            "dev": {"mode": "remote", "api_base_url": "http://localhost:8080"},
        },
    })
    result = CliRunner().invoke(env, ["show", "dev"])
    assert result.exit_code == 0
    assert "remote" in result.output


def test_env_show_invalid(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["show", "banana"])
    assert result.exit_code == 1
    assert "Invalid environment" in result.output


def test_env_show_unconfigured(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["show", "prd"])
    assert result.exit_code == 1
    assert "not configured" in result.output


# --- envs / env list ---


def test_envs_lists_all(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    result = CliRunner().invoke(envs)
    assert result.exit_code == 0
    assert "local" in result.output
    assert "dev" in result.output
    assert "stg" in result.output
    assert "prd" in result.output


def test_envs_marks_active(config_dir):
    _write_config(config_dir, {
        "env": "dev",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    result = CliRunner().invoke(envs)
    assert result.exit_code == 0
    assert "* dev" in result.output


def test_envs_shows_configured_status(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {"local": {"mode": "local"}},
    })
    result = CliRunner().invoke(envs)
    assert result.exit_code == 0
    assert "yes" in result.output  # local is configured
    assert "no" in result.output   # others are not


def test_env_list_matches_envs(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    envs_result = CliRunner().invoke(envs)
    list_result = CliRunner().invoke(env, ["list"])
    assert envs_result.exit_code == 0
    assert list_result.exit_code == 0
    assert envs_result.output == list_result.output


# --- env edit ---


def test_env_edit_updates_field(config_dir):
    _write_config(config_dir, {
        "env": "dev",
        "environments": {"dev": {"mode": "remote", "api_base_url": "http://localhost:8080"}},
    })
    result = CliRunner().invoke(env, ["edit", "dev", "--api-base-url", "http://new-url:8080"])
    assert result.exit_code == 0
    assert "updated" in result.output
    assert _read_config(config_dir)["environments"]["dev"]["api_base_url"] == "http://new-url:8080"


def test_env_edit_updates_multiple_fields(config_dir):
    _write_config(config_dir, {
        "env": "dev",
        "environments": {"dev": {"mode": "remote", "api_base_url": "http://localhost:8080"}},
    })
    result = CliRunner().invoke(env, ["edit", "dev", "--mode", "local", "--database-url", "sqlite:///new.db"])
    assert result.exit_code == 0
    config = _read_config(config_dir)
    assert config["environments"]["dev"]["mode"] == "local"
    assert config["environments"]["dev"]["database_url"] == "sqlite:///new.db"


def test_env_edit_no_changes(config_dir):
    _write_config(config_dir, {
        "env": "dev",
        "environments": {"dev": {"mode": "remote", "api_base_url": "http://localhost:8080"}},
    })
    result = CliRunner().invoke(env, ["edit", "dev"])
    assert result.exit_code == 1
    assert "No changes specified" in result.output


def test_env_edit_invalid(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["edit", "banana", "--mode", "local"])
    assert result.exit_code == 1
    assert "Invalid environment" in result.output


def test_env_edit_unconfigured(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["edit", "prd", "--mode", "remote"])
    assert result.exit_code == 1
    assert "not configured" in result.output


# --- env delete ---


def test_env_delete_removes_config(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    result = CliRunner().invoke(env, ["delete", "dev", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output
    assert "dev" not in _read_config(config_dir)["environments"]


def test_env_delete_rejects_active(config_dir):
    _write_config(config_dir, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    result = CliRunner().invoke(env, ["delete", "local", "--yes"])
    assert result.exit_code == 1
    assert "Cannot delete active environment" in result.output


def test_env_delete_invalid(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["delete", "banana", "--yes"])
    assert result.exit_code == 1
    assert "Invalid environment" in result.output


def test_env_delete_unconfigured(config_dir):
    _write_config(config_dir, {"env": "local", "environments": {"local": {"mode": "local"}}})
    result = CliRunner().invoke(env, ["delete", "stg", "--yes"])
    assert result.exit_code == 1
    assert "not configured" in result.output
