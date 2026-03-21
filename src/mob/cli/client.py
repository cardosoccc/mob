"""HTTP client for communicating with the mob API."""

import asyncio
import json
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


def _local_request(method: str, path: str, data: dict | None = None, params: dict | None = None) -> Any:
    """Make a request to the FastAPI app in-process using ASGITransport."""
    async def _call():
        from mob.api.app import create_app
        from mob.database import close_db, init_db

        await init_db()

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://local") as client:
            url = f"/api/v1{path}"
            if method == "GET":
                resp = await client.get(url, params=params)
            elif method == "POST":
                resp = await client.post(url, json=data)
            elif method == "PUT":
                resp = await client.put(url, json=data)
            elif method == "DELETE":
                resp = await client.delete(url)
            else:
                raise ValueError(f"Unsupported method: {method}")

        await close_db()
        return resp

    resp = asyncio.run(_call())
    return _handle_response(resp)


def api_get(path: str, params: dict | None = None) -> Any:
    if is_local_mode():
        return _local_request("GET", path, params=params)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.get(url, params=params)
    return _handle_response(resp)


def api_post(path: str, data: dict | None = None) -> Any:
    if is_local_mode():
        return _local_request("POST", path, data=data)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.post(url, json=data)
    return _handle_response(resp)


def api_put(path: str, data: dict | None = None) -> Any:
    if is_local_mode():
        return _local_request("PUT", path, data=data)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.put(url, json=data)
    return _handle_response(resp)


def api_delete(path: str) -> Any:
    if is_local_mode():
        return _local_request("DELETE", path)
    url = f"{get_api_url()}/api/v1{path}"
    with httpx.Client() as client:
        resp = client.delete(url)
    return _handle_response(resp)
