from .constants import NAVY, RESET
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

LOGO = f"""
{NAVY}  ████████╗ ██████╗ ██╗   ██╗ ██████╗ ██████╗ ███████╗███████╗{RESET}
{NAVY}  ╚══██╔══╝██╔═══██╗╚██╗ ██╔╝██╔════╝ ██╔══██╗██╔════╝██╔════╝{RESET}
{NAVY}     ██║   ██║   ██║ ╚████╔╝ ██║  ███╗██████╔╝█████╗  ███████╗{RESET}
{NAVY}     ██║   ██║   ██║  ╚██╔╝  ██║   ██║██╔══██╗██╔══╝  ╚════██║{RESET}
{NAVY}     ██║   ╚██████╔╝   ██║   ╚██████╔╝██║  ██║███████╗███████║{RESET}
{NAVY}     ╚═╝    ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝{RESET}
"""


def print_logo():
    print(LOGO)


def print_shortcuts(is_baseline=False):
    console = Console()
    table = Table(
        show_header=False,
        box=box.SIMPLE,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("Description", style="dim white")

    table.add_row("Esc + Enter", "Submit query / command")
    table.add_row("?? <question>", "Ask AI a question")
    table.add_row("\\<cmd>", "Execute psql meta-commands")
    table.add_row("menu", "Return to database selection")

    if is_baseline:
        table.add_row(
            "[yellow]reset db[/yellow]",
            "[yellow]Reset baseline to empty (Warning: affects future recovery)[/yellow]",
        )
        table.add_row(
            "[red]drop db / delete db[/red]",
            "[red]Drop this baseline DB[/red]",
        )
    else:
        table.add_row(
            "[yellow]reset db[/yellow]",
            "[yellow]Delete all rows from all tables[/yellow]",
        )
        table.add_row(
            "[red]atom bomb[/red]",
            "[red]Drop all tables, indexes, functions — everything[/red]",
        )

    table.add_row("exit / quit", "Quit application")
    table.add_row("Ctrl+C", "Force quit")

    console.print(
        Panel(table, title="[bold blue]Available Commands[/bold blue]", expand=False)
    )
