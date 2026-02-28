from toygres.db import executeSQL, connect_to_observer_db
from .models import ObserverAiResponse
from . import db
from openai import OpenAI
import os
import dotenv
import json
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
import select

dotenv.load_dotenv()


OBSERVER_PROMPT = """
You are an Expert PostgreSQL AI Observer. Your goal is to write a trigger function and its attachment command to track changes on a table requested by the user.

Requirements:
1. The user wants to track specific events (e.g., status changes, insertions, deletions) on a table.
2. The trigger function MUST use `pg_notify` to send a JSON payload whenever the condition is met.
3. The channel name for `pg_notify` should be something unique and descriptive, e.g., 'table_status_changes'.
4. The JSON payload emitted by `pg_notify` MUST adhere strictly to the following structures based on the triggering event type (TG_OP):
   
   If INSERT, use this format:
   json_build_object('operation', 'INSERT', 'data', row_to_json(NEW))::text
   
   If DELETE, use this format:
   json_build_object('operation', 'DELETE', 'data', row_to_json(OLD))::text

   If UPDATE, use this format showing old and new values:
   json_build_object(
       'operation', 'UPDATE',
       'data', json_build_object('old', row_to_json(OLD), 'new', row_to_json(NEW))
   )::text
5. Return exactly these details:
   - `creation_command`: The CREATE OR REPLACE FUNCTION command.
   - `attach_command`: The CREATE TRIGGER command.
   - `function_name`: The name of the function you created.
   - `trigger_name`: The name of the trigger you created.
   - `table_name`: The name of the table the trigger is attached to.
   - `channel_name`: The name of the pg_notify channel you used.
   - `description`: A clear, natural language explanation of exactly what this trigger is actively observing.

To avoid naming conflicts, use unique names for your function and trigger. Do NOT use the names below:
Existing Functions: {existing_functions}
Existing Triggers: {existing_triggers}

Available Tables and Schemas:
{schemas}
"""


class ObserverAgent:
    def _create_trigger(self, command):
        executeSQL(command)

    def _attach_trigger(self, command):
        executeSQL(command)

    def _cleanup(self, function_name, trigger_name, table_name):
        executeSQL(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
        executeSQL(f"DROP FUNCTION IF EXISTS {function_name}()")

    def _format_event_data(self, data, op) -> str:
        """Formats the data dictionary strictly based on the event operation."""
        if not isinstance(data, dict):
            return str(data)

        if op == "UPDATE" and "old" in data and "new" in data:
            old_data = data["old"] or {}
            new_data = data["new"] or {}

            # Filter to show only keys that changed
            out = []
            for k in set(old_data.keys()).union(new_data.keys()):
                old_val = old_data.get(k)
                new_val = new_data.get(k)
                if old_val != new_val:
                    out.append(
                        f"• [dim]{k}:[/dim] [red]{old_val}[/red] ➔ [green]{new_val}[/green]"
                    )
            return "\n".join(out) if out else "• (No fields changed)"

        # INSERT / DELETE fallback
        return "\n".join([f"• {k}: {v}" for k, v in data.items()])

    def _print_event(self, notify, now, console: Console):
        """Parse the JSON payload and render it as a Rich panel."""
        try:
            payload_dict = json.loads(notify.payload)
            op = payload_dict.get("operation", "UNKNOWN")
            data = payload_dict.get("data", payload_dict)

            if op == "UPDATE":
                color = "yellow"
            elif op == "INSERT":
                color = "green"
            elif op == "DELETE":
                color = "red"
            else:
                color = "magenta"

            formatted_data = self._format_event_data(data, op)

            panel = Panel(
                formatted_data,
                title=f"[bold {color}]{op} Event[/bold {color}]",
                subtitle=f"[dim]{now}[/dim]",
                expand=False,
                border_style=color,
            )
            console.print(panel)
        except json.JSONDecodeError:
            # Fallback if not valid JSON
            console.print(
                f"[dim]{now}[/dim] [bold cyan]Raw Event:[/bold cyan] {notify.payload}"
            )

    def start(self, ai_response: ObserverAiResponse):
        console = Console()
        try:
            self._create_trigger(ai_response.creation_command)
            self._attach_trigger(ai_response.attach_command)
        except Exception as e:
            console.print(f"[red]Failed to attach triggers: {e}[/red]")
            return

        channel_name = ai_response.channel_name

        if not channel_name:
            console.print(
                "[red]AI failed to generate a channel name in pg_notify.[/red]"
            )
            self._cleanup(
                ai_response.function_name,
                ai_response.trigger_name,
                ai_response.table_name,
            )
            return

        conn = connect_to_observer_db(db.DBNAME)

        with conn.cursor() as cur:
            cur.execute(f"LISTEN {channel_name}")
            conn.commit()

            console.print(
                f"\n[bold green] Listening on channel '{channel_name}'... (Press Ctrl+C to stop)[/bold green]"
            )
            console.print(
                f"[bold cyan]Description:[/bold cyan] {ai_response.description}\n"
            )

            try:
                with console.status("Waiting for events...", spinner="monkey"):
                    while True:
                        if select.select([conn], [], [], 5) == ([], [], []):
                            pass
                        else:
                            conn.poll()
                            while conn.notifies:
                                notify = conn.notifies.pop(0)
                                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                self._print_event(notify, now, console)
                                console.print("\n")

            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping listener and cleaning up...[/yellow]")

            finally:
                self._cleanup(
                    ai_response.function_name,
                    ai_response.trigger_name,
                    ai_response.table_name,
                )
                console.print(
                    "[bold green]Observer stopped and cleaned up successfully.[/bold green] \n"
                )


def run_observer_workflow(user_text: str):
    console = Console()
    dbname = db.DBNAME
    if not dbname:
        console.print("[red]Not connected to any database.[/red]")
        return

    try:
        triggers = db.get_existing_triggers(dbname)
        functions = db.get_existing_functions(dbname)

        # Get all schemas
        _, rows, _ = db.executeSQL(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
        )
        table_names = [row[0] for row in rows] if rows else []

        schema_lines = []
        for t in table_names:
            _, cols, _ = db.executeSQL(
                f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{t}' ORDER BY ordinal_position;"
            )
            if cols:
                col_str = ", ".join(f"{c[0]} ({c[1]})" for c in cols)
                schema_lines.append(f"  {t}: {col_str}")

        schemas_str = "\n".join(schema_lines) if schema_lines else "(none)"
        prompt = OBSERVER_PROMPT.format(
            existing_functions=", ".join(functions) if functions else "(none)",
            existing_triggers=", ".join(triggers) if triggers else "(none)",
            schemas=schemas_str,
        )

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        with console.status("Generating Observer SQL...", spinner="dots"):
            resp = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_text},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "ObserverAiResponse",
                        "schema": ObserverAiResponse.model_json_schema(),
                        "strict": True,
                    }
                },
            )

            ai_response = ObserverAiResponse.model_validate_json(resp.output_text)

        console.print(
            "[bold bright_green]AI generated tracking triggers! Starting observer...[/bold bright_green]"
        )

        agent = ObserverAgent()
        agent.start(ai_response)

    except Exception as e:
        console.print(f"[red]Error in observer workflow: {e}[/red]")
