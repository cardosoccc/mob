"""Migrate command - run database schema migrations."""

import asyncio

import click

from mob.database import migrate_db


@click.command("migrate")
def migrate():
    """Run database schema migrations.

    Creates missing tables and adds missing columns to existing tables.
    Backfills NOT NULL columns for existing rows.
    """
    actions = asyncio.run(migrate_db())
    if actions:
        for action in actions:
            click.echo(action)
        click.echo(f"\nMigration complete. {len(actions)} action(s).")
    else:
        click.echo("Database schema is up to date.")
