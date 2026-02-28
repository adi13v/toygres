from toygres.models import AiMessage
from toygres.constants import (
    RESET,
    MATRIX_GREEN,
    MAX_TOOL_RESULT_LENGTH,
    TRUNCATED_TOOL_RESULT_MESSAGE,
)
from rapidfuzz.fuzz import ratio as fuzz_ratio
from openai import OpenAI
import json
import os
import dotenv
from toygres.costs import session_costs
from . import db
from .models import AiResponse, OutputData

SYSTEM_PROMPT = """
## SYSTEM PROMPT

You are an Expert PostgreSQL Analyst with tools to execute SQL or meta commands, and to inspect table schemas. Use these tools when necessary to resolve the user's question accurately.

You have read-only execution capability. If a required query is not read-only, do not execute it yourself. Instead, output the SQL query for the user to run.

---

### Objective

Provide the most appropriate and correct response to the user’s query using the available tools and database context.

---

### Tool Usage Policy

- Prefer using tools when the answer depends on actual database state.
- You may execute:
  - read-only SQL queries
  - meta/schema inspection commands
- You must not execute any query that modifies data or schema. Just output the command to user via sql or meta command.
- If a non–read-only query is required, output it for the user instead.

---

### Output Rules

- Output either:
  - plain text for the user, or
  - an SQL query the user can run.
- Choose whichever best answers the user's question.
- Do not include explanations outside the required output.
- Whenever doing any operation on a noun

---

### For statements that are NOT read only
If you want the user to execute a query, you must output it with type being ```sql``` or ```meta``` and content being the query.

### If user asks about user info
If user asks like which user/role am i in, understand that you have access to 'ai' role only, and give them the sql command for themselves to run.
"""
# Score threshold for a table name to be considered "referenced" in the conversation
_FUZZY_THRESHOLD = 70


tools = [
    {
        "type": "function",
        "name": "execute_read_only_sql",
        "description": "Execute a read only SQL query. Should try to return focused and small data, output that will be easy for you to analyse.",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "An SQL query to execute.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "type": "function",
        "name": "execute_meta_commands",
        "description": "meta commands",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "A meta command to execute.",
                },
            },
            "required": ["command"],
        },
    },
]


def _execute_read_only_sql(sql: str) -> str:
    """Run a read-only SQL query and return the result as a plain string."""
    try:
        _, rows, status = db.executeSQLReadOnly(sql)
        if rows:
            return "\n".join(str(row) for row in rows)
        return status or "(no rows returned)"
    except Exception as e:
        return f"Error: {e}"


def _execute_meta_commands(command: str) -> str:
    """Run a meta-command and return the output as a plain string."""
    try:
        result = db.execute_read_only_meta_command(command)
        return str(result) if result else "(no output)"
    except Exception as e:
        return f"Error: {e}"


_TOOL_DISPATCH: dict[str, callable] = {
    "execute_read_only_sql": lambda args: _execute_read_only_sql(args["sql"]),
    "execute_meta_commands": lambda args: _execute_meta_commands(args["command"]),
}


def _dispatch_tool(name: str, arguments_json: str) -> str:
    """Parse tool arguments and call the matching local function."""
    args = json.loads(arguments_json)
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    return handler(args)


