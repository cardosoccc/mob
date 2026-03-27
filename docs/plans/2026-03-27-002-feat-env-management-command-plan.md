---
title: "feat: Add env management CLI command"
type: feat
status: active
date: 2026-03-27
---

# feat: Add env management CLI command

## Overview

Add a dedicated `env` command group and `envs` list command to the MOB CLI for managing environments. Currently, switching environments requires the low-level `mob config set env <name>` which has no validation. The new command provides a first-class, validated interface for switching, inspecting, listing, editing, and deleting environment configurations.

## Problem Statement / Motivation

- Switching environments via `mob config set env banana` silently succeeds with invalid values, leading to confusing downstream failures
- No quick way to see the active environment or inspect a specific environment's config
- No way to delete or edit an environment's configuration without manually editing `~/.mob/config.json`
- The `init` command output (line 129 of `init_cmd.py`) tells users to run `mob config set env <name>` — not intuitive

## Proposed Solution

Create `src/mob/cli/commands/env_cmd.py` with:

- **`mob env <name>`** — switch active environment (validated)
- **`mob env show [name]`** — show environment config (defaults to active)
- **`mob env list`** — list all environments
- **`mob env edit <name>`** — edit environment config via flags
- **`mob env delete <name>`** — delete environment config (with confirmation)
- **`mob envs`** — top-level list command (alias for `mob env list`)

Follow the existing dual-command pattern (`envs` + `env` group) consistent with `orgs`/`org`, `configs`/`config`, etc.

## Technical Considerations

### Architecture

- **Config-file-only command** — no API client, resolver, or local_backend needed. Analogous to `config_cmd.py` and `init_cmd.py`.
- **File naming**: `env_cmd.py` using the `_cmd` suffix convention (avoids shadowing the `env` builtin/common name, same pattern as `config_cmd.py`).
- **Reuses existing config helpers**: `load_config()`, `save_config()`, `get_active_env()`, `VALID_ENVS`, `ENV_DEFAULTS` from `src/mob/config.py`.

### Key Design Decisions

1. **Switching to unconfigured env is refused** — `mob env prd` errors with "Environment 'prd' not configured. Run `mob init prd` first." This prevents silent failures from empty `api_base_url` defaults.
2. **Deleting the active env is refused** — `mob env delete local` errors with "Cannot delete active environment. Switch to another env first."
3. **`mob env show` accepts optional argument** — `mob env show` shows active env, `mob env show dev` shows dev's config regardless of active env.
4. **`mob env edit` is flag-based** (not interactive) — follows the existing edit pattern in `org.py`, `domain.py`, etc.

### Interaction with Existing Commands

- `mob config set env <name>` remains functional but should gain `VALID_ENVS` validation
- `init_cmd.py` line 129 should be updated to reference `mob env <name>` instead of `mob config set env <name>`

## Acceptance Criteria

- [ ] `mob env local` / `mob env dev` / `mob env stg` / `mob env prd` switches the active environment
- [ ] `mob env <invalid>` shows error with valid options
- [ ] `mob env <unconfigured>` refuses and suggests `mob init <name>`
- [ ] `mob env show` displays active environment name + config
- [ ] `mob env show <name>` displays a specific environment's config
- [ ] `mob env show <unconfigured>` shows error
- [ ] `mob envs` lists all VALID_ENVS with columns: name, mode, configured (yes/no), active marker
- [ ] `mob env list` produces identical output to `mob envs`
- [ ] `mob env delete <name>` removes environment config after confirmation
- [ ] `mob env delete <active_env>` is rejected with a clear error
- [ ] `mob env delete <unconfigured>` shows error
- [ ] `mob env edit <name>` updates specific fields via `--mode`, `--database-url`, `--api-base-url`
- [ ] `mob env edit <unconfigured>` shows error
- [ ] `mob config set env <name>` validates against VALID_ENVS
- [ ] `init_cmd.py` hint updated to reference `mob env <name>`
- [ ] Unit tests cover all subcommands and edge cases
- [ ] Integration tests with CliRunner

## Success Metrics

- Users can switch, inspect, and manage environments without editing JSON manually
- Invalid environment names are caught at the CLI layer, not as downstream failures
- Consistent UX with existing mob CLI patterns

## Dependencies & Risks

