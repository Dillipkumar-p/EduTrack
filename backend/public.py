import time
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from backend.database import execute_query
from backend.utilities import (
    validate_phone,
    validate_email,
    get_website_settings,
    log_audit,
    get_client_ip
)
from backend.email_service import send_enquiry_notification

public_bp = Blueprint("public", __name__)

# Basic in-memory submission cooldown by IP (prevents rapid spam submissions)
_CONTACT_SUBMISSION_TIMES = {}

@public_bp.route("/")
def index():
    """Public landing page showcasing EduTrack's capabilities."""
    settings = get_website_settings()

    # Fetch active announcements
    announcements_sql = """
        SELECT title, content, badge_text, created_at
        FROM announcements
        WHERE is_active = 1
        ORDER BY priority DESC, created_at DESC
        LIMIT 5
    """
    announcements = execute_query(announcements_sql, fetch="all") or []

    return render_template(
        "public/index.html",
        settings=settings,
        announcements=announcements
    )

@public_bp.route("/contact", methods=["POST"])
def submit_contact():
    """
    Handles institutional contact enquiries with validation, DB persistence,
    and resilient SMTP email notifications.
    """
    ip = get_client_ip()
    now = time.time()

    # Rate limiting: 1 submission per 20 seconds per IP (bypassed in testing)
    last_sub = _CONTACT_SUBMISSION_TIMES.get(ip, 0)
    if not current_app.config.get("TESTING") and (now - last_sub < 20):
        flash("Please wait a moment before submitting another enquiry.", "warning")
        return redirect(url_for("public.index") + "#contact")

    # Anti-bot honeypot field check
    honeypot = request.form.get("organization_fax_code", "").strip()
    if honeypot:
        # Silently reject bots without alerting them
        return redirect(url_for("public.index") + "#contact")

    full_name = request.form.get("full_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()
    college_name = request.form.get("college_name", "").strip()
    email_address = request.form.get("email_address", "").strip()
    message = request.form.get("message", "").strip()

    # 1. Validation of required fields
    if not full_name or not phone_number or not college_name:
        flash("Please fill in all required fields: Full Name, Phone Number, and College / Institution.", "error")
        return redirect(url_for("public.index") + "#contact")

    # 2. Validate phone number format
    if not validate_phone(phone_number):
        flash("Please enter a valid phone number (at least 7 to 15 digits).", "error")
        return redirect(url_for("public.index") + "#contact")

    # 3. Validate email when supplied
    if email_address and not validate_email(email_address):
        flash("Please provide a valid email address.", "error")
        return redirect(url_for("public.index") + "#contact")

    # 4. Save enquiry into MySQL
    insert_sql = """
        INSERT INTO contact_enquiries (full_name, phone_number, college_name, email_address, message)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        res = execute_query(
            insert_sql,
            (full_name, phone_number, college_name, email_address or None, message or None),
            commit=True
        )
        enquiry_id = res["lastrowid"]
        _CONTACT_SUBMISSION_TIMES[ip] = now
        log_audit("CONTACT_ENQUIRY_SUBMITTED", target_type="contact_enquiries", target_id=enquiry_id, details=f"From: {college_name}")
    except Exception as err:
        flash("A database error occurred while recording your enquiry. Please try again shortly.", "error")
        return redirect(url_for("public.index") + "#contact")

    # 5. Send email notification (errors handled gracefully inside)
    enquiry_payload = {
        "enquiry_id": enquiry_id,
        "full_name": full_name,
        "phone_number": phone_number,
        "college_name": college_name,
        "email_address": email_address,
        "message": message
    }
    send_enquiry_notification(enquiry_payload)

    # 6. Success response
    flash("Thank you for reaching out! Your enquiry has been received. Our institutional onboarding team will contact you shortly.", "success")
    return redirect(url_for("public.index") + "#contact")
