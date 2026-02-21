from rich.console import Console

from . import db
from .models import OutputData

console = Console()


def run(command) -> OutputData:
    """Execute a meta-command and return a structured OutputData model."""
    output = db.executepsql(command)
    return OutputData(type="meta", output=output or "")


def parse_meta_output(data: OutputData) -> None:
    """Render a meta-command OutputData model to the terminal."""
    if data.output:
        console.print(data.output)
