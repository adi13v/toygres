import os
from datetime import datetime, timedelta
from prompt_toolkit.completion import Completer, Completion
from .utils import looks_like_sql


def clean_history(file_path=".toygres_history", days=3):
    if not os.path.exists(file_path):
        return

    cutoff_date = datetime.now() - timedelta(days=days)
    new_lines = []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            timestamp_str = line[2:].strip()
            try:
                dt = datetime.fromisoformat(timestamp_str)
                if dt < cutoff_date:
                    # Skip the timestamp line
                    i += 1
                    # Skip the command lines that follow until the next timestamp
                    while i < len(lines) and not lines[i].startswith("# "):
                        i += 1
                    continue
            except ValueError:
                pass

        new_lines.append(line)
        i += 1

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


class HistoryCompleter(Completer):
    def __init__(self, history):
        clean_history(".toygres_history", days=3)
        self.history = history

    def get_completions(self, document, complete_event):
        word = document.text_before_cursor

        for entry in self.history.get_strings():
            if looks_like_sql(entry) and entry.lower().startswith(word.lower()):
                yield Completion(
                    entry,
                    start_position=-len(word),
                )
