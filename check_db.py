"""
EduTrack Database Health Diagnostic
Run with: python check_db.py
Verifies connection to MySQL (Local or Aiven Cloud) and reports table status.
"""
import sys
import mysql.connector
from config import Config
from backend.database import get_connection_config

def main():
    print("=" * 60)
    print(" EduTrack Database Diagnostic Check")
    print("=" * 60)
    cfg = get_connection_config()
    masked_pw = ("*" * len(cfg["password"])) if cfg["password"] else "(empty)"
    print(f"Target Host:     {cfg['host']}:{cfg['port']}")
    print(f"User:            {cfg['user']}")
    print(f"Password:        {masked_pw}")
    print(f"Database:        {cfg['database']}")
    print(f"SSL CA Path:     {Config.MYSQL_SSL_CA or '(not set)'}")
    print("-" * 60)

    try:
        conn = mysql.connector.connect(**cfg)
        print("[OK] SUCCESS: Successfully connected to MySQL database!")
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()
        print(f"[OK] MySQL Engine Version: {version[0] if version else 'Unknown'}")

        cursor.execute("SHOW TABLES;")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"[OK] Total Tables Present ({len(tables)}):")
        for tbl in sorted(tables):
            cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
            count = cursor.fetchone()[0]
            print(f"   - {tbl:<22} ({count} records)")

        cursor.close()
        conn.close()
        print("-" * 60)
        print("[OK] Database diagnostic passed cleanly. Ready for production.")
        print("=" * 60)
        return 0
    except mysql.connector.Error as err:
        print("[X] CONNECTION FAILED:")
        print(f"   Error Code: {err.errno}")
        print(f"   SQLSTATE:   {err.sqlstate}")
        print(f"   Message:    {err.msg}")
        print("-" * 60)
        print("Troubleshooting tips:")
        print(" 1. Check your .env file or Render/Aiven environment variables.")
        print(" 2. Verify that your MySQL host, port, user, and password are correct.")
        print(" 3. For Aiven Cloud MySQL, ensure your service is running and SSL is enabled.")
        print(" 4. Run 'python app.py init-db' to initialize database tables if missing.")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
