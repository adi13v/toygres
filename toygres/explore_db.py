import questionary
from rich.console import Console
from rich.table import Table
from rich import box

from . import db
from .constants import YELLOW, RESET, PG_TYPES, MAX_EXPLORE_COLUMNS_BEFORE_WARNING

console = Console()


def get_tables():
    query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
    try:
        _, rows, _ = db.executeSQL(query)
        return [row[0] for row in rows] if rows else []
    except Exception:
        return []


def get_views():
    query = (
        "SELECT table_name FROM information_schema.views WHERE table_schema = 'public';"
    )
    try:
        _, rows, _ = db.executeSQL(query)
        return [row[0] for row in rows] if rows else []
    except Exception:
        return []


def get_primary_keys(table_name):
    query = f"""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tco
        JOIN information_schema.key_column_usage kcu 
          ON kcu.constraint_name = tco.constraint_name
          AND kcu.constraint_schema = tco.constraint_schema
        WHERE tco.constraint_type = 'PRIMARY KEY'
          AND kcu.table_name = '{table_name}';
    """
    try:
        _, rows, _ = db.executeSQL(query)
        return [row[0] for row in rows] if rows else []
    except Exception:
        return []


def truncate_value(value, is_pk: bool, max_len: int = 30) -> str:
    s = str(value)
    if is_pk or len(s) <= max_len:
        return s

    half = (max_len - 2) // 2
    return s[:half] + ".." + s[-(max_len - 2 - half) :]


def explore_database():
    while True:
        tables = get_tables()
        views = get_views()

        if not tables and not views:
            print(f"{YELLOW}No tables or views found in this database.{RESET}")
            return

        choices = []
        if tables:
            choices.append(questionary.Separator("--- Tables ---"))
            choices.extend(tables)
        if views:
            choices.append(questionary.Separator("--- Views ---"))
            choices.extend(views)

        print(
            f"\n{YELLOW}(Press Ctrl+C at any time to go back to the main menu){RESET}"
        )

        try:
            selected_table = questionary.select(
                "Select a table/view to explore:", choices=choices
            ).ask()
        except KeyboardInterrupt:
            return

        if not selected_table:
            return

        # Fetch data up to 100 rows
        query = f'SELECT * FROM "{selected_table}" LIMIT 100;'
        try:
            description, rows, _ = db.executeSQL(query)
        except Exception as e:
            print(f"Error fetching data for table {selected_table}: {e}")
            continue

        if not description:
            print(f"{YELLOW}No columns found for {selected_table}.{RESET}")
            continue

        columns = [col.name for col in description]
        pks = get_primary_keys(selected_table)

        too_many_cols = len(columns) > MAX_EXPLORE_COLUMNS_BEFORE_WARNING
        too_many_rows = rows and len(rows) >= 100

        if too_many_cols or too_many_rows:
            warnings = []
            if too_many_cols:
                warnings.append(f"{len(columns)} columns")
            if too_many_rows:
                warnings.append("100+ rows")

            print(
                f"\n{YELLOW}⚠️  Warning: This table has {' and '.join(warnings)}.{RESET}"
            )
            print(
                f"{YELLOW}   High numbers of rows or columns can cause problems in rendering.{RESET}"
            )
            print(
                f"{YELLOW}   Consider using SQL views with only the specific data you care about for concise information.{RESET}\n"
            )

        if not rows:
            print(f"{YELLOW}Table {selected_table} is empty.{RESET}")
            continue

        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold #ECE7D1",
            title=f"Table: {selected_table} (showing up to 100 rows)",
        )

        for col in description:
            type_name = PG_TYPES.get(col.type_code, f"oid:{col.type_code}")
            pk_marker = "🔑 " if col.name in pks else ""
            table.add_column(
                f"{pk_marker}{col.name}\n[dim]{type_name}[/dim]", overflow="fold"
            )

        is_view = selected_table in views

        for row in rows:
            cells = []
            for j, val in enumerate(row):
                if val is None:
                    cells.append("[bold red]NULL[/bold red]")
                else:
                    if is_view:
                        cells.append(str(val))
                    else:
                        col_name = columns[j]
                        is_pk = col_name in pks
                        cells.append(truncate_value(val, is_pk=is_pk, max_len=30))
            table.add_row(*cells)

        console.print(table)

        if too_many_cols or too_many_rows:
            warnings = []
            if too_many_cols:
                warnings.append(f"{len(columns)} columns")
            if too_many_rows:
                warnings.append("100+ rows")

            print(
                f"\n{YELLOW}⚠️  Warning: Could not show full data.This table has {' and '.join(warnings)}.{RESET}"
            )
            print(
                f"{YELLOW}   High numbers of rows or columns can cause problems in rendering.{RESET}"
            )
            print(
                f"{YELLOW}   Consider using SQL views with only the specific data you care about for concise information.{RESET}\n"
            )
