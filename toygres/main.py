import re
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
from questionary import Choice
import questionary
from rich.console import Console
from rich.panel import Panel
from .execute_sql import parse_sql_output
from .execute_meta import parse_meta_output
from .utils import clean_history
from .observer import run_observer_workflow


class SmartHistory(FileHistory):
    """FileHistory that prunes old entries and deduplicates on save."""

    def __init__(self, filename: str, days: int = 3) -> None:
        clean_history(filename, days=days)
        super().__init__(filename)

    def append_string(self, string: str) -> None:
        # Deleting already present in the in-memory list, and re append it at last
        # This shows the most recent queries at the top of the history.
        # Makes up for a much better UX
        string = string.strip()
        if not string:
            return

        if string in self._loaded_strings:
            self._loaded_strings.remove(string)
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


def handle_cascade_operations(query: str):
    """Parses queries to detect DB drops or renames and cascades them to baselines."""
    drop_match = re.search(
        r"drop\s+database\s+(?:if\s+exists\s+)?([a-zA-Z0-9_]+)",
        query,
        re.IGNORECASE,
    )
    rename_match = re.search(
        r"alter\s+database\s+([a-zA-Z0-9_]+)\s+rename\s+to\s+([a-zA-Z0-9_]+)",
        query,
        re.IGNORECASE,
    )

    if drop_match:
        target = drop_match.group(1)
        try:
            all_dbs = db.get_databases()
            baselines = [d for d in all_dbs if d.endswith(f"_baseline_for_{target}")]
            for b in baselines:
                db.drop_database(b)
                print(f"{YELLOW}Cascaded drop to baseline: {b}{RESET}")
        except Exception:
            pass
    elif rename_match:
        target = rename_match.group(1)
        new_target = rename_match.group(2)
        try:
            all_dbs = db.get_databases()
            baselines = [d for d in all_dbs if d.endswith(f"_baseline_for_{target}")]
            for b in baselines:
                new_baseline_name = b.replace(
                    f"_baseline_for_{target}",
                    f"_baseline_for_{new_target}",
                )
                db.rename_database(b, new_baseline_name, force=True)
                print(
                    f"{YELLOW}Cascaded rename to baseline: {b} -> {new_baseline_name}{RESET}"
                )
        except Exception:
            pass


