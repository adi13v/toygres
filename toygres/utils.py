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
