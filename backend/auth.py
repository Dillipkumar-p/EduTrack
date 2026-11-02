import time
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import check_password_hash, generate_password_hash
from backend.database import execute_query
from backend.utilities import log_audit, get_client_ip

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# In-memory login attempt tracker for rate limiting
# Key: ip_address -> list of failed attempt timestamps
_LOGIN_ATTEMPTS = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_PERIOD_SECONDS = 300  # 5 minutes

def is_rate_limited(ip):
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(ip, [])
    # Filter attempts within lockout window
    recent = [t for t in attempts if now - t < LOCKOUT_PERIOD_SECONDS]
    _LOGIN_ATTEMPTS[ip] = recent
    return len(recent) >= MAX_FAILED_ATTEMPTS

def record_failed_attempt(ip):
    now = time.time()
    if ip not in _LOGIN_ATTEMPTS:
        _LOGIN_ATTEMPTS[ip] = []
    _LOGIN_ATTEMPTS[ip].append(now)

def clear_failed_attempts(ip):
    if ip in _LOGIN_ATTEMPTS:
        del _LOGIN_ATTEMPTS[ip]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            user_role = session.get("role")

            if not user_id:
                flash("Please sign in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.url))

            if user_role not in allowed_roles:
                log_audit("UNAUTHORIZED_ACCESS_ATTEMPT", details=f"Attempted {request.path} requiring {allowed_roles}")
                flash("Access denied: You do not have permission to access that resource.", "error")
                # Redirect to appropriate home according to actual role
                if user_role == "admin":
                    return redirect(url_for("admin.dashboard"))
                elif user_role == "teacher":
                    return redirect(url_for("teacher.dashboard"))
                elif user_role == "student":
                    return redirect(url_for("student.dashboard"))
                else:
                    return redirect(url_for("public.index"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, redirect to respective dashboard
    if session.get("user_id") and session.get("role"):
        role = session["role"]
        if role == "admin":
            return redirect(url_for("admin.dashboard"))
        elif role == "teacher":
            return redirect(url_for("teacher.dashboard"))
        elif role == "student":
            return redirect(url_for("student.dashboard"))

    client_ip = get_client_ip()

    if request.method == "POST":
        if is_rate_limited(client_ip):
            flash("Too many failed login attempts. Please wait 5 minutes before trying again.", "error")
            return render_template("auth/login.html", rate_limited=True)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please provide both username and password.", "error")
            return render_template("auth/login.html")

        # Query user securely
        user_sql = """
            SELECT user_id, username, email, password_hash, role, is_active
            FROM users
            WHERE username = %s OR email = %s
            LIMIT 1
        """
        user = execute_query(user_sql, (username, username), fetch="one")

        if not user or not check_password_hash(user["password_hash"], password):
            record_failed_attempt(client_ip)
            log_audit("LOGIN_FAILED", target_type="user", details=f"Failed attempt for identifier: {username}")
            flash("Invalid credentials. Please verify your username and password.", "error")
            return render_template("auth/login.html")

        if not user["is_active"]:
            log_audit("LOGIN_BLOCKED_INACTIVE", target_type="user", target_id=user["user_id"])
            flash("Your account has been deactivated. Please contact the administrator.", "error")
            return render_template("auth/login.html")

        # Successful login
        clear_failed_attempts(client_ip)
        session.clear()  # Prevent session fixation
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["email"] = user["email"]
        session["role"] = user["role"]
        session.permanent = True

        # Fetch role-specific details
        if user["role"] == "student":
            student_sql = "SELECT student_id, roll_no, full_name, section FROM students WHERE user_id = %s"
            stu = execute_query(student_sql, (user["user_id"],), fetch="one")
            if stu:
                session["student_id"] = stu["student_id"]
                session["roll_no"] = stu["roll_no"]
                session["full_name"] = stu["full_name"]
                session["section"] = stu["section"]
        elif user["role"] == "teacher":
            teacher_sql = "SELECT teacher_id, employee_id, full_name, department FROM teachers WHERE user_id = %s"
            tch = execute_query(teacher_sql, (user["user_id"],), fetch="one")
            if tch:
                session["teacher_id"] = tch["teacher_id"]
                session["employee_id"] = tch["employee_id"]
                session["full_name"] = tch["full_name"]
                session["department"] = tch["department"]
        elif user["role"] == "admin":
            session["full_name"] = "System Administrator"

        # Update last login timestamp
        execute_query("UPDATE users SET last_login = NOW() WHERE user_id = %s", (user["user_id"],), commit=True)
        log_audit("LOGIN_SUCCESS", target_type="user", target_id=user["user_id"])

        flash(f"Welcome back, {session.get('full_name', user['username'])}!", "success")

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        if user["role"] == "admin":
            return redirect(url_for("admin.dashboard"))
        elif user["role"] == "teacher":
            return redirect(url_for("teacher.dashboard"))
        elif user["role"] == "student":
            return redirect(url_for("student.dashboard"))
        else:
            return redirect(url_for("public.index"))

    return render_template("auth/login.html")

@auth_bp.route("/demo")
def demo_login():
    """Instant one-click demo login for reviewing the student portal safely."""
    # Find active student in system
    student = execute_query(
        """SELECT s.student_id, s.roll_no, s.full_name, s.section, u.user_id, u.username, u.email, u.role
           FROM students s
           JOIN users u ON s.user_id = u.user_id
           WHERE u.is_active = 1
           ORDER BY s.student_id ASC
           LIMIT 1""",
        fetch="one"
    )

    if not student:
        flash("No active student records available for demo. Please login with your credentials.", "warning")
        return redirect(url_for("auth.login"))

    session.clear()
    session["user_id"] = student["user_id"]
    session["username"] = student["username"]
    session["email"] = student["email"]
    session["role"] = "student"
    session["student_id"] = student["student_id"]
    session["roll_no"] = student["roll_no"]
    session["full_name"] = student["full_name"]
    session["section"] = student["section"]
    session["is_demo"] = True
    session.permanent = True

    log_audit("DEMO_STUDENT_ACCESSED", target_type="user", target_id=student["user_id"], details="Visitor explored student demo portal")
    flash(f"Welcome to the Student Interactive Demo as {student['full_name']} ({student['roll_no']})!", "info")
    return redirect(url_for("student.dashboard"))

@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id:
        log_audit("LOGOUT", target_type="user", target_id=user_id)
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("public.index"))
