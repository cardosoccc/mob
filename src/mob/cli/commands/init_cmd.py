"""Init command - initialize environment configurations."""

import click

from mob.cli.output import console, print_success
from mob.config import (
    DEFAULT_CONFIG_DIR,
    ENV_DEFAULTS,
    VALID_ENVS,
    load_config,
    save_config,
)


def _prompt_local_env() -> dict:
    """Prompt for local environment configuration."""
    console.print("\n[bold]Configuring 'local' environment[/bold]")
    console.print("[dim]Local mode uses SQLite directly - no API server needed.[/dim]")

    default_db = f"sqlite+aiosqlite:///{DEFAULT_CONFIG_DIR / 'mob.db'}"
    database_url = click.prompt("Database URL", default=default_db)

    return {
        "mode": "local",
        "database_url": database_url,
    }


def _prompt_remote_env(env_name: str) -> dict:
    """Prompt for a remote environment configuration."""
    labels = {"dev": "development", "stg": "staging", "prd": "production"}
    label = labels.get(env_name, env_name)

    console.print(f"\n[bold]Configuring '{env_name}' ({label}) environment[/bold]")

    if env_name == "dev":
        console.print(
            "[dim]Dev mode simulates production locally - uses API + database.[/dim]"
        )
        default_url = ENV_DEFAULTS["dev"]["api_base_url"]
    else:
        console.print(
            f"[dim]Remote environment pointing to your {label} API server.[/dim]"
        )
        default_url = ENV_DEFAULTS.get(env_name, {}).get("api_base_url", "")

    api_base_url = click.prompt("API base URL", default=default_url or None)

    env_config: dict = {
        "mode": "remote",
        "api_base_url": api_base_url,
    }

    if env_name == "dev":
        database_url = click.prompt(
            "Database URL (for local API server)",
            default="postgresql+asyncpg://mob_admin:localdev@localhost:5432/mob",
        )
        env_config["database_url"] = database_url

    return env_config


def _init_env(env_name: str) -> dict:
    """Initialize a single environment by prompting the user."""
    if env_name == "local":
        return _prompt_local_env()
    return _prompt_remote_env(env_name)


@click.command("init")
@click.argument("env", required=False, default=None)
def init(env: str | None):
    """Initialize environment configurations.

    Without arguments, initializes all environments (local, dev, stg, prd).
    With an argument, initializes only the specified environment.

    \b
    Examples:
        mob init          # Initialize all environments
        mob init local    # Initialize only local environment
        mob init dev      # Initialize only dev environment
        mob init stg      # Initialize only staging environment
        mob init prd      # Initialize only production environment
    """
    if env is not None and env not in VALID_ENVS:
        console.print(
            f"[red]Invalid environment '{env}'. "
            f"Valid options: {', '.join(VALID_ENVS)}[/red]"
        )
        raise SystemExit(1)

    config = load_config()
    environments = config.get("environments", {})

    console.print("[bold]mob - Environment Initialization[/bold]")

    if env is None:
        # Initialize all environments
        envs_to_init = list(VALID_ENVS)
    else:
        envs_to_init = [env]

    for env_name in envs_to_init:
        if env_name in environments:
            if not click.confirm(
                f"\nEnvironment '{env_name}' already configured. Overwrite?"
            ):
                continue
        environments[env_name] = _init_env(env_name)
        print_success(f"Environment '{env_name}' configured.")

    config["environments"] = environments

    # Set default active env if not set
    if "env" not in config:
        if "local" in environments:
            config["env"] = "local"
        elif envs_to_init:
            config["env"] = envs_to_init[0]

    save_config(config)

    console.print(f"\n[bold]Active environment:[/bold] {config.get('env', 'local')}")
    console.print(
        f"[dim]Config saved to {config}[/dim]"
        if False
        else f"[dim]Use 'mob env set <name>' to switch environments.[/dim]"
    )
