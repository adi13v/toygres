"""
Fuzzy matching playground — test partial_ratio against a set of table names.

Run:
    python test_fuzzy.py
or pass args directly:
    python test_fuzzy.py "show me all users and their orders" --tables users orders products --threshold 70
"""

import argparse
from rapidfuzz import fuzz

# ── Default test data ────────────────────────────────────────────────────────

DEFAULT_TABLES = [
    "users",
    "orders",
    "products",
    "order_items",
    "categories",
    "reviews",
]

DEFAULT_THRESHOLD = 70


# ── Core helper ──────────────────────────────────────────────────────────────


def match_tables(
    text: str, table_names: list[str], threshold: int
) -> list[tuple[str, int]]:
    """Return (table_name, score) pairs that meet the threshold, sorted by score desc."""
    results = []
    for table in table_names:
        score = fuzz.partial_ratio(table.lower(), text.lower())
        results.append((table, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def print_results(text: str, table_names: list[str], threshold: int) -> None:
    results = match_tables(text, table_names, threshold)
    matched = [(t, s) for t, s in results if s >= threshold]
    skipped = [(t, s) for t, s in results if s < threshold]

    print(f"\nInput text : {text!r}")
    print(f"Threshold  : {threshold}")
    print(f"Tables     : {table_names}")
    print()

    if matched:
        print("✅ Matched:")
        for table, score in matched:
            bar = "█" * (int(score) // 5)
            print(f"  {table:<20} {int(score):>3}  {bar}")
    else:
        print("❌ No tables matched the threshold.")

    if skipped:
        print("\n⬇️  Below threshold:")
        for table, score in skipped:
            bar = "░" * (int(score) // 5)
            print(f"  {table:<20} {int(score):>3}  {bar}")


# ── Interactive REPL mode ────────────────────────────────────────────────────


def interactive(table_names: list[str], threshold: int) -> None:
    print("Fuzzy matching REPL — type a sentence and see which tables match.")
    print(f"Tables: {table_names}")
    print(f"Threshold: {threshold}  (change with :threshold <n>)")
    print("Type :quit to exit.\n")

    while True:
        try:
            text = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not text:
            continue
        if text == ":quit":
            break
        if text.startswith(":threshold "):
            try:
                threshold = int(text.split()[1])
                print(f"Threshold set to {threshold}")
            except ValueError:
                print("Usage: :threshold <number>")
            continue

        print_results(text, table_names, threshold)
        print()


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test rapidfuzz partial_ratio against table names."
    )
    parser.add_argument(
        "text", nargs="?", help="Text to match against (omit for interactive mode)"
    )
    parser.add_argument("--tables", nargs="+", default=DEFAULT_TABLES, metavar="TABLE")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    if args.text:
        print_results(args.text, args.tables, args.threshold)
    else:
        interactive(args.tables, args.threshold)


if __name__ == "__main__":
    main()
