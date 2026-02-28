import psycopg2
import os
import psycopg2
from psycopg2 import sql
import subprocess

conn = None
read_only_conn = None
observer_conn = None

# Initialize with superuser until the initial db selection
HOST = "localhost"
USER = "postgres"
PORT = "5432"
DBNAME = "postgres"

# Initial connection with template1 as a fallback incase postgres is deleted
try:
    conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    conn.autocommit = True
except psycopg2.OperationalError:
    conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname="template1")
    conn.autocommit = True
    conn.cursor().execute(f"CREATE DATABASE {DBNAME};")
    conn.close()
    conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    conn.autocommit = True


def get_databases():
    temp_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    temp_conn.autocommit = True
    with temp_conn.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        dbs = [row[0] for row in cur.fetchall()]
    temp_conn.close()
    return dbs


def create_database(new_dbname):
    # Create database shall be done our created internal db, since it cannot be deleted by normal user
    # So we have a fallback even if user deletes all the other dbs
    temp_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    temp_conn.autocommit = True
    with temp_conn.cursor() as cur:
        query = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_dbname))
        cur.execute(query)
    temp_conn.close()


def get_existing_triggers(dbname):
    temp_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=dbname)
    temp_conn.autocommit = True
    with temp_conn.cursor() as cur:
        cur.execute("SELECT tgname FROM pg_trigger WHERE tgisinternal = false;")
        triggers = [row[0] for row in cur.fetchall()]
    temp_conn.close()
    return triggers


def get_existing_functions(dbname):
    temp_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=dbname)
    temp_conn.autocommit = True
    with temp_conn.cursor() as cur:
        cur.execute(
            "SELECT proname FROM pg_proc JOIN pg_namespace ON pg_proc.pronamespace = pg_namespace.oid "
            "WHERE pg_namespace.nspname = 'public';"
        )
        functions = [row[0] for row in cur.fetchall()]
    temp_conn.close()
    return functions


def connect_db(dbname):
    global conn, DBNAME
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    DBNAME = dbname

    conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    conn.autocommit = True
    return HOST, USER, PORT, DBNAME


# Connect as a user role called ai to grant only read permission, this is important for tool calling
def connect_to_read_only_db(dbname):
    global read_only_conn, DBNAME
    if read_only_conn is not None:
        try:
            read_only_conn.close()
        except Exception:
            pass
    DBNAME = dbname
    read_only_conn = psycopg2.connect(host=HOST, user="ai", port=PORT, dbname=DBNAME)
    return HOST, USER, PORT, DBNAME


def connect_to_observer_db(dbname):
    global observer_conn, DBNAME
    if observer_conn is not None:
        try:
            observer_conn.close()
        except Exception:
            pass
    DBNAME = dbname
    observer_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    return observer_conn


def establish_all_connections(dbname):
    """
    Establishes all the appropriate connections required
    1. Establishses a normal connection for sql queries execution
    2. Establishses a read only connection for sql queries execution (Used by AI)
    3. Establishses a connection for observation (Used by observer AI)

    Returns:
        Only the details of normal connection, since the other 2 will be required only when user explicitly asks for it(Either while using ai or using observer)
    """
    host, user, port, target_dbname = connect_db(dbname)
    connect_to_read_only_db(dbname)
    connect_to_observer_db(dbname)
    return host, user, port, target_dbname


def executeSQL(sql):
    try:
        cur = conn.cursor()
        cur.execute(sql)

        description = cur.description  # column metadata, None for non-SELECT
        status = cur.statusmessage  # e.g. "SELECT 5", "INSERT 0 1", "CREATE TABLE"
        try:
            rows = cur.fetchall()
        except Exception:
            rows = []

        conn.commit()
        return description, rows, status
    except Exception:
        conn.rollback()
        raise


def executeSQLReadOnly(sql):
    try:
        cur = read_only_conn.cursor()
        cur.execute(sql)

        description = cur.description
        status = cur.statusmessage
        try:
            rows = cur.fetchall()
        except Exception:
            rows = []

        read_only_conn.commit()
        return description, rows, status
    except Exception:
        read_only_conn.rollback()
        raise


def reset_db():
    try:
        cur = conn.cursor()
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        tables = [row[0] for row in cur.fetchall()]
        if not tables:
            return "No tables found in the public schema."

        query = sql.SQL("TRUNCATE TABLE {} CASCADE;").format(
            sql.SQL(", ").join(map(sql.Identifier, tables))
        )
        cur.execute(query)
        conn.commit()
        return f"Successfully deleted all rows from {len(tables)} table(s)."
    except Exception:
        conn.rollback()
        raise


def reset_public_schema():
    try:
        cur = conn.cursor()
        cur.execute("DROP SCHEMA public CASCADE;")
        cur.execute("CREATE SCHEMA public;")
        cur.execute("GRANT ALL ON SCHEMA public TO postgres;")
        cur.execute("GRANT ALL ON SCHEMA public TO public;")
        conn.commit()
        return "NUKED: Dropped and recreated the 'public' schema."
    except Exception:
        conn.rollback()
        raise


def execute_meta_command(command):
    command = command.rstrip().rstrip(";")
    result = subprocess.run(
        ["psql", "-U", USER, "-d", DBNAME, "-h", HOST, "-p", PORT, "-c", command],
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    error = result.stderr.strip()
    if error:
        raise RuntimeError(error)
    return output


def execute_read_only_meta_command(command):
    command = command.rstrip().rstrip(";")
    result = subprocess.run(
        ["psql", "-U", "ai", "-d", DBNAME, "-h", HOST, "-p", PORT, "-c", command],
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    error = result.stderr.strip()
    if error:
        raise RuntimeError(error)
    return output


def create_baseline(user_name, target_dbname, schema_only=True):
    baseline_name = f"{user_name}_baseline_for_{target_dbname}"
    conn.autocommit = True
    executeSQL(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(baseline_name)))

    if schema_only:
        dump_cmd = f"pg_dump -s -U {USER} -h {HOST} -p {PORT} {target_dbname}"
    else:
        dump_cmd = f"pg_dump -U {USER} -h {HOST} -p {PORT} {target_dbname}"

    os.system(
        f"{dump_cmd} | psql -U {USER} -h {HOST} -p {PORT} -d {baseline_name} > /dev/null 2>&1"
    )
    return baseline_name


def drop_database(dbname):
    conn.autocommit = True
    executeSQL(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))


def rename_database(old_name, new_name, force=False):
    if "_baseline_for_" in old_name and not force:
        raise ValueError("Error: Renaming baseline databases is not allowed.")
    conn.autocommit = True
    executeSQL(
        sql.SQL("ALTER DATABASE {} RENAME TO {}").format(
            sql.Identifier(old_name), sql.Identifier(new_name)
        )
    )


def recreate_from_baseline(target_dbname, baseline_dbname):
    dbs = get_databases()
    other_dbs = [d for d in dbs if d != target_dbname and d != baseline_dbname]
    hop_db = other_dbs[0] if other_dbs else "template1"

    print(f"Hopping to {hop_db} to release connections...")
    establish_all_connections(hop_db)

    print("Dropping target database...")
    drop_database(target_dbname)

    print("Recreating database from baseline...")
    conn.autocommit = True
    executeSQL(f"CREATE DATABASE {target_dbname} TEMPLATE {baseline_dbname};")

    print(f"Reconnecting to freshly made {target_dbname}...")
    establish_all_connections(target_dbname)

    return f"NUKED and recreated from baseline: {baseline_dbname}"