class ChatSession:
    def __init__(
        self,
        system_prompt: str = SYSTEM_PROMPT,
        model: str | None = None,
        api_key: str | None = None,
        history_length: int = 5,
    ):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.history_length = history_length
        self.messages = [AiMessage(role="system", content=system_prompt, id=0)]

    def ask(self, user_text: str) -> AiResponse:
        """Send a message, run the tool-call loop, and return a structured AiResponse."""
        self._add_message_to_history(AiMessage(role="user", content=user_text))
        self.refresh_system_prompt()

        input_messages: list = [
            {"role": m.role, "content": m.content} for m in self.messages
        ]

        while True:
            resp = self.client.responses.create(
                model=self.model,
                input=input_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "AiResponse",
                        "schema": AiResponse.model_json_schema(),
                        "strict": True,
                    }
                },
                tools=tools,
                max_tool_calls=5,
            )
            print("\n")
            print(f"Prompt: {resp.usage.input_tokens}")
            print(f"Completion: {resp.usage.output_tokens}")
            print(f"Total: {resp.usage.total_tokens}")
            print("\n")

            session_costs.add_tokens(resp.usage.input_tokens, resp.usage.output_tokens)

            tool_calls = [item for item in resp.output if item.type == "function_call"]

            if not tool_calls:
                break

            # We extend the local input messages, not the class level self.messages because currently we
            # treat tool calling or multiple tool callings, as an internal conversation to achieve a task.
            # So we will forget it once this task is done. (Can change later, but doesn't seem useful right now)
            input_messages.extend(resp.output)

            print(f"{MATRIX_GREEN}┌{'-' * 78}┐{RESET}")
            for tc in tool_calls:
                print(
                    f"{MATRIX_GREEN}│ \033[1m⚙️  [tool] \033[0m{MATRIX_GREEN}{tc.name}({tc.arguments}){RESET}"
                )
                result = _dispatch_tool(tc.name, tc.arguments)
                if len(result) > MAX_TOOL_RESULT_LENGTH:
                    result = TRUNCATED_TOOL_RESULT_MESSAGE
                print(
                    f"{MATRIX_GREEN}│ \033[1m✅ [tool result] \033[0m{MATRIX_GREEN}{result[:200]}{RESET}"
                )
                input_messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": tc.call_id,
                        "output": result,
                    }
                )
            print(f"{MATRIX_GREEN}└{'-' * 78}┘{RESET}")

        ai_response = AiResponse.model_validate_json(resp.output_text)
        self._add_message_to_history(
            message=AiMessage(role="assistant", content=ai_response.content)
        )
        return ai_response

    # ------------------------------------------------------------------
    # System prompt refresh
    # ------------------------------------------------------------------

    def _history_text(self) -> str:
        """Return all non-system message content concatenated for fuzzy matching."""
        return " ".join(
            msg.content
            for msg in self.messages[1:]  # skip system prompt
        ).lower()

    def _referenced_tables(self, table_names: list[str]) -> list[str]:
        """Return tables whose names fuzzy-match text in the conversation history.

        For a table name like ``user_metadata`` (1 underscore → 2 parts) we
        slide a 2-word window over the history and score each chunk with
        fuzz.ratio, which avoids the token-set logic smearing scores across
        individual words.
        """
        history = self._history_text()
        if not history.strip():
            return []

        history_words = history.split()
        matched = []

        for t in table_names:
            parts = t.split("_")
            window_size = len(parts)  # e.g. "user_metadata" → 2
            t_normalised = t.replace("_", " ")

            best_score = 0
            for i in range(max(1, len(history_words) - window_size + 1)):
                chunk = " ".join(history_words[i : i + window_size])
                score = fuzz_ratio(t_normalised, chunk)
                if score > best_score:
                    best_score = score

            if best_score >= _FUZZY_THRESHOLD:
                print(f"  [fuzzy] '{t}' matched (score={int(best_score)})")
                matched.append(t)

        return matched

    def _fetch_schema(self, table_name: str) -> str:
        """Fetch column names and types for a single table."""
        _, rows, _ = db.executeSQL(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = '{table_name}' "
            "ORDER BY ordinal_position;"
        )
        if not rows:
            return ""
        cols = ", ".join(f"{row[0]} ({row[1]})" for row in rows)
        return f"  {table_name}: {cols}"

    def refresh_system_prompt(self) -> None:
        """
        Rebuild the system prompt with:
        - the current list of all public tables
        - schemas of tables that appear in the conversation history (via fuzzy match)
        """
        _, rows, _ = db.executeSQL(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
        )
        table_names = [row[0] for row in rows] if rows else []
        tables_str = ", ".join(table_names) if table_names else "(none)"

        # Fuzzy match the table names with the conversation history, to find which table's schema can be included in the prompt.
        referenced = self._referenced_tables(table_names)
        print(f"Referenced tables: {referenced}")
        if referenced:
            schema_lines = ["\nSchemas of referenced tables:"]
            for t in referenced:
                schema = self._fetch_schema(t)
                if schema:
                    schema_lines.append(schema)
            schemas_str = "\n".join(schema_lines)
        else:
            schemas_str = ""

        self.messages[0].content = SYSTEM_PROMPT.format(
            tables=tables_str,
            schemas=schemas_str,
        )

    def _trim_history_if_needed(self) -> None:
        messages = self.messages
        max_length = self.history_length
        """Trim conversation history to max_length turns, always keeping messages[0] (system prompt)."""
        conversation = messages[1:]  # everything except the system prompt
        if len(conversation) > max_length:
            messages[1:] = conversation[
                -max_length:
            ]  # in-place — mutates the real list

    def _add_message_to_history(self, message: AiMessage):
        self._trim_history_if_needed()

        # Get and append next id
        next_id = self.messages[-1].id + 1
        message.id = next_id

        # append
        self.messages.append(message)


def run(session: ChatSession, question: str) -> OutputData:
    """Ask the AI and return a typed OutputData model."""
    ai_response = session.ask(question)
    if ai_response.type == "sql":
        return OutputData(type="ai-sql", command=ai_response.content)
    elif ai_response.type == "meta":
        return OutputData(type="ai-meta", command=ai_response.content)
    else:
        return OutputData(type="ai-text", output=ai_response.content)
