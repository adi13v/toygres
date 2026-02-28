from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict


class ColumnMeta(BaseModel):
    name: str
    type_code: int


OutputType = Literal["sql", "meta", "ai-text", "ai-sql", "ai-meta"]


class OutputData(BaseModel):
    type: OutputType
    # The three fields are used to store the output of a SQL query, because the output of a sql query is not a plain table
    # It has these 3 components
    # Status tells how many tables were affected
    # Rows contains the rows of the table
    # Description holds the metadata of rows returned, like column names and types
    description: list[ColumnMeta] = []
    rows: list[list] = []
    status: str = ""
    command: str = ""  # AI-generated SQL or meta-command
    output: str = ""  # actual text output (meta result, AI text response)


# ---------------------------------------------------------------------------
# AI structured response — what OpenAI is asked to return
# ---------------------------------------------------------------------------


class AiResponse(BaseModel):
    """Structured schema returned by the AI model."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "sql", "meta"]
    content: str


class ObserverAiResponse(BaseModel):
    """Structured schema returned by the AI model for observer workflows."""

    model_config = ConfigDict(extra="forbid")

    creation_command: str
    attach_command: str
    function_name: str
    trigger_name: str
    table_name: str
    channel_name: str
    description: str


class AiMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    id: Optional[int] = None
