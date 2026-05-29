import sys
import psycopg2
from sqlalchemy import create_engine
from config import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME, DATABASE_URL
from database import Base

def create_database_if_not_exists():
    print(f"Connecting to database server at {DB_HOST}:{DB_PORT} as user '{DB_USER}'...")
    try:
        # Connect to default postgres DB first to create our application DB
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database="postgres"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if DB exists
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Database '{DB_NAME}' does not exist. Creating...")
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"Database '{DB_NAME}' created successfully.")
        else:
            print(f"Database '{DB_NAME}' already exists.")
            
        cursor.close()
        conn.close()
    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] Failed to connect to PostgreSQL server: {e}", file=sys.stderr)
        print("\nPlease ensure:", file=sys.stderr)
        print("1. PostgreSQL service is running.", file=sys.stderr)
        print(f"2. User credentials in config.py or .env are correct. (Current user: {DB_USER})", file=sys.stderr)
        print("You can set DB_USER, DB_PASSWORD, DB_HOST, DB_PORT env variables or create a '.env' file.", file=sys.stderr)
        sys.exit(1)

def init_tables():
    try:
        from database import engine
        print("Creating database tables via SQLAlchemy...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"\n[ERROR] Failed to create tables: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if DATABASE_URL.startswith("sqlite"):
        print("Using SQLite database. Initializing tables...")
        init_tables()
    else:
        create_database_if_not_exists()
        init_tables()

