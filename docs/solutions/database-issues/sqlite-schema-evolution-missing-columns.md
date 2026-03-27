---
title: SQLite Schema Evolution - Missing Columns After Model Changes
category: database-issues
date: 2026-03-24
tags:
  - sqlite
  - sqlalchemy
  - schema-migration
  - create-all
  - backward-compatibility
severity: high
component: database/initialization
symptoms:
  - "sqlite3.OperationalError: no such column: sessions.name"
  - CLI commands crash after adding new columns to SQLAlchemy models
  - Application works on fresh databases but fails on existing ones
---

# SQLite Schema Evolution - Missing Columns After Model Changes

## Problem

After adding a new column to a SQLAlchemy model (e.g., `name` on `Session`), running any command that queries that table on an **existing** SQLite database crashes:

```
sqlite3.OperationalError: no such column: sessions.name
[SQL: SELECT sessions.id, sessions.name, sessions.agent_id, ...]
```

The error only occurs on databases created before the column was added. Fresh databases work fine.

## Root Cause

SQLAlchemy's `Base.metadata.create_all()` is idempotent for **tables** but not for **columns**. It:
- Creates tables that don't exist
- Does **NOT** add columns to tables that already exist
- Does **NOT** modify column definitions on existing tables

SQLite makes this worse because it cannot:
- Add NOT NULL columns without a default to tables with existing rows
- Alter column constraints after creation (no `ALTER COLUMN`)

## Investigation Steps

1. `mob sessions` crashed immediately after the `name` column was added to `Session` model
2. Fresh test databases (in-memory SQLite) passed all tests — the column existed because `create_all` created the table from scratch
3. The local dev database (file-based SQLite) failed because the `sessions` table already existed without the `name` column
4. Confirmed `create_all` silently skips existing tables by checking SQLAlchemy source

## Solution

### 1. `_add_missing_columns()` function in `database.py`

Inspects every table, compares model columns to actual database columns, and adds any missing ones:

```python
def _add_missing_columns(conn, actions: list[str] | None = None) -> None:
    inspector = inspect(conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing:
                col_type = column.type.compile(conn.dialect)
                # Always add as nullable to avoid errors on existing rows
                conn.execute(text(
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"
                ))
                # Backfill NULLs for NOT NULL columns
                if not column.nullable:
                    result = conn.execute(text(
                        f"UPDATE {table.name} SET {column.name} = "
                        f"'{table.name}-' || substr(id, 1, 8) "
                        f"WHERE {column.name} IS NULL"
                    ))
```

Key design decisions:
- **Always add as nullable first** — SQLite can't add NOT NULL to tables with rows
- **Backfill with `{table}-{id[:8]}`** — gives existing rows a unique-ish value for NOT NULL columns
- **Optional `actions` list** — when provided, records what was done for verbose output

### 2. Runs automatically on startup

`init_db()` calls `_add_missing_columns()` after `create_all()`, so existing databases are silently fixed on every app start:

```python
async def init_db(database_url: str | None = None) -> None:
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
```

### 3. Explicit `mob migrate` command

For explicit control with verbose output:

```bash
$ mob migrate
Added column: sessions.name (VARCHAR(255))
Backfilled sessions.name for 6 rows

Migration complete. 2 action(s).
```

Or when nothing to do:
```bash
$ mob migrate
Database schema is up to date.
```

Also available as `make migrate`.

## Prevention

1. **Run `mob migrate` after pulling code with model changes** — the command shows exactly what changed
2. **Prefer nullable columns for new fields** — avoids backfill complexity entirely
3. **Unit tests use in-memory SQLite** — they always get a fresh schema, so they won't catch this. Integration tests against a persistent database are needed to catch schema drift.
4. **Consider Alembic for production** — the project already has `alembic>=1.13.0` as a dependency but hasn't initialized it. Alembic handles column additions, type changes, and reversible migrations properly.

## Known Limitations

- Backfill generates placeholder values (`sessions-a1b2c3d4`), not semantically meaningful data
- SQLite columns added this way remain nullable at the database level even if the model says NOT NULL
- The approach doesn't handle column type changes, renames, or deletions — only additions

## Related

- PR #11: `fix/sqlite-missing-columns` — initial fix
- PR #12: `feat/make-migrate` — CLI command and Makefile target
- PR #9: `feat/session-commands` — the change that triggered this issue
- `docs/ideation/2026-03-23-open-ideation.md` — discusses Alembic as a future improvement
- `src/mob/database.py` — implementation
- `src/mob/cli/commands/migrate_cmd.py` — CLI command
