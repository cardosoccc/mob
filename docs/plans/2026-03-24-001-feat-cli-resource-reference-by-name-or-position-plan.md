---
title: "feat: CLI resource reference by name or positional index"
type: feat
status: completed
date: 2026-03-24
---

# feat: CLI resource reference by name or positional index

## Overview

Replace raw UUID arguments in all CLI action subcommands (`show`, `edit`, `delete`, etc.) with a **smart reference resolver** that accepts either:

1. **A textual name/identifier** — resolved to the resource's unique natural key (e.g., `mob org show acme-corp`)
2. **A positional integer** — resolved to the Nth row in the listing produced by the same filters the user would pass to the list command (e.g., `mob org show 2` → second org in `mob orgs`)

Action subcommands (`edit`, `delete`, `show`, and resource-specific actions like `agent run`) accept the **same filter/sort options** as their corresponding list commands so that a positional index matches exactly what the user saw.

## Problem Statement / Motivation

Currently every action subcommand requires a UUID:

```
mob org show 3f8a1b2c-...
mob agent delete 9e4d7f6a-...
```

The table output truncates UUIDs to 8 characters, so users must run `mob orgs`, find the row, then copy the full UUID from `mob org show <short-id>` or the database. This is painful, error-prone, and hostile to interactive CLI workflows.

## Proposed Solution

### 1. Reference Resolver Module

Create `src/mob/cli/resolver.py` — a single module that all action commands delegate to for turning a `REF` argument into a UUID.

**Resolution logic:**

```
if REF is all digits → positional index (1-based)
else               → name/identifier lookup
```

**Positional resolution:** call the same list endpoint/service with the same filter params, then pick the Nth item. Error if N is out of range.

**Name resolution per resource type:**

| Resource     | Textual field | Unique?                          | Scoping required         |
|-------------|---------------|----------------------------------|--------------------------|
| Organization | `identifier`  | Globally unique                  | None                     |
| Domain       | `identifier`  | Globally unique                  | None                     |
| User         | `email`       | Globally unique                  | None                     |
| Skill        | `name`        | Globally unique                  | None                     |
| Group        | `name`        | Unique within org (`uq_group_name_org`) | `--org` required   |
| Agent        | `name`        | **Not unique**                   | `--domain` required      |

For scoped resources (Group, Agent), if the textual ref is provided without the required scope flag, the resolver should:
1. Attempt lookup without scope
2. If exactly one match → use it
3. If multiple matches → error with a message listing the matches and asking the user to provide `--org` or `--domain`
4. If zero matches → "not found" error

### 2. Row Number Column in List Output

Add a **`#` column** (1-based row number) as the first column in all `print_table` output so the user can see which positional index to use.

**Before:**
```
ID        IDENTIFIER   NAME        CREATED AT
3f8a1b2c  acme-corp    Acme Corp   2026-03-20
9e4d7f6a  widgets-inc  Widgets     2026-03-21
```

**After:**
```
#  ID        IDENTIFIER   NAME        CREATED AT
1  3f8a1b2c  acme-corp    Acme Corp   2026-03-20
2  9e4d7f6a  widgets-inc  Widgets     2026-03-21
```

### 3. Shared Filter Options via Click Decorator

Create shared option decorators so list commands and action commands share the same filter options without duplication.

**Example for domains:**

```python
# src/mob/cli/resolver.py

def domain_filters(fn):
    """Shared filter options for domain list and action commands."""
    fn = click.option("--org", "organization_id", help="Filter by organization ID")(fn)
    return fn
```

**Usage in commands:**

```python
# List command
@click.command("domains")
@domain_filters
def domains(organization_id):
    ...

# Action commands
@domain.command("show")
@click.argument("ref")
@domain_filters
def domain_show(ref, organization_id):
    domain_id = resolve_ref("domain", ref, organization_id=organization_id)
    ...
```

### 4. Service Layer: Add `find_by_name` Queries

Add lookup-by-natural-key functions to relevant service modules. These are thin wrappers around existing queries.

**Files to modify:**

