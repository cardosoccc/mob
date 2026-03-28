"""Resolve CLI resource references by name/identifier or positional index."""

import re
import sys

import click

from mob.cli.client import api_get


# UUID pattern: 8-4-4-4-12 hex characters
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


# Resource type → (list API path, name field used for textual lookup, filter query param name)
_RESOURCE_CONFIG: dict[str, tuple[str, str, str | None]] = {
    "organization": ("/organizations", "identifier", None),
    "domain": ("/domains", "identifier", "organization_id"),
    "user": ("/users", "email", None),
    "skill": ("/skills", "name", None),
    "group": ("/groups", "name", "organization_id"),
    "agent": ("/agents", "name", "domain_id"),
    "session": ("/sessions", "name", "agent_id"),
}


def resolve_ref(resource_type: str, ref: str, **filters: str | None) -> str:
    """Resolve a resource reference to a UUID.

    If ref is all digits, treat as a 1-based positional index into the list.
    If ref looks like a UUID, return it directly.
    Otherwise, look up by the resource's natural key (name/identifier/email).
    """
    config = _RESOURCE_CONFIG.get(resource_type)
    if not config:
        raise click.ClickException(f"Unknown resource type: {resource_type}")

    list_path, name_field, _filter_param = config

    # UUID passthrough
    if _UUID_RE.match(ref):
        return ref

    # Build query params from filters (remove None values)
    params = {k: v for k, v in filters.items() if v is not None}

    # Positional index (all digits)
    if ref.isdigit():
        return _resolve_by_position(resource_type, int(ref), list_path, params)

    # Name/identifier lookup
    return _resolve_by_name(resource_type, ref, list_path, name_field, params)


def _resolve_by_position(
    resource_type: str, position: int, list_path: str, params: dict
) -> str:
    """Resolve a 1-based positional index to a UUID."""
    data = api_get(list_path, params=params or None)
    if not data:
        raise click.ClickException(
            f"No {resource_type}s found (list is empty)."
        )
    if position < 1 or position > len(data):
        raise click.ClickException(
            f"Position {position} is out of range (list has {len(data)} item{'s' if len(data) != 1 else ''})."
        )
    return data[position - 1]["id"]


def _resolve_by_name(
    resource_type: str, name: str, list_path: str, name_field: str, params: dict
) -> str:
    """Resolve a textual name/identifier to a UUID."""
    data = api_get(list_path, params=params or None)
    matches = [item for item in data if item.get(name_field) == name]

    if len(matches) == 1:
        return matches[0]["id"]

    if len(matches) == 0:
        # Try without filters in case the user didn't scope but the name is unique globally
        if params:
            all_data = api_get(list_path)
            all_matches = [item for item in all_data if item.get(name_field) == name]
            if len(all_matches) == 1:
                return all_matches[0]["id"]
            if len(all_matches) > 1:
                _raise_ambiguity_error(resource_type, name, name_field, all_matches)
        raise click.ClickException(
            f"No {resource_type} with {name_field} '{name}' found."
        )

    # Multiple matches — ambiguous
    _raise_ambiguity_error(resource_type, name, name_field, matches)


def _raise_ambiguity_error(
    resource_type: str, name: str, name_field: str, matches: list[dict]
) -> None:
    """Raise an error listing ambiguous matches."""
    config = _RESOURCE_CONFIG[resource_type]
    scope_param = config[2]
    lines = [f"Multiple {resource_type}s match {name_field} '{name}':"]
    for m in matches:
        lines.append(f"  - id={m['id'][:8]}... ({name_field}={m.get(name_field)})")
    if scope_param:
        flag = f"--{scope_param.replace('_', '-').removesuffix('-id')}"
        lines.append(f"Use {flag} to narrow the results.")
    raise click.ClickException("\n".join(lines))


# ── Shared filter decorators ──────────────────────────────────────


def domain_filters(fn):
    """Shared filter options for domain-scoped commands."""
    fn = click.option("--org", "organization_id", help="Filter by organization ID")(fn)
    return fn


def group_filters(fn):
    """Shared filter options for group-scoped commands."""
    fn = click.option("--org", "organization_id", help="Filter by organization ID")(fn)
    return fn


def agent_filters(fn):
    """Shared filter options for agent-scoped commands."""
    fn = click.option("--domain", "domain_id", help="Filter by domain ID")(fn)
    return fn