- **No external dependencies** — purely config-file operations using existing helpers
- **Risk: `env` group default command** — Click doesn't natively support `mob env local` as both a group and having positional subcommands. Solution: use `@env.command()` for each subcommand and implement the switch as `mob env set <name>` OR use `click.Group` with `invoke_without_command` + result callback. See MVP below for the recommended approach.
- **Risk: Dual path for env switching** — `mob config set env` and `mob env <name>` coexist. Mitigated by adding validation to `set_config_value` for the `env` key.

## MVP

### `src/mob/cli/commands/env_cmd.py`

```python
"""Environment management CLI commands."""

import click

from mob.cli.output import console, print_detail, print_error, print_success, print_table
from mob.config import ENV_DEFAULTS, VALID_ENVS, load_config, save_config


def _get_env_config(config: dict, env_name: str) -> dict | None:
    """Get a specific environment's config, or None if not configured."""
    return config.get("environments", {}).get(env_name)


def _require_configured(config: dict, env_name: str) -> dict:
    """Get env config or exit with error if not configured."""
    env_config = _get_env_config(config, env_name)
    if env_config is None:
        print_error(
            f"Environment '{env_name}' not configured. "
            f"Run 'mob init {env_name}' first."
        )
        raise SystemExit(1)
    return env_config


@click.command("envs")
def envs():
    """List all environments."""
    _list_envs()


def _list_envs():
    """Shared implementation for envs list."""
    config = load_config()
    active_env = config.get("env", "local")
    environments = config.get("environments", {})

    rows = []
    for env_name in VALID_ENVS:
        env_config = environments.get(env_name)
        rows.append({
            "name": f"* {env_name}" if env_name == active_env else f"  {env_name}",
            "mode": env_config.get("mode", "-") if env_config else "-",
            "configured": "yes" if env_config else "no",
        })

    print_table(rows, columns=["name", "mode", "configured"])


@click.group("env")
def env():
    """Manage environments."""
    pass


@env.command("set")
@click.argument("name")
def env_set(name: str):
    """Switch the active environment.

    \b
    Examples:
        mob env set local
        mob env set dev
        mob env set stg
        mob env set prd
    """
    if name not in VALID_ENVS:
        print_error(
            f"Invalid environment '{name}'. "
            f"Valid options: {', '.join(VALID_ENVS)}"
        )
        raise SystemExit(1)

    config = load_config()
    _require_configured(config, name)

    config["env"] = name
    save_config(config)
    print_success(f"Switched to environment '{name}'.")


@env.command("show")
@click.argument("name", required=False, default=None)
def env_show(name: str | None):
    """Show environment configuration.

    Without arguments, shows the active environment.
    With a name, shows that specific environment's config.
    """
    config = load_config()

    if name is None:
        name = config.get("env", "local")
        console.print(f"[bold]Active environment:[/bold] {name}")
    else:
        if name not in VALID_ENVS:
            print_error(
                f"Invalid environment '{name}'. "
                f"Valid options: {', '.join(VALID_ENVS)}"
            )
            raise SystemExit(1)

    env_config = _require_configured(config, name)
    print_detail(env_config)


@env.command("list")
def env_list():
    """List all environments."""
    _list_envs()


@env.command("edit")
@click.argument("name")
@click.option("--mode", type=click.Choice(["local", "remote"]), help="Environment mode.")
@click.option("--database-url", help="Database connection URL.")
@click.option("--api-base-url", help="API base URL (for remote mode).")
def env_edit(name: str, mode: str | None, database_url: str | None, api_base_url: str | None):
    """Edit an environment's configuration.

    \b
    Examples:
        mob env edit dev --api-base-url http://api.dev.example.com
        mob env edit local --database-url sqlite+aiosqlite:///path/to/db
        mob env edit stg --mode remote --api-base-url https://api.stg.example.com
    """
    if name not in VALID_ENVS:
        print_error(
            f"Invalid environment '{name}'. "
            f"Valid options: {', '.join(VALID_ENVS)}"
        )
        raise SystemExit(1)

    config = load_config()
    env_config = _require_configured(config, name)

    updates = {}
    if mode is not None:
        updates["mode"] = mode
    if database_url is not None:
        updates["database_url"] = database_url
    if api_base_url is not None:
        updates["api_base_url"] = api_base_url

    if not updates:
        print_error("No changes specified. Use --mode, --database-url, or --api-base-url.")
        raise SystemExit(1)

    env_config.update(updates)
    config["environments"][name] = env_config
    save_config(config)

    print_success(f"Environment '{name}' updated.")
    print_detail(env_config)


@env.command("delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this environment?")
def env_delete(name: str):
    """Delete an environment's configuration.

    \b
    Examples:
        mob env delete stg
        mob env delete prd
    """
    if name not in VALID_ENVS:
        print_error(
            f"Invalid environment '{name}'. "
            f"Valid options: {', '.join(VALID_ENVS)}"
        )
        raise SystemExit(1)

    config = load_config()
    active_env = config.get("env", "local")

    if name == active_env:
        print_error(
            f"Cannot delete active environment '{name}'. "
            f"Switch to another environment first with 'mob env set <name>'."
        )
        raise SystemExit(1)

    _require_configured(config, name)

    del config["environments"][name]
    save_config(config)
    print_success(f"Environment '{name}' deleted.")
```

