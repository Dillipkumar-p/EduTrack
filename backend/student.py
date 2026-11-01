from flask import Blueprint, render_template, redirect, url_for, flash, session
from backend.auth import login_required, role_required
from backend.database import execute_query
from backend.analytics import get_student_academic_summary, calculate_grade
from backend.utilities import get_website_settings

student_bp = Blueprint("student", __name__, url_prefix="/student")

@student_bp.before_request
@login_required
@role_required("student")
def ensure_student():
    """Security Boundary: Strictly derives identity from session."""
    pass

def get_current_student_id():
    """Derives verified student_id purely from authenticated session user_id."""
    sid = session.get("student_id")
    if sid:
        return sid
    uid = session.get("user_id")
    row = execute_query("SELECT student_id, roll_no, full_name, section FROM students WHERE user_id = %s", (uid,), fetch="one")
    if row:
        session["student_id"] = row["student_id"]
        session["roll_no"] = row["roll_no"]
        session["full_name"] = row["full_name"]
        session["section"] = row["section"]
        return row["student_id"]
    return None

@student_bp.route("/dashboard")
def dashboard():
    student_id = get_current_student_id()
    if not student_id:
        flash("Student profile not found. Please contact administration.", "error")
        return redirect(url_for("public.index"))

    summary = get_student_academic_summary(student_id)
    settings = get_website_settings()

    # Active announcements
    announcements = execute_query(
        "SELECT title, content, badge_text, created_at FROM announcements WHERE is_active = 1 ORDER BY priority DESC LIMIT 3",
        fetch="all"
    ) or []

    return render_template(
        "student/dashboard.html",
        summary=summary,
        settings=settings,
        announcements=announcements
    )

@student_bp.route("/profile")
def profile():
    student_id = get_current_student_id()
    sql = """
        SELECT s.student_id, s.roll_no, s.full_name, s.email, s.phone, s.section, s.batch_year, u.created_at, u.last_login
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.student_id = %s
    """
    student_info = execute_query(sql, (student_id,), fetch="one")
    return render_template("student/profile.html", student=student_info)

@student_bp.route("/results")
def results():
    student_id = get_current_student_id()
    summary = get_student_academic_summary(student_id)
    return render_template("student/results.html", summary=summary)

@student_bp.route("/performance")
def performance():
    student_id = get_current_student_id()
    summary = get_student_academic_summary(student_id)
    return render_template("student/performance.html", summary=summary)

@student_bp.route("/report")
def report():
    """Printable official academic scorecard and transcript."""
    student_id = get_current_student_id()
    summary = get_student_academic_summary(student_id)
    settings = get_website_settings()
    return render_template("student/report_print.html", summary=summary, settings=settings)
