"""Output formatting for CLI."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def _short_id(value: str) -> str:
    """Shorten UUIDs to 8 chars for table display."""
    s = str(value)
    # Detect UUID pattern (8-4-4-4-12 hex)
    if len(s) == 36 and s.count("-") == 4:
        return s[:8]
    return s


def print_table(data: list[dict], columns: list[str] | None = None) -> None:
    if not data:
        console.print("[dim]No results found.[/dim]")
        return

    if columns is None:
        columns = list(data[0].keys())

    # Columns ending in "id" or named "id" get short UUIDs
    id_columns = {col for col in columns if col == "id" or col.endswith("_id")}

    table = Table()
    table.add_column("#", justify="right", style="dim")
    for col in columns:
        table.add_column(col.upper().replace("_", " "))

    for idx, row in enumerate(data, start=1):
        values = [str(idx)]
        for col in columns:
            val = str(row.get(col, ""))
            if col in id_columns:
                val = _short_id(val)
            values.append(val)
        table.add_row(*values)

    console.print(table)


def print_detail(data: dict, fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(data.keys())
    for field in fields:
        value = data.get(field, "")
        console.print(f"[bold]{field}:[/bold] {value}")


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


def print_success(msg: str) -> None:
    console.print(f"[green]{msg}[/green]")


def print_error(msg: str) -> None:
    console.print(f"[red]{msg}[/red]")
