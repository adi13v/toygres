from . import db
from . import execute_sql
from . import execute_meta
from . import ai as execute_ai
from .ai import ChatSession
from .art import print_logo, print_shortcuts
from .constants import YELLOW, RESET
from .autocomplete import HistoryCompleter
from .utils import looks_like_sql
from .models import OutputData
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.history import FileHistory
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from .execute_sql import parse_sql_output
from .execute_meta import parse_meta_output


class SQLOnlyHistory(FileHistory):
    """FileHistory that only stores SQL entries and deduplicates them."""

    def append_string(self, string: str) -> None:
        # Reject non-SQL (menu, exit, psql meta-commands, etc.)
        # if not looks_like_sql(string):
        #     return
        # Reject duplicates already present in the in-memory list
        if string in self._loaded_strings:
            return
        super().append_string(string)


history = SQLOnlyHistory(".toygres_history")


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
        case "ai-sql":
            parse_ai_sql_and_output(data)
        case "ai-meta":
            parse_ai_meta_output(data)
        case "ai-text":
            parse_ai_text(data)


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

        bindings = KeyBindings()

        @bindings.add("enter")
        def smart_enter(event):
            buf = event.current_buffer
            text = buf.text.strip()
            # Allow command without colon mostly for special commands
            if text.rstrip().endswith(";") or text.strip().lower() in (
                "menu",
                "clear",
                "exit",
                "quit",
                "reset db",
                "atom bomb",
            ):
                buf.validate_and_handle()
            else:
                buf.insert_text("\n")

        session = PromptSession(
            key_bindings=bindings,
            multiline=True,
            history=history,
            completer=HistoryCompleter(history),
            # search_ignore_case=True, ## doesn't seem to work, done manually in autocomplete.py
        )

        # Inner loop for query prompting
        inner_break = False
        while True:
            try:
                query = session.prompt("> ")
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
                    output = execute_meta.run(query)
                    render_output(output)
                elif query.startswith("??"):
                    question = query[2:].strip().rstrip(";")
                    if question:
                        with console.status("Processing...", spinner="dots"):
                            ai_output = execute_ai.run(ai_session, question)
                            if ai_output.type == "ai-sql":
                                sql_output = execute_sql.run(ai_output.command)
                                ai_output.rows = sql_output.rows
                                ai_output.description = sql_output.description
                                ai_output.status = sql_output.status
                            elif ai_output.type == "ai-meta":
                                meta_output = execute_meta.run(ai_output.command)
                                ai_output.output = meta_output.output
                            elif ai_output.type == "ai-text":
                                pass  # AI text will be rendered as-is
                        render_output(ai_output)
                else:
                    output = execute_sql.run(query)
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
