from openai import OpenAI
import os
import dotenv

from rapidfuzz.fuzz import partial_ratio_alignment

from . import db
from .models import AiResponse, OutputData

dotenv.load_dotenv()

SYSTEM_PROMPT = """
You are an Expert PostgreSQL Analyst with tools to execute sql or meta commands, or command to see the schema of a table. Use these tools or to resolve the user's question.
Finally output either plain text that user can see or an SQL query that user can run. Whatever  is suitable for the user's question.
The internal queries that you run via tools should return small data, since large data will be hard for you to analyse. The output SQL that you send to user can however return large data, since it is not going to be executed by you.
The tables that currently exist in the database are: {tables}
{schemas}"""

# Score threshold for a table name to be considered "referenced" in the conversation
_FUZZY_THRESHOLD = 70


class ChatSession:
    def __init__(
        self,
        system_prompt: str = SYSTEM_PROMPT,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        history_length: int = 5,
    ):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.history_length = history_length
        self.messages = [{"role": "system", "content": system_prompt}]

    def ask(self, user_text: str) -> AiResponse:
        """Send a message and return a structured AiResponse."""
        # refresh the system prompt before every ask
        self._trim_history_if_needed(self.messages, self.history_length)
        self.refresh_system_prompt()
        # Add the message to the history
        self.messages.append({"role": "user", "content": user_text})

        resp = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=self.messages,
            response_format=AiResponse,
        )

        ai_response: AiResponse = resp.choices[0].message.parsed
        self.messages.append({"role": "assistant", "content": ai_response.content})
        return ai_response

    def add_output(self, output: str) -> None:
        self.messages.append({"role": "assistant", "content": output})

    # ------------------------------------------------------------------
    # System prompt refresh
    # ------------------------------------------------------------------

    def _history_text(self) -> str:
        """Return all non-system message content concatenated for fuzzy matching."""
        return " ".join(
            msg["content"]
            for msg in self.messages[1:]  # skip system prompt
        ).lower()

    def _referenced_tables(self, table_names: list[str]) -> list[str]:
        """Return tables whose names fuzzy-match text in the conversation history."""
        history = self._history_text()
        if not history.strip():
            return []
        matched = []
        print(f"\nHistory: {history}")
        for t in table_names:
            alignment = partial_ratio_alignment(t.lower(), history.lower())
            score = alignment.score
            if score >= _FUZZY_THRESHOLD:
                matched_fragment = history[alignment.dest_start : alignment.dest_end]
                print(
                    f"  [fuzzy] '{t}' → matched '{matched_fragment}' in history (score={int(score)})"
                )
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

        self.messages[0]["content"] = SYSTEM_PROMPT.format(
            tables=tables_str,
            schemas=schemas_str,
        )

    def _trim_history_if_needed(
        self, messages: list[dict[str, str]], max_length: int
    ) -> None:
        """Trim conversation history to max_length turns, always keeping messages[0] (system prompt)."""
        conversation = messages[1:]  # everything except the system prompt
        if len(conversation) > max_length:
            messages[1:] = conversation[
                -max_length:
            ]  # in-place — mutates the real list


def run(session: ChatSession, question: str) -> OutputData:
    """Refresh DB context, ask the AI, and return a typed OutputData model."""
    # print("\n--- Chat history ---")
    # for i, msg in enumerate(session.messages):
    #     preview = msg["content"]
    #     print(f"  [{i}] {msg['role'].upper()}: {preview}")
    # print("--------------------\n")
    ai_response = session.ask(question)

    if ai_response.type == "sql":
        return OutputData(type="ai-sql", command=ai_response.content)
    elif ai_response.type == "meta":
        return OutputData(type="ai-meta", command=ai_response.content)
    else:
        return OutputData(type="ai-text", output=ai_response.content)
