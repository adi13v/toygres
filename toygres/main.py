from toygres.models import AiMessage
from . import db
from . import execute_sql
from . import execute_meta
from . import ai as execute_ai
from .ai import ChatSession
from .art import print_logo, print_shortcuts
from .constants import YELLOW, RESET
from .autocomplete import HistoryCompleter
from .models import OutputData
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
import questionary
from rich.console import Console
from rich.panel import Panel
from .execute_sql import parse_sql_output
from .execute_meta import parse_meta_output
from .utils import clean_history


class SmartHistory(FileHistory):
    """FileHistory that prunes old entries and deduplicates on save."""

    def __init__(self, filename: str, days: int = 3) -> None:
        clean_history(filename, days=days)
        super().__init__(filename)

    def append_string(self, string: str) -> None:
        # Reject duplicates already present in the in-memory list
        if string in self._loaded_strings:
            return
        super().append_string(string)


history = SmartHistory(".toygres_history")


def parse_ai_sql_and_output(data: OutputData) -> None:
    """Render an AI SQL OutputData model to the terminal."""
    console = Console()
    # Show the sql that AI executed
    console.print(
        f"[bold bright_green]SQL:[/bold bright_green] [bright_green]{data.command}[/bright_green]"
    )
    # Parse the sql output
    parse_sql_output(data)


def parse_ai_meta_output(data: OutputData) -> None:
    """Render an AI meta-command OutputData model to the terminal."""
    console = Console()
    console.print(
        f"[bold bright_green]Command:[/bold bright_green] [bright_green]{data.command}[/bright_green]"
    )
    if data.output:
        console.print(data.output)


def parse_ai_text(data: OutputData) -> None:
    """Render an AI Text OutputData model to the terminal."""
    console = Console()
    if data.output:
        console.print(
            f"[bold bright_green]AI:[/bold bright_green] [bright_green]{data.output}[/bright_green]"
        )


def render_output(data: OutputData) -> None:
    """Unified output layer — routes an OutputData model to the right renderer."""
    match data.type:
        case "sql":
            parse_sql_output(data)
        case "meta":
            parse_meta_output(data)
        case "ai-text":
            parse_ai_text(data)


def run_and_track(ai_session: ChatSession, runner, query: str) -> OutputData:
    """Execute a query/command, logging it (and any error) into the AI session."""
    print(f"query is {query}")
    ai_session._add_message_to_history(
        AiMessage(role="user", content=f"Ran the query: {query}")
    )
    try:
        return runner(query)
    except Exception as e:
        ai_session._add_message_to_history(
            AiMessage(role="assistant", content=f"Error raised {e}")
        )
        raise


def main():
    print_logo()

    while True:
        try:
            dbs = db.get_databases()
        except Exception as e:
            print(f"Error connecting to Postgres server to fetch databases: {e}")
            return

        choices = dbs + ["➕ Create a new database"]

        selected_db = questionary.select(
            "Select a database to connect to:", choices=choices
        ).ask()

        if selected_db is None:
            return

        if selected_db == "➕ Create a new database":
            new_db = questionary.text("Enter new database name:").ask()
            if not new_db:
                print("Database name cannot be empty. Exiting.")
                return

            try:
                db.create_database(new_db)
                selected_db = new_db
                print(f"Database '{new_db}' created successfully.")
            except Exception as e:
                print(f"Failed to create database '{new_db}': {e}")
                continue

        try:
            host, user, port, dbname = db.connect_db(selected_db)
            _, _, _, _ = db.connect_to_read_only_db(
                selected_db
            )  # Also create a seperate read only connection (Will be used by AI)
        except Exception as e:
            print(f"Failed to connect to database '{selected_db}': {e}")
            continue

        console = Console()
        conn_url = f"postgresql://{user}@{host}:{port}/{dbname}"

        ai_session = ChatSession()
        info = (
            f"[bold]Username:[/bold] {user}\n"
            f"[bold]Hostname:[/bold] {host}\n"
            f"[bold]Port:[/bold] {port}\n"
            f"[bold]Database:[/bold] {dbname}\n\n"
            f"[bold]URL:[/bold] [green]{conn_url}[/green]"
        )

        console.print(
            Panel(info, title="[bold blue]Connection Info[/bold blue]", expand=False)
        )

        print_shortcuts()

        session = PromptSession(
            multiline=True,
            history=history,
            completer=HistoryCompleter(history),
        )

        # Inner loop for query prompting
        inner_break = False
        next_default = ""
        while True:
            try:
                query = session.prompt("> ", default=next_default)
                next_default = ""
                query = query.strip()
                if not query:
                    continue

                cmd_lower = query.lower().rstrip(";")
                if cmd_lower == "menu":
                    print(f"\n{YELLOW}Returning to DB selection menu...{RESET}\n")
                    inner_break = True
                    break
                elif cmd_lower == "reset db":
                    confirm = questionary.confirm(
                        "Are you sure you want to delete all rows from all tables?"
                    ).ask()
                    if confirm:
                        try:
                            msg = db.reset_db()
                            print(f"\n{YELLOW}{msg}{RESET}\n")
                        except Exception as e:
                            print(f"{YELLOW}Failed to reset DB: {e}{RESET}")
                    else:
                        print(f"\n{YELLOW}Reset cancelled.{RESET}\n")
                elif cmd_lower == "atom bomb":
                    print(
                        f"\n{YELLOW}WARNING: This will destroy EVERYTHING in the database—tables, indexes, enums, functions, views… everything. The database will be reset to a freshly created state.{RESET}"
                    )

                    confirm = questionary.text(
                        "Type 'NUKE' to confirm complete annihilation of this database:"
                    ).ask()
                    if confirm == "NUKE":
                        try:
                            msg = db.atom_bomb()
                            print(f"\n{YELLOW}☢️  {msg} ☢️{RESET}\n")
                        except Exception as e:
                            print(f"{YELLOW}Failed to nuke DB: {e}{RESET}")
                    else:
                        print(
                            f"\n{YELLOW}Crisis averted. Atom bomb cancelled.{RESET}\n"
                        )
                elif cmd_lower in ("exit", "quit"):
                    print(f"\n{YELLOW}Bye! ʕ·ᴥ·ʔ{RESET}\n")
                    return
                elif query.startswith("\\"):
                    output = run_and_track(
                        ai_session, execute_meta.run, query.rstrip(";")
                    )
                    render_output(output)
                elif query.startswith("??"):
                    question = query[2:].strip().rstrip(";")
                    if question:
                        with console.status("Processing...", spinner="dots"):
                            ai_output = execute_ai.run(ai_session, question)
                        if ai_output.type in ("ai-sql", "ai-meta"):
                            console.print(
                                f"[bold bright_green]AI suggests:[/bold bright_green] "
                                f"[bright_green]{ai_output.command}[/bright_green]"
                            )
                            # Instead of
                            next_default = ai_output.command
                        else:
                            render_output(ai_output)
                else:
                    output = run_and_track(
                        ai_session, execute_sql.run, query.rstrip(";")
                    )
                    render_output(output)
            except KeyboardInterrupt:
                print(f"\n{YELLOW}Bye! ʕ·ᴥ·ʔ{RESET}\n")
                return
            except EOFError:
                print(f"\n{YELLOW}Bye! ʕ·ᴥ·ʔ{RESET}\n")
                return
            except Exception as e:
                print(f"{YELLOW}Error:{RESET} {e}")

        if not inner_break:
            break


if __name__ == "__main__":
    main()