def main():
    print_logo()

    while True:
        try:
            dbs = db.get_databases()
        except Exception as e:
            print(f"Error connecting to Postgres server to fetch databases: {e}")
            return

        normal_dbs = [d for d in dbs if "_baseline_for_" not in d]
        baseline_dbs = [d for d in dbs if "_baseline_for_" in d]

        choices = (
            [Choice([("bold", "--- Normal DBs ---")], disabled="")]
            + [Choice(d, value=d) for d in normal_dbs]
            + [
                Choice(
                    [("fg:yellow bold", "➕ Create a new database")],
                    value="➕ Create a new database",
                )
            ]
            + [
                questionary.Separator("\n"),
                Choice([("bold", "--- Baseline DBs ---")], disabled=""),
            ]
            + [Choice(d, value=d) for d in baseline_dbs]
            + [
                Choice(
                    [("fg:yellow bold", "➕ Create new baseline")],
                    value="➕ Create new baseline",
                )
            ]
        )

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
        elif selected_db == "➕ Create new baseline":
            if not normal_dbs:
                print("No normal databases available to baseline. Create one first.")
                continue
            target_db = questionary.select(
                "Select target database for baseline:", choices=normal_dbs
            ).ask()
            if not target_db:
                continue

            user_name = questionary.text("Enter baseline prefix/name:").ask()
            if not user_name:
                print("Name cannot be empty.")
                continue

            baseline_type = questionary.select(
                "What should the baseline include?",
                choices=[
                    "Schema only (Best for manual population)",
                    "Schema + Data (Copy current table data)",
                ],
            ).ask()
            if not baseline_type:
                continue

            schema_only = baseline_type.startswith("Schema only")

            try:
                print(
                    f"Creating baseline for '{target_db}'... (This may take a moment)"
                )
                baseline_name = db.create_baseline(user_name, target_db, schema_only)
                selected_db = baseline_name
                print(f"Baseline '{baseline_name}' created successfully.")
            except Exception as e:
                print(f"Failed to create baseline: {e}")
                continue

        try:
            # Establish a connection to the selected db, so that we can safely delete the current baseline
            host, user, port, dbname = db.establish_all_connections(selected_db)
            print(f"{YELLOW}\nConnected to database: {dbname}{RESET}")
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

        is_baseline = "_baseline_for_" in selected_db
        if is_baseline:
            operation_mode = "Start AI/SQL Chat"
        else:
            operation_mode = questionary.select(
                "Select operation mode:",
                choices=["Start AI/SQL Chat", "Deploy Observer Agent", "Explore Data"],
            ).ask()

        if operation_mode == "Deploy Observer Agent":
            print(f"{YELLOW}What do you want to track?{RESET}")
            print(
                f"{YELLOW}(Ex- Track when the status of user with id 1 changes){RESET}"
            )
            print(f"{YELLOW}(Press [ESC] followed by [ENTER] to submit){RESET}")

            try:
                observer_session = PromptSession(multiline=True)
                track_prompt = observer_session.prompt("> ")
                if track_prompt.strip():
                    run_observer_workflow(track_prompt)
            except KeyboardInterrupt:
                pass  # Nothing to do here, continue below will bring us back to main menu
            continue

        elif operation_mode == "Explore Data":
            from .explore_db import explore_database

            explore_database()
            continue

        elif operation_mode == "Start AI/SQL Chat":
            print_shortcuts(is_baseline)

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
                    elif cmd_lower in ("delete db", "drop db"):
                        if is_baseline:
                            confirm = questionary.confirm(
                                "WARNING: This is a backup instance. Deleting it would not allow you to create from this baseline ever again. Are you sure?"
                            ).ask()
                            if confirm:
                                try:
                                    target_db = dbname.split("_baseline_for_")[-1]
                                    host, user, port, new_dbname = (
                                        db.establish_all_connections(target_db)
                                    )
                                    db.drop_database(dbname)
                                    dbname = new_dbname
                                    is_baseline = False
                                    print(
                                        f"\n{YELLOW}You are now in owner DB '{dbname}'. Baseline has been deleted.{RESET}\n"
                                    )
                                except Exception as e:
                                    print(f"{YELLOW}Failed: {e}{RESET}")
                            else:
                                print(f"\n{YELLOW}Drop cancelled.{RESET}\n")
                        else:
                            print(
                                f"{YELLOW}Command restricted to baselines. (Use 'atom bomb' instead for normal DBs){RESET}"
                            )
                    elif cmd_lower == "reset db":
                        if is_baseline:
                            confirm = questionary.confirm(
                                "WARNING: This is a baseline instance. Clearing the tables would mean previous data won't be applicable when restoring from this baseline"
                            ).ask()
                        else:
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
                        if is_baseline:
                            print(f"{YELLOW}Command restricted to normal DBs.{RESET}")
                            continue

                        print(
                            f"\n{YELLOW}WARNING: This will destroy EVERYTHING in the database—tables, indexes, enums, functions, views… everything. The database will be reset to a freshly created state.{RESET}"
                        )
                        baseline_choices = [
                            d
                            for d in db.get_databases()
                            if d.endswith(f"_baseline_for_{dbname}")
                        ]
                        choices = ["Complete annihilation (reset to fresh state)"]
                        if baseline_choices:
                            choices.extend(
                                [
                                    f"Recreate from baseline: {b}"
                                    for b in baseline_choices
                                ]
                            )
                        choices.append("Cancel")

                        nuke_type = questionary.select(
                            "Select atom bomb mode:", choices=choices
                        ).ask()
                        if nuke_type == "Cancel":
                            print(
                                f"\n{YELLOW}Crisis averted. Atom bomb cancelled.{RESET}\n"
                            )
                            continue

                        confirm = questionary.text(
                            "Type 'NUKE' to confirm complete annihilation of this database:"
                        ).ask()
                        if confirm == "NUKE":
                            try:
                                if nuke_type.startswith("Recreate"):
                                    baseline_name = nuke_type.split(": ")[1]
                                    msg = db.recreate_from_baseline(
                                        dbname, baseline_name
                                    )
                                else:
                                    msg = db.reset_public_schema()
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
                            with console.status("Processing...", spinner="pong"):
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

                        # For normal dbs look out for renames and drops and cascade them to baselines
                        if not is_baseline:
                            handle_cascade_operations(query)
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