| Service file                        | New function                                      |
|------------------------------------|--------------------------------------------------|
| `src/mob/services/organizations.py` | `find_organization_by_identifier(session, ident)` |
| `src/mob/services/domains.py`       | `find_domain_by_identifier(session, ident)`       |
| `src/mob/services/users.py`         | `find_user_by_email(session, email)`              |
| `src/mob/services/skills.py`        | `find_skill_by_name(session, name)`               |
| `src/mob/services/groups.py`        | `find_groups_by_name(session, name, org_id=None)` |
| `src/mob/services/agents.py`        | `find_agents_by_name(session, name, domain_id=None)` |

Each returns the model or raises `ServiceError(404)`. For scoped lookups (groups, agents), returns a list when unscoped.

### 5. Local Backend Route Updates

Update `src/mob/cli/local_backend.py` to support lookup by identifier/name in addition to UUID. The resolver calls the list endpoint + indexing for positional refs, and the new `find_by_*` service functions for name refs.

Two approaches for the local backend:
- **Option A (simpler):** The resolver always works at the CLI layer — it calls the list API, picks the item, extracts the UUID, then passes the UUID to the existing action endpoint. No backend route changes needed.
- **Option B:** Add name-based lookup routes to the API.

**Recommendation: Option A.** The resolver is purely a CLI convenience layer. The API continues to work with UUIDs. This keeps the API clean and avoids duplicating resolution logic.

### 6. Command Signature Changes

Every action subcommand changes its `ARGUMENT` from a specific `*_id` to a generic `ref`:

**Before:**
```python
@domain.command("show")
@click.argument("domain_id")
def domain_show(domain_id: str):
    data = api_get(f"/domains/{domain_id}")
```

**After:**
```python
@domain.command("show")
@click.argument("ref")
@domain_filters
def domain_show(ref: str, organization_id: str | None):
    domain_id = resolve_ref("domain", ref, organization_id=organization_id)
    data = api_get(f"/domains/{domain_id}")
```

## Technical Considerations

### Architecture

- The resolver is a **CLI-only concern**. The API and service layers continue to use UUIDs as primary keys.
- The resolver module is stateless — it makes API/service calls on every invocation (no caching).
- Local mode and remote mode both work because the resolver uses the same `api_get`/`local_request` client functions.

### Performance

- Positional resolution requires fetching the full list. For most mob deployments this is fine (dozens to low hundreds of resources). If this becomes a concern, pagination + offset can be added later.
- Name resolution is a single query with an indexed column — negligible overhead.

### Edge Cases

- **Numeric identifiers:** If an org has identifier `"123"`, typing `mob org show 123` would be ambiguous. Resolution: always treat all-digit input as a positional index. Users who have numeric identifiers must use the full identifier with a prefix hint (e.g., `mob org show id:123`) or use the show-by-position workflow. **For v1, document this limitation.** A future `name:` / `#:` prefix syntax can be added if needed.
- **Deleted rows shifting positions:** Positional indices are ephemeral — they reflect the current list at the time of the command. This is inherent and acceptable (same as `kill %1` in job control).
- **Empty list:** Position `1` on an empty list → clear error message.
- **Agent name scoping:** Agent names are not unique even within a domain. The resolver should match by name + domain_id filter. If the user doesn't provide `--domain`, try matching globally; error on ambiguity.

### Security

- No new auth/authz concerns — the resolver just calls existing endpoints.
- No injection risk — identifiers are validated by existing Pydantic schemas and SQLAlchemy parameterized queries.

## System-Wide Impact

- **Interaction graph:** CLI commands → resolver → `api_get` (list endpoint) or service `find_by_*` → existing DB queries. No new callbacks or side effects.
- **Error propagation:** Resolver raises `click.ClickException` for user-facing errors (not found, ambiguous, out of range). Service layer `ServiceError` is caught as before.
- **State lifecycle risks:** None — resolver is read-only for resolution, then delegates to existing write paths.
- **API surface parity:** The API (FastAPI routes) is unchanged. Only CLI commands gain the new reference syntax.
- **Integration test scenarios:**
  1. `mob org show acme-corp` resolves to correct UUID via identifier
  2. `mob org show 1` resolves to first org in default listing
  3. `mob agent show my-agent --domain <dom-id>` resolves scoped agent name
  4. `mob agent show 2 --domain <dom-id>` resolves positional within filtered list
  5. `mob group show eng` with two "eng" groups in different orgs → ambiguity error

