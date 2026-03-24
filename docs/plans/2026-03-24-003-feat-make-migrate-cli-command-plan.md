---
title: "feat: Add mob migrate CLI command and make migrate target"
type: feat
status: completed
date: 2026-03-24
---

# feat: Add `mob migrate` CLI command and `make migrate` target

## Overview

Extract schema migration logic from `init_db()` into a standalone `mob migrate` CLI command, and add a `make migrate` Makefile target that calls it. Currently, `_add_missing_columns` runs silently on every request (local mode) and on API startup — there's no way to run it explicitly or see what it did.

## Problem Statement / Motivation

The migration logic (`_add_missing_columns`) is buried inside `init_db()`, which runs automatically on every local CLI request and on API server startup. This has several issues:

1. **No explicit control** — you can't run migrations without also doing `create_all`
2. **Silent execution** — when columns are added or backfilled, there's no output telling you what changed
3. **No `make migrate`** — the Makefile has `setup`, `test`, `build`, `deploy-*` but no migration target
4. **Coupled to init** — the `init` command is an interactive config wizard; users shouldn't have to run it just to migrate

## Proposed Solution

1. Add a `mob migrate` CLI command that runs `create_all` + `_add_missing_columns` with verbose output
2. Extract a `migrate_db()` function from `init_db()` so the migration logic is callable independently
3. Add a `make migrate` Makefile target
4. Keep `init_db()` calling both `create_all` and `_add_missing_columns` so automatic migration on startup continues to work (no behavior change for existing users)

### UX After Implementation

```bash
# Explicit migration with output
mob migrate
# Adding column: agent_runs.name (VARCHAR(255))
# Backfilling agent_runs.name for 6 existing rows
# Migration complete. 1 column added, 6 rows backfilled.

# Or nothing to do
mob migrate
# Database schema is up to date.

# Via Makefile
make migrate
```

## Technical Approach

### 1. Refactor `database.py`

Split `init_db` so migration logic is independently callable:

```python
# src/mob/database.py

async def init_db(database_url: str | None = None) -> None:
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def migrate_db(database_url: str | None = None, verbose: bool = False) -> list[str]:
    """Run schema migrations. Returns list of actions taken."""
    engine = get_engine(database_url)
    actions = []
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(lambda c: _add_missing_columns(c, actions=actions))
    return actions
```

Update `_add_missing_columns` to optionally collect action descriptions:

```python
def _add_missing_columns(conn, actions: list[str] | None = None) -> None:
    # ... existing logic ...
    # When a column is added:
    msg = f"Added column: {table.name}.{column.name} ({col_type})"
    if actions is not None:
        actions.append(msg)
    # When rows are backfilled:
    result = conn.execute(...)
    if result.rowcount and actions is not None:
        actions.append(f"Backfilled {table.name}.{column.name} for {result.rowcount} rows")
```

### 2. Add `mob migrate` CLI command

```python
# src/mob/cli/commands/migrate_cmd.py

import asyncio
import click
from mob.database import migrate_db

@click.command("migrate")
def migrate():
    """Run database schema migrations."""
    actions = asyncio.run(migrate_db())
    if actions:
        for action in actions:
            click.echo(action)
        click.echo(f"\nMigration complete. {len(actions)} action(s).")
    else:
        click.echo("Database schema is up to date.")
```

Register in `src/mob/cli/main.py`:
```python
from mob.cli.commands.migrate_cmd import migrate
cli.add_command(migrate)
```

### 3. Add `make migrate` target

```makefile
## migrate: run database schema migrations
migrate:
	$(UV) run mob migrate
```

**Files touched:**
- `src/mob/database.py` — add `migrate_db()`, update `_add_missing_columns` signature
- `src/mob/cli/commands/migrate_cmd.py` — **new file**
- `src/mob/cli/main.py` — register `migrate` command
- `Makefile` — add `migrate` target

## Acceptance Criteria

- [ ] `mob migrate` runs schema migrations and prints what changed
- [ ] `mob migrate` prints "up to date" when nothing to do
- [ ] `make migrate` works as a Makefile target
- [ ] `init_db()` behavior is unchanged (automatic migration on startup still works)
- [ ] Existing `_add_missing_columns` logic continues to work silently when called from `init_db`

## Dependencies & Risks

- **No risk to existing behavior** — `init_db()` keeps calling both `create_all` and `_add_missing_columns` as before
- **No new dependencies** — uses existing `database.py` functions

## Sources & References

- Migration logic: `src/mob/database.py:42-67`
- Init command: `src/mob/cli/commands/init_cmd.py`
- CLI entry point: `src/mob/cli/main.py`
- Makefile: `Makefile`
