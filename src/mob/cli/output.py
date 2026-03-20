"""Output formatting for CLI."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def print_table(data: list[dict], columns: list[str] | None = None) -> None:
    if not data:
        console.print("[dim]No results found.[/dim]")
        return

    if columns is None:
        columns = list(data[0].keys())

    table = Table()
    for col in columns:
        table.add_column(col.upper().replace("_", " "))

    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

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
