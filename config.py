import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "edutrack-production-secret-key-default-2026-v1")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")

    # MySQL Database Settings
    # Primary variables support both standard naming and fallback aliases
    MYSQL_HOST = os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER") or os.getenv("DB_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE") or os.getenv("DB_NAME", "edutrack_db")
    MYSQL_SSL_CA = os.getenv("MYSQL_SSL_CA") or os.getenv("DB_SSL_CA", "")
    DB_SSL = os.getenv("DB_SSL", "false").lower() in ("true", "1", "yes")

    # Connection pooling configuration
    DB_POOL_NAME = "edutrack_pool"
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))

    # File uploads
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB limit
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "svg", "webp"}

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    # Contact & SMTP settings
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@edutrack.edu")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", os.getenv("ADMIN_EMAIL", "notifications@edutrack.edu"))

    # WTForms / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
