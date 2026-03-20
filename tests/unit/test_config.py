"""Unit tests for config management."""

import json
import os
import tempfile

import pytest

from mob.config import (
    get_config_value,
    get_settings,
    load_config,
    save_config,
    set_config_value,
    Settings,
)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setenv("MOB_CONFIG_FILE", str(config_file))
    return tmp_path


def test_load_config_empty(config_dir):
    config = load_config()
    assert config == {}


def test_save_and_load_config(config_dir):
    save_config({"api_base_url": "http://example.com:8080", "debug": True})
    config = load_config()
    assert config["api_base_url"] == "http://example.com:8080"
    assert config["debug"] is True


def test_set_config_value(config_dir):
    set_config_value("api_host", "myhost")
    assert get_config_value("api_host") == "myhost"


def test_set_config_value_nested(config_dir):
    set_config_value("foo.bar.baz", "hello")
    assert get_config_value("foo.bar.baz") == "hello"


def test_set_config_value_boolean(config_dir):
    set_config_value("debug", "true")
    assert get_config_value("debug") is True


def test_set_config_value_number(config_dir):
    set_config_value("api_port", "9090")
    assert get_config_value("api_port") == 9090


def test_get_config_value_missing(config_dir):
    assert get_config_value("nonexistent") is None


def test_settings_defaults():
    settings = Settings()
    assert settings.api_host == "localhost"
    assert settings.api_port == 8080
    assert settings.debug is False
    assert settings.kubernetes_namespace == "mob"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("MOB_API_PORT", "9999")
    monkeypatch.setenv("MOB_DEBUG", "true")
    settings = Settings()
    assert settings.api_port == 9999
    assert settings.debug is True