### Changes to `src/mob/cli/main.py`

```python
# Add import
from mob.cli.commands.env_cmd import env, envs

# Add registrations
cli.add_command(envs)
cli.add_command(env)
```

### Changes to `src/mob/config.py` — validate `env` key in `set_config_value`

```python
def set_config_value(key: str, value: str) -> None:
    config = load_config()
    keys = key.split(".")
    # Validate 'env' key against VALID_ENVS
    if keys == ["env"] and value not in VALID_ENVS:
        msg = f"Invalid environment '{value}'. Valid options: {', '.join(VALID_ENVS)}"
        raise ValueError(msg)
    # ... rest unchanged
```

### Changes to `src/mob/cli/commands/init_cmd.py` — update hint text

```python
# Line 129: change the hint message
f"[dim]Use 'mob env set <name>' to switch environments.[/dim]"
```

### `tests/unit/test_env_cmd.py`

```python
"""Tests for env CLI commands."""

import json
from click.testing import CliRunner
from mob.cli.commands.env_cmd import env, envs


def _write_config(tmp_path, config):
    """Write a config file and return the path."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


def test_env_set_switches_environment(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote", "api_base_url": "http://localhost:8080"}},
    })
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["set", "dev"])
    assert result.exit_code == 0
    assert "Switched to environment 'dev'" in result.output


def test_env_set_rejects_invalid(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {"env": "local", "environments": {"local": {"mode": "local"}}})
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["set", "banana"])
    assert result.exit_code == 1
    assert "Invalid environment" in result.output


def test_env_set_rejects_unconfigured(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {"env": "local", "environments": {"local": {"mode": "local"}}})
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["set", "prd"])
    assert result.exit_code == 1
    assert "not configured" in result.output


def test_env_show_active(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {
        "env": "local",
        "environments": {"local": {"mode": "local", "database_url": "sqlite:///test.db"}},
    })
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["show"])
    assert result.exit_code == 0
    assert "local" in result.output


def test_env_show_specific(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote", "api_base_url": "http://localhost:8080"}},
    })
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["show", "dev"])
    assert result.exit_code == 0
    assert "remote" in result.output


def test_envs_lists_all(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(envs)
    assert result.exit_code == 0
    assert "local" in result.output
    assert "dev" in result.output


def test_env_delete_rejects_active(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {
        "env": "local",
        "environments": {"local": {"mode": "local"}, "dev": {"mode": "remote"}},
    })
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["delete", "local", "--yes"])
    assert result.exit_code == 1
    assert "Cannot delete active environment" in result.output


def test_env_edit_updates_field(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, {
        "env": "dev",
        "environments": {"dev": {"mode": "remote", "api_base_url": "http://localhost:8080"}},
    })
    monkeypatch.setenv("MOB_CONFIG_FILE", config_path)

    runner = CliRunner()
    result = runner.invoke(env, ["edit", "dev", "--api-base-url", "http://new-url:8080"])
    assert result.exit_code == 0
    assert "updated" in result.output

    config = json.loads((tmp_path / "config.json").read_text())
    assert config["environments"]["dev"]["api_base_url"] == "http://new-url:8080"
```

## Sources & References

### Internal References

- CLI dual-command pattern: `src/mob/cli/commands/org.py`
- Config helpers: `src/mob/config.py:14` (`VALID_ENVS`), `src/mob/config.py:16` (`ENV_DEFAULTS`)
- Existing config commands: `src/mob/cli/commands/config_cmd.py`
- Init environment prompts: `src/mob/cli/commands/init_cmd.py`
- Output utilities: `src/mob/cli/output.py`
- Command registration: `src/mob/cli/main.py`

### Institutional Learnings

- Local mode pod IPs not routable from host — consider surfacing this when showing local env config
- Kind inotify limits must be checked — relevant context for local/dev env setup
