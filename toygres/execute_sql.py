from rich.console import Console
from rich.table import Table
from rich import box

from . import db
from .constants import PG_TYPES
from .models import ColumnMeta, OutputData

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


def run(sql) -> OutputData:
    """Execute SQL and return a structured SqlOutputData model."""
    description, rows, status = db.executeSQL(sql)

    col_meta = []
    if description:
        for col in description:
            col_meta.append(ColumnMeta(name=col.name, type_code=col.type_code))

    serialised_rows = [list(row) for row in rows] if rows else []

    return OutputData(
        type="sql",
        description=col_meta,
        rows=serialised_rows,
        status=status or "",
    )


def parse_sql_output(data: OutputData) -> None:
    """Render a SqlOutputData model to the terminal using Rich."""
    msg = _pretty_status(data.status)
    if msg:
        console.print(f"[green]✓[/green] {msg}")

    if data.description:
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold #ECE7D1")
        for col in data.description:
            type_name = PG_TYPES.get(col.type_code, f"oid:{col.type_code}")
            table.add_column(f"{col.name}\n[dim]{type_name}[/dim]", overflow="fold")

        for row in data.rows:
            cells = []
            for val in row:
                if val is None:
                    cells.append("[bold red]NULL[/bold red]")
                else:
                    cells.append(truncate(val))
            table.add_row(*cells)

        console.print(table)
