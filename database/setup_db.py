import os
import sys
from psycopg import connect, Connection
from psycopg.errors import DuplicateDatabase
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "querypilot")

if not DB_PASSWORD:
    print("Error: DB_PASSWORD is not set in your .env file.")
    print("Please open .env and set your password before running this script.")
    sys.exit(1)

def run_sql_file(conn: Connection, filepath: str):
    """Reads and executes a SQL file."""
    print(f"Executing {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
    
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print(f"Successfully executed {filepath}.")

def main():
    # 1. Connect to default database 'postgres' to create the target database if not exists
    print(f"Connecting to default database 'postgres' at {DB_HOST}:{DB_PORT} as user {DB_USER}...")
    try:
        # Autocommit mode is required for CREATE DATABASE
        conn = connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname="postgres",
            autocommit=True
        )
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        print("\nPlease make sure:")
        print("1. The PostgreSQL server is running.")
        print("2. The username, host, and port in your .env are correct.")
        print("3. Your DB_PASSWORD is correct.")
        sys.exit(1)

    # Check if database exists, if not create it
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            exists = cur.fetchone()
            if not exists:
                print(f"Database '{DB_NAME}' does not exist. Creating...")
                cur.execute(f'CREATE DATABASE "{DB_NAME}"')
                print(f"Database '{DB_NAME}' created successfully.")
            else:
                print(f"Database '{DB_NAME}' already exists.")
    except DuplicateDatabase:
        print(f"Database '{DB_NAME}' already exists (handled conflict).")
    except Exception as e:
        print(f"Error checking/creating database: {e}")
        conn.close()
        sys.exit(1)
    finally:
        conn.close()

    # 2. Connect to the target database and execute schema & seed files
    print(f"\nConnecting to target database '{DB_NAME}'...")
    try:
        target_conn = connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
    except Exception as e:
        print(f"Failed to connect to target database '{DB_NAME}': {e}")
        sys.exit(1)

    try:
        # Run schema DDL
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        run_sql_file(target_conn, schema_path)

        # Run seed DML
        seed_path = os.path.join(os.path.dirname(__file__), "seed.sql")
        run_sql_file(target_conn, seed_path)

        print("\nDatabase initialization complete! PostgreSQL tables are ready.")

    except Exception as e:
        print(f"Error executing setup files: {e}")
        target_conn.rollback()
        sys.exit(1)
    finally:
        target_conn.close()

if __name__ == "__main__":
    main()
