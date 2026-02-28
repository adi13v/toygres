import os
from datetime import datetime, timedelta

SQL_PREFIXES = {
    "select",
    "insert",
    "update",
    "delete",
    "with",
    "create",
    "drop",
    "alter",
    "explain",
    "show",
}


def looks_like_sql(text: str) -> bool:
    stripped = text.strip().lower()
    if not stripped:
        return False

    first_word = stripped.split()[0]
    return first_word in SQL_PREFIXES


def looks_like_meta(text: str) -> bool:
    stripped = text.strip().lower()
    if not stripped:
        return False
    return stripped.startswith("\\")


def clean_history(file_path: str, days: int = 3) -> None:
    """Remove history entries older than `days` days from the history file."""
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
                    i += 1
                    while i < len(lines) and not lines[i].startswith("# "):
                        i += 1
                    continue
            except ValueError:
                pass
        new_lines.append(line)
        i += 1
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
