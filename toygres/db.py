import psycopg2
from psycopg2 import sql
import subprocess

conn = None

HOST = "localhost"
USER = "postgres"
PORT = "5432"
DBNAME = "postgres"


def get_databases():
    temp_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname="postgres")
    temp_conn.autocommit = True
    with temp_conn.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        dbs = [row[0] for row in cur.fetchall()]
    temp_conn.close()
    return dbs


def create_database(new_dbname):
    temp_conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname="postgres")
    temp_conn.autocommit = True
    with temp_conn.cursor() as cur:
        query = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_dbname))
        cur.execute(query)
    temp_conn.close()


def connect_db(dbname):
    global conn, DBNAME
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    DBNAME = dbname
    conn = psycopg2.connect(host=HOST, user=USER, port=PORT, dbname=DBNAME)
    return HOST, USER, PORT, DBNAME


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


def atom_bomb():
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


def executepsql(command):
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