## Acceptance Criteria

### Functional Requirements

- [ ] All action subcommands (`show`, `edit`, `delete` + resource-specific: `agent run`, `agent stop`, `agent logs`, `user grant`, `user revoke`) accept a `REF` that is either a name/identifier or a 1-based positional index
- [ ] Positional index resolution uses the same filters as the corresponding list command
- [ ] List output (`print_table`) shows a `#` column as the first column
- [ ] Resources with globally unique natural keys (org→identifier, domain→identifier, user→email, skill→name) resolve without extra flags
- [ ] Scoped resources (group→name+org, agent→name+domain) require scope flags when ambiguous, with a helpful error message listing matches
- [ ] All-digit input is always interpreted as a positional index
- [ ] Out-of-range positional index produces a clear error: `"Position 5 is out of range (list has 3 items)"`
- [ ] Name not found produces a clear error: `"No organization with identifier 'foo-bar' found"`
- [ ] Action subcommands share the same filter options as their list counterparts (via shared decorators)

### Non-Functional Requirements

- [ ] No changes to the FastAPI routes or API contract
- [ ] No database migrations required
- [ ] Backward compatible — passing a full UUID still works (treated as a name lookup, matches the `id` field as fallback)

### Quality Gates

- [ ] Unit tests for `resolve_ref` covering: name resolution, positional resolution, ambiguity errors, out-of-range errors, UUID fallback
- [ ] Integration tests for at least org and agent (one unscoped, one scoped resource)
- [ ] Existing tests continue to pass

## Implementation Phases

### Phase 1: Core Resolver + Row Numbers

**Files to create:**
- `src/mob/cli/resolver.py` — `resolve_ref()` function + shared filter decorators

**Files to modify:**
- `src/mob/cli/output.py` — add `#` column to `print_table`
- `src/mob/services/organizations.py` — add `find_organization_by_identifier()`
- `src/mob/services/domains.py` — add `find_domain_by_identifier()`
- `src/mob/services/users.py` — add `find_user_by_email()`
- `src/mob/services/skills.py` — add `find_skill_by_name()`
- `src/mob/services/groups.py` — add `find_groups_by_name()`
- `src/mob/services/agents.py` — add `find_agents_by_name()`

**Tests:**
- `tests/unit/test_resolver.py`

### Phase 2: Wire All Commands

**Files to modify:**
- `src/mob/cli/commands/org.py` — `show`, `edit`, `delete` accept `ref` + use resolver
- `src/mob/cli/commands/domain.py` — `show`, `edit`, `delete` accept `ref` + shared `--org` filter
- `src/mob/cli/commands/user.py` — `show`, `edit`, `delete`, `grant`, `revoke` accept `ref`
- `src/mob/cli/commands/group.py` — `show`, `edit`, `delete` accept `ref` + shared `--org` filter
- `src/mob/cli/commands/agent.py` — `show`, `edit`, `delete`, `run`, `stop`, `logs`, `attach`, `send` accept `ref` + shared `--domain` filter
- `src/mob/cli/commands/skill.py` — `edit`, `delete` accept `ref`

**Tests:**
- `tests/unit/test_cli_commands_resolver.py` — end-to-end CLI invocation tests
- Update `tests/integration/test_cli_integration.py` if it tests action commands

### Phase 3: UUID Fallback + Polish

- Ensure that if the textual ref looks like a UUID (contains hyphens, 36 chars), it's tried as a direct ID lookup first before name resolution
- Add `--help` text explaining the ref syntax to each command
- Document the "all-digit identifiers" limitation

## Sources & References

### Internal References

- CLI entry point: `src/mob/cli/main.py`
- Output formatting: `src/mob/cli/output.py:21` (`print_table`)
- Existing command pattern: `src/mob/cli/commands/org.py`
- Service lookup pattern: `src/mob/services/organizations.py:52` (`get_organization`)
- Model unique constraints: `src/mob/models/organization.py:13` (`identifier` unique index), `src/mob/models/group.py:25` (`uq_group_name_org`)
- Local backend routing: `src/mob/cli/local_backend.py`

### Technology

- Click (CLI framework): v8.1+
- SQLAlchemy async: v2.0+
- Rich (table output): v13.7+
