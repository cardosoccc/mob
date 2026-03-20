"""Configuration management for mob."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


DEFAULT_CONFIG_DIR = Path.home() / ".mob"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///mob.db"
    api_host: str = "localhost"
    api_port: int = 8080
    api_base_url: str = "http://localhost:8080"
    kubeconfig: str | None = None
    kubernetes_namespace: str = "mob"
    keycloak_url: str | None = None
    keycloak_realm: str = "mob"
    debug: bool = False

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
    config = load_config()
    env_overrides = {}
    for key in Settings.model_fields:
        env_key = f"MOB_{key.upper()}"
        if env_key in os.environ:
            env_overrides[key] = os.environ[env_key]
    merged = {**config, **env_overrides}
    return Settings(**{k: v for k, v in merged.items() if k in Settings.model_fields})
