import os
import sys
from backend import create_app
from backend.database import init_database_schema, execute_query
from werkzeug.security import generate_password_hash

app = create_app()

def run_init_db():
    print("Initializing EduTrack MySQL schema from database.sql...")
    success = init_database_schema()
    if success:
        print("[OK] EduTrack MySQL schema initialized/verified successfully.")
    else:
        print("[X] Database initialization failed. Please inspect your .env credentials.")

def run_create_admin():
    import getpass
    print("=" * 50)
    print(" EduTrack Initial Administrator Setup")
    print("=" * 50)
    username = input("Enter admin username [admin]: ").strip() or "admin"
    email = input("Enter admin email [admin@edutrack.edu]: ").strip() or "admin@edutrack.edu"
    password = getpass.getpass("Enter secure admin password: ").strip()

    if not password or len(password) < 6:
        print("[X] Error: Password must be at least 6 characters.")
        return

    password_hash = generate_password_hash(password)
    sql = """
        INSERT INTO users (username, email, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'admin', 1)
        ON DUPLICATE KEY UPDATE email = VALUES(email), password_hash = VALUES(password_hash), is_active = 1
    """
    try:
        execute_query(sql, (username, email, password_hash), commit=True)
        print(f"[OK] Administrator '{username}' configured successfully.")
    except Exception as e:
        print(f"[X] Database error: {e}")

@app.cli.command("init-db")
def init_db_command():
    """CLI command to initialize MySQL tables and seed records."""
    run_init_db()

@app.cli.command("create-admin")
def create_admin_command():
    """CLI command to create or reset the administrator account."""
    run_create_admin()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "init-db":
            run_init_db()
            sys.exit(0)
        elif cmd == "create-admin":
            run_create_admin()
            sys.exit(0)

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    print(f"Starting EduTrack on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
