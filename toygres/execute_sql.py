from rich.console import Console
from rich.table import Table
from rich import box

from . import db
from .constants import PG_TYPES

console = Console()


def truncate(value, max_len=30):
    """Middle-truncate a string to max_len characters."""
    s = str(value)
    if len(s) <= max_len:
        return s
    half = (max_len - 3) // 2
    return s[:half] + "..." + s[-(max_len - 3 - half) :]


def _pretty_status(status: str) -> str | None:
    """Turn a psycopg2 statusmessage into a human-readable string."""
    if not status:
        return None

    parts = status.split()
    match parts:
        case ["SELECT", n]:
            count = int(n)
            noun = "row" if count == 1 else "rows"
            return f"{count} {noun} fetched"
        case ["INSERT", _, n]:
            count = int(n)
            noun = "row" if count == 1 else "rows"
            return f"{count} {noun} inserted"
        case ["UPDATE", n]:
            count = int(n)
            noun = "row" if count == 1 else "rows"
            return f"{count} {noun} updated"
        case ["DELETE", n]:
            count = int(n)
            noun = "row" if count == 1 else "rows"
            return f"{count} {noun} deleted"
        case _:
            # CREATE TABLE, DROP TABLE, TRUNCATE, etc. — pass through as-is
            return status.lower()


def run(sql):
    description, rows, status = db.executeSQL(sql)

    # Always show the status message for every query
    msg = _pretty_status(status)
    if msg:
        console.print(f"[green]✓[/green] {msg}")

    # Show tabular results if the query returned rows
    if description:
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold #ECE7D1")
        for col in description:
            type_name = PG_TYPES.get(col.type_code, f"oid:{col.type_code}")
            table.add_column(f"{col.name}\n[dim]{type_name}[/dim]", overflow="fold")

        for row in rows:
            cells = []
            for val in row:
                if val is None:
                    cells.append("[bold red]NULL[/bold red]")
                else:
                    cells.append(truncate(val))
            table.add_row(*cells)

        console.print(table)
