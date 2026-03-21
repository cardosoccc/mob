"""HTTP client for communicating with the mob API."""

import sys
from typing import Any

import httpx

from mob.config import get_settings, is_local_mode


def get_api_url() -> str:
    return get_settings().api_base_url


def _handle_response(resp: httpx.Response) -> Any:
    if resp.status_code == 204:
        return None
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        print(f"Error ({resp.status_code}): {detail}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def api_get(path: str, params: dict | None = None) -> Any:
    if is_local_mode():
        from mob.cli.local_backend import local_request
        return local_request("GET", path, params=params)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.get(url, params=params)
    return _handle_response(resp)


def api_post(path: str, data: dict | None = None) -> Any:
    if is_local_mode():
        from mob.cli.local_backend import local_request
        return local_request("POST", path, data=data)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.post(url, json=data)
    return _handle_response(resp)


def api_put(path: str, data: dict | None = None) -> Any:
    if is_local_mode():
        from mob.cli.local_backend import local_request
        return local_request("PUT", path, data=data)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.put(url, json=data)
    return _handle_response(resp)


def api_delete(path: str) -> Any:
    if is_local_mode():
        from mob.cli.local_backend import local_request
        return local_request("DELETE", path)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.delete(url)
    return _handle_response(resp)
