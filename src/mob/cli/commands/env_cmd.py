"""Environment management CLI commands."""

import click

from mob.cli.output import console, print_detail, print_error, print_success, print_table
from mob.config import VALID_ENVS, load_config, save_config


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


def _validate_env_name(name: str) -> None:
    """Validate environment name is in VALID_ENVS or exit."""
    if name not in VALID_ENVS:
        print_error(
            f"Invalid environment '{name}'. "
            f"Valid options: {', '.join(VALID_ENVS)}"
        )
        raise SystemExit(1)


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


@click.command("envs")
def envs():
    """List all environments."""
    _list_envs()


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
    _validate_env_name(name)

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
        _validate_env_name(name)

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
    _validate_env_name(name)

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
    _validate_env_name(name)

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
