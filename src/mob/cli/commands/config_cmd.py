"""Config CLI commands."""

import json

import click

from mob.cli.output import console, print_success
from mob.config import get_config_value, load_config, set_config_value


@click.command("configs")
def configs():
    """List all configuration values."""
    config = load_config()
    if not config:
        console.print("[dim]No configuration values set.[/dim]")
        return
    console.print_json(json.dumps(config, default=str))


@click.group("config")
def config():
    """Manage configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value."""
    set_config_value(key, value)
    print_success(f"Config '{key}' set to '{value}'.")


@config.command("get")
@click.argument("key")
def config_get(key: str):
    """Get a configuration value."""
    value = get_config_value(key)
    if value is None:
        console.print(f"[dim]Config key '{key}' not found.[/dim]")
    else:
        console.print(f"{key} = {value}")
