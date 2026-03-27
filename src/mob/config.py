"""Configuration management for mob."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


DEFAULT_CONFIG_DIR = Path.home() / ".mob"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"

VALID_ENVS = ("local", "dev", "stg", "prd")

ENV_DEFAULTS = {
    "local": {
        "mode": "local",
        "database_url": f"sqlite+aiosqlite:///{DEFAULT_CONFIG_DIR / 'mob.db'}",
    },
    "dev": {
        "mode": "remote",
        "api_base_url": "http://localhost:8080",
    },
    "stg": {
        "mode": "remote",
        "api_base_url": "",
    },
    "prd": {
        "mode": "remote",
        "api_base_url": "",
    },
}


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_CONFIG_DIR / 'mob.db'}"
    api_host: str = "localhost"
    api_port: int = 8080
    api_base_url: str = "http://localhost:8080"
    kubeconfig: str | None = None
    kubernetes_namespace: str = "mob"
    keycloak_url: str | None = None
    keycloak_realm: str = "mob"
    debug: bool = False
    mode: str = "local"

    model_config = {"env_prefix": "MOB_"}


def get_config_path() -> Path:
    return Path(os.environ.get("MOB_CONFIG_FILE", str(DEFAULT_CONFIG_FILE)))


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_config(config: dict[str, Any]) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")


def get_active_env() -> str:
    """Get the currently active environment name."""
    config = load_config()
    return config.get("env", "local")


def get_active_env_config() -> dict[str, Any]:
    """Get the configuration for the currently active environment."""
    config = load_config()
    env = config.get("env", "local")
    environments = config.get("environments", {})
    return environments.get(env, ENV_DEFAULTS.get(env, {}))


def is_local_mode() -> bool:
    """Check if the current environment runs in local mode (direct DB, no API)."""
    env_config = get_active_env_config()
    return env_config.get("mode", "local") == "local"


def get_config_value(key: str) -> Any:
    config = load_config()
    keys = key.split(".")
    current = config
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return current


def set_config_value(key: str, value: str) -> None:
    config = load_config()
    keys = key.split(".")
    # Validate 'env' key against VALID_ENVS
    if keys == ["env"] and value not in VALID_ENVS:
        msg = f"Invalid environment '{value}'. Valid options: {', '.join(VALID_ENVS)}"
        raise ValueError(msg)
    current = config
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    # Try to parse as JSON for booleans, numbers, etc.
    try:
        parsed = json.loads(value)
        current[keys[-1]] = parsed
    except (json.JSONDecodeError, ValueError):
        current[keys[-1]] = value
    save_config(config)


def get_settings() -> Settings:
    """Build Settings from the active environment config + env var overrides."""
    env_config = get_active_env_config()

    # Environment variable overrides take precedence
    env_overrides = {}
    for key in Settings.model_fields:
        env_key = f"MOB_{key.upper()}"
        if env_key in os.environ:
            env_overrides[key] = os.environ[env_key]

    merged = {**env_config, **env_overrides}
    return Settings(**{k: v for k, v in merged.items() if k in Settings.model_fields})
