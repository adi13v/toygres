# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
NAVY = "\033[38;2;3;4;94m"  # #03045E
YELLOW = "\033[1;33m"
GRAY = "\033[0;37m"
MATRIX_GREEN = "\033[38;5;28m"
DEEP_RED = "\033[38;2;200;0;0m"

# PostgreSQL OID → type name mapping
PG_TYPES = {
    16: "bool",
    17: "bytea",
    18: "char",
    19: "name",
    20: "int8",
    21: "int2",
    23: "int4",
    25: "text",
    26: "oid",
    114: "json",
    142: "xml",
    700: "float4",
    701: "float8",
    869: "inet",
    1042: "bpchar",
    1043: "varchar",
    1082: "date",
    1083: "time",
    1114: "timestamp",
    1184: "timestamptz",
    1186: "interval",
    1700: "numeric",
    2950: "uuid",
    3802: "jsonb",
}

MAX_EXPLORE_COLUMNS_BEFORE_WARNING = 8
MAX_TOOL_RESULT_LENGTH = 8000
TRUNCATED_TOOL_RESULT_MESSAGE = "extremely long response, either execute a shorter query or give the sql output to user"
