import re
import os
import time
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import request, session
from backend.database import execute_query
from config import Config

# In-memory settings cache with TTL
_SETTINGS_CACHE = {}
_SETTINGS_CACHE_TIME = 0
CACHE_TTL_SECONDS = 300  # 5 minutes cache to prevent repetitive DB queries on every request

def get_client_ip():
    """Extract client IP address considering proxy headers like X-Forwarded-For."""
    if request:
        if request.headers.get("X-Forwarded-For"):
            return request.headers.get("X-Forwarded-For").split(",")[0].strip()
        return request.remote_addr or "127.0.0.1"
    return "127.0.0.1"

def log_audit(action, target_type=None, target_id=None, details=None):
    """
    Record an action into the audit_logs table.
    Pulls current user context from Flask session if available.
    """
    user_id = session.get("user_id") if session else None
    username = session.get("username", "anonymous") if session else "anonymous"
    role = session.get("role", "public") if session else "public"
    ip = get_client_ip()

    sql = """
        INSERT INTO audit_logs (user_id, username, role, action, target_type, target_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        execute_query(sql, (user_id, username, role, action, target_type, str(target_id) if target_id else None, details, ip), commit=True)
    except Exception as e:
        # Never crash the main application if audit logging encounters a database hiccup
        print(f"Warning: Failed to log audit event: {e}")

def validate_phone(phone):
    """
    Validates phone number format.
    Must be 7 to 20 characters and contain valid telephone characters (+, -, (), spaces, digits).
    """
    if not phone or not isinstance(phone, str):
        return False
    phone_clean = phone.strip()
    pattern = r"^\+?[0-9\s\-\(\)\.]{7,25}$"
    if not re.match(pattern, phone_clean):
        return False
    # Ensure there are at least 7 digits
    digits_only = re.sub(r"\D", "", phone_clean)
    return len(digits_only) >= 7

def validate_email(email):
    """Validates email format using RFC 5322 compatible pattern."""
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))

def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def save_uploaded_file(file_storage, folder_prefix="brand"):
    """
    Validate, securely name and persist an uploaded file.
    Returns relative URL path e.g. '/static/uploads/brand_xxxx.png'
    """
    if not file_storage or file_storage.filename == "":
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Invalid file extension. Allowed: PNG, JPG, JPEG, SVG, WEBP.")

    # Secure the base name and create unique prefix
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique_id = uuid.uuid4().hex[:12]
    filename = secure_filename(f"{folder_prefix}_{int(time.time())}_{unique_id}.{ext}")

    target_dir = Path(Config.UPLOAD_FOLDER)
    target_dir.mkdir(parents=True, exist_ok=True)
    save_path = target_dir / filename

    file_storage.save(str(save_path))
    return f"/static/uploads/{filename}"

def get_website_settings(force_refresh=False):
    """
    Retrieve all website settings from MySQL as a key-value dictionary.
    Includes caching for optimal response times.
    """
    global _SETTINGS_CACHE, _SETTINGS_CACHE_TIME
    now = time.time()
    if not force_refresh and _SETTINGS_CACHE and (now - _SETTINGS_CACHE_TIME < CACHE_TTL_SECONDS):
        return _SETTINGS_CACHE.copy()

    try:
        rows = execute_query("SELECT setting_key, setting_value FROM website_settings", fetch="all")
        settings = {r["setting_key"]: r["setting_value"] for r in rows}
        
        # Ensure default fallbacks exist
        defaults = {
            "site_title": "EduTrack",
            "site_tagline": "Academic Performance, Made Visible.",
            "hero_headline": "Academic Performance, Made Visible.",
            "hero_subheadline": "EduTrack brings students, teachers and academic performance together in one intelligent platform. Track progress, manage results and make better academic decisions.",
            "about_heading": "Engineered for Academic Precision",
            "about_body": "EduTrack was designed from the ground up to solve the visibility gap in modern collegiate education.",
            "features_visible": "true",
            "how_it_works_visible": "true",
            "benefits_visible": "true",
            "contact_visible": "true",
            "announcements_visible": "true",
            "primary_accent_color": "#C8F169",
            "contact_email": "contact@EduTrack.edu",
            "contact_phone": "+91 (800) 456-7890",
            "contact_college_placeholder": "Institution Name",
            "contact_address": "EduTrack Academic Complex",
            "assistance_threshold_pct": "40.0",
            "logo_url": ""
        }
        for k, v in defaults.items():
            if k not in settings:
                settings[k] = v

        _SETTINGS_CACHE = settings
        _SETTINGS_CACHE_TIME = now
        return _SETTINGS_CACHE.copy()
    except Exception as e:
        print(f"Error fetching website settings: {e}")
        return _SETTINGS_CACHE.copy() if _SETTINGS_CACHE else {}

def update_website_setting(key, value, category="general"):
    """Update or insert a website setting in MySQL and invalidate cache."""
    global _SETTINGS_CACHE_TIME
    sql = """
        INSERT INTO website_settings (setting_key, setting_value, category)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), category = VALUES(category), updated_at = NOW()
    """
    execute_query(sql, (key, str(value), category), commit=True)
    _SETTINGS_CACHE_TIME = 0  # Invalidate cache
