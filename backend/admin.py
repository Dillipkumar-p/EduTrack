import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from backend.auth import login_required, role_required
from backend.database import execute_query, execute_transaction
from backend.utilities import (
    log_audit,
    get_website_settings,
    update_website_setting,
    save_uploaded_file,
    validate_email,
    validate_phone
)
from backend.analytics import get_institutional_analytics, get_student_academic_summary

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.before_request
@login_required
@role_required("admin")
def ensure_admin():
    """Ensure every route in this blueprint is restricted to authenticated administrators."""
    pass

# ------------------------------------------------------------------------------
# 1. OVERVIEW DASHBOARD
# ------------------------------------------------------------------------------
@admin_bp.route("/dashboard")
def dashboard():
    analytics = get_institutional_analytics()
    
    # Recent enquiries
    recent_enquiries = execute_query(
        "SELECT enquiry_id, full_name, college_name, phone_number, is_contacted, created_at FROM contact_enquiries ORDER BY created_at DESC LIMIT 5",
        fetch="all"
    ) or []

    # Recent marks entered
    recent_marks = execute_query(
        """SELECT m.mark_id, m.marks_obtained, m.max_marks, s.roll_no, s.full_name, sub.subject_name, e.exam_name, m.created_at
           FROM marks m
           JOIN students s ON m.student_id = s.student_id
           JOIN subjects sub ON m.subject_id = sub.subject_id
           JOIN examinations e ON m.exam_id = e.exam_id
           ORDER BY m.created_at DESC LIMIT 6""",
        fetch="all"
    ) or []

    return render_template(
        "admin/dashboard.html",
        analytics=analytics,
        recent_enquiries=recent_enquiries,
        recent_marks=recent_marks
    )

# ------------------------------------------------------------------------------
# 2. STUDENT MANAGEMENT
# ------------------------------------------------------------------------------
@admin_bp.route("/students")
def students():
    search = request.args.get("q", "").strip()
    section = request.args.get("section", "").strip()

    sql = """
        SELECT s.student_id, s.user_id, s.roll_no, s.full_name, s.email, s.phone, s.section, s.batch_year, u.is_active, u.created_at
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (s.roll_no LIKE %s OR s.full_name LIKE %s OR s.email LIKE %s)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])
    if section:
        sql += " AND s.section = %s"
        params.append(section)

    sql += " ORDER BY s.roll_no ASC"
    student_list = execute_query(sql, tuple(params), fetch="all") or []

    # Get distinct sections for filter dropdown
    sections = execute_query("SELECT DISTINCT section FROM students ORDER BY section ASC", fetch="all") or []
    section_names = [s["section"] for s in sections]

    return render_template(
        "admin/students.html",
        students=student_list,
        sections=section_names,
        search=search,
        selected_section=section
    )

@admin_bp.route("/students/add", methods=["POST"])
def add_student():
    full_name = request.form.get("full_name", "").strip()
    roll_no = request.form.get("roll_no", "").strip().upper()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    section = request.form.get("section", "A").strip().upper()
    batch_year = request.form.get("batch_year", "2024-2028").strip()
    raw_password = request.form.get("password", "").strip() or f"EduTrack@{roll_no}"

    if not full_name or not roll_no or not email:
        flash("Full name, Roll Number, and Email are required.", "error")
        return redirect(url_for("admin.students"))

    if not validate_email(email):
        flash("Please provide a valid student email address.", "error")
        return redirect(url_for("admin.students"))

    # Check for existing username/roll_no or email
    existing_user = execute_query("SELECT user_id FROM users WHERE username = %s OR email = %s", (roll_no, email), fetch="one")
    if existing_user:
        flash(f"An account with Roll Number '{roll_no}' or Email '{email}' already exists.", "error")
        return redirect(url_for("admin.students"))

    existing_roll = execute_query("SELECT student_id FROM students WHERE roll_no = %s", (roll_no,), fetch="one")
    if existing_roll:
        flash(f"Student with roll number '{roll_no}' already exists.", "error")
        return redirect(url_for("admin.students"))

    # Create user + student in transaction
    password_hash = generate_password_hash(raw_password)
    user_insert = execute_query(
        "INSERT INTO users (username, email, password_hash, role, is_active) VALUES (%s, %s, %s, 'student', 1)",
        (roll_no, email, password_hash),
        commit=True
    )
    user_id = user_insert["lastrowid"]

    execute_query(
        """INSERT INTO students (user_id, roll_no, full_name, email, phone, section, batch_year)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, roll_no, full_name, email, phone or None, section, batch_year),
        commit=True
    )

    log_audit("STUDENT_CREATED", target_type="student", target_id=roll_no, details=f"Created {full_name} ({roll_no})")
    flash(f"Student '{full_name}' ({roll_no}) created successfully. Initial password: {raw_password}", "success")
    return redirect(url_for("admin.students"))

@admin_bp.route("/students/edit/<int:student_id>", methods=["POST"])
def edit_student(student_id):
    student = execute_query("SELECT student_id, user_id, roll_no FROM students WHERE student_id = %s", (student_id,), fetch="one")
    if not student:
        flash("Student record not found.", "error")
        return redirect(url_for("admin.students"))

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    section = request.form.get("section", "A").strip().upper()
    batch_year = request.form.get("batch_year", "2024-2028").strip()
    is_active = 1 if request.form.get("is_active") == "1" else 0
    new_password = request.form.get("new_password", "").strip()

    if not full_name or not email:
        flash("Full name and email cannot be empty.", "error")
        return redirect(url_for("admin.students"))

    # Check duplicate email
    dup_email = execute_query("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (email, student["user_id"]), fetch="one")
    if dup_email:
        flash(f"Email '{email}' is already in use by another user.", "error")
        return redirect(url_for("admin.students"))

    # Update student record
    execute_query(
        """UPDATE students SET full_name = %s, email = %s, phone = %s, section = %s, batch_year = %s
           WHERE student_id = %s""",
        (full_name, email, phone or None, section, batch_year, student_id),
        commit=True
    )

    # Update user record
    if new_password:
        pwd_hash = generate_password_hash(new_password)
        execute_query("UPDATE users SET email = %s, is_active = %s, password_hash = %s WHERE user_id = %s",
                      (email, is_active, pwd_hash, student["user_id"]), commit=True)
        log_audit("STUDENT_PASSWORD_RESET", target_type="user", target_id=student["user_id"])
    else:
        execute_query("UPDATE users SET email = %s, is_active = %s WHERE user_id = %s",
                      (email, is_active, student["user_id"]), commit=True)

    log_audit("STUDENT_UPDATED", target_type="student", target_id=student_id, details=f"Updated {full_name}")
    flash(f"Student record for '{full_name}' updated successfully.", "success")
    return redirect(url_for("admin.students"))

@admin_bp.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    student = execute_query("SELECT student_id, user_id, full_name, roll_no FROM students WHERE student_id = %s", (student_id,), fetch="one")
    if not student:
        flash("Student record not found.", "error")
        return redirect(url_for("admin.students"))

    # Deleting user will cascade delete student and marks cleanly
    execute_query("DELETE FROM users WHERE user_id = %s", (student["user_id"],), commit=True)
    log_audit("STUDENT_DELETED", target_type="student", target_id=student["roll_no"], details=f"Deleted {student['full_name']}")
    flash(f"Student '{student['full_name']}' ({student['roll_no']}) and associated records deleted.", "info")
    return redirect(url_for("admin.students"))

# ------------------------------------------------------------------------------
# 3. TEACHER MANAGEMENT
# ------------------------------------------------------------------------------
@admin_bp.route("/teachers")
def teachers():
    search = request.args.get("q", "").strip()
    sql = """
        SELECT t.teacher_id, t.user_id, t.employee_id, t.full_name, t.email, t.phone, t.department, t.designation, u.is_active, u.created_at
        FROM teachers t
        JOIN users u ON t.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (t.employee_id LIKE %s OR t.full_name LIKE %s OR t.email LIKE %s)"
        pat = f"%{search}%"
        params.extend([pat, pat, pat])
    sql += " ORDER BY t.full_name ASC"

    teacher_list = execute_query(sql, tuple(params), fetch="all") or []
    all_subjects = execute_query("SELECT subject_id, subject_code, subject_name FROM subjects WHERE is_active = 1", fetch="all") or []

    # Fetch assignments for all teachers
    assignments_raw = execute_query(
        """SELECT ta.teacher_id, ta.assignment_id, ta.section, s.subject_name, s.subject_code
           FROM teacher_assignments ta
           JOIN subjects s ON ta.subject_id = s.subject_id""",
        fetch="all"
    ) or []

    assignments_map = {}
    for a in assignments_raw:
        tid = a["teacher_id"]
        if tid not in assignments_map:
            assignments_map[tid] = []
        assignments_map[tid].append(a)

    return render_template(
        "admin/teachers.html",
        teachers=teacher_list,
        subjects=all_subjects,
        assignments_map=assignments_map,
        search=search
    )

@admin_bp.route("/teachers/add", methods=["POST"])
def add_teacher():
    full_name = request.form.get("full_name", "").strip()
    employee_id = request.form.get("employee_id", "").strip().upper()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "Computer Science & Engineering").strip()
    designation = request.form.get("designation", "Assistant Professor").strip()
    raw_password = request.form.get("password", "").strip() or f"Teach@{employee_id}"

    if not full_name or not employee_id or not email:
        flash("Full name, Employee ID, and Email are required.", "error")
        return redirect(url_for("admin.teachers"))

    if not validate_email(email):
        flash("Please provide a valid email address.", "error")
        return redirect(url_for("admin.teachers"))

    existing_user = execute_query("SELECT user_id FROM users WHERE username = %s OR email = %s", (employee_id, email), fetch="one")
    if existing_user:
        flash(f"User with Employee ID '{employee_id}' or Email '{email}' already exists.", "error")
        return redirect(url_for("admin.teachers"))

    password_hash = generate_password_hash(raw_password)
    user_res = execute_query(
        "INSERT INTO users (username, email, password_hash, role, is_active) VALUES (%s, %s, %s, 'teacher', 1)",
        (employee_id, email, password_hash),
        commit=True
    )
    user_id = user_res["lastrowid"]

    execute_query(
        """INSERT INTO teachers (user_id, employee_id, full_name, email, phone, department, designation)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, employee_id, full_name, email, phone or None, department, designation),
        commit=True
    )

    log_audit("TEACHER_CREATED", target_type="teacher", target_id=employee_id, details=f"Created {full_name}")
    flash(f"Faculty member '{full_name}' ({employee_id}) registered successfully. Initial password: {raw_password}", "success")
    return redirect(url_for("admin.teachers"))

@admin_bp.route("/teachers/edit/<int:teacher_id>", methods=["POST"])
def edit_teacher(teacher_id):
    teacher = execute_query("SELECT teacher_id, user_id, employee_id FROM teachers WHERE teacher_id = %s", (teacher_id,), fetch="one")
    if not teacher:
        flash("Teacher record not found.", "error")
        return redirect(url_for("admin.teachers"))

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()
    is_active = 1 if request.form.get("is_active") == "1" else 0
    new_password = request.form.get("new_password", "").strip()

    if not full_name or not email:
        flash("Full name and email are required.", "error")
        return redirect(url_for("admin.teachers"))

    execute_query(
        """UPDATE teachers SET full_name = %s, email = %s, phone = %s, department = %s, designation = %s
           WHERE teacher_id = %s""",
        (full_name, email, phone or None, department, designation, teacher_id),
        commit=True
    )

    if new_password:
        pwd_hash = generate_password_hash(new_password)
        execute_query("UPDATE users SET email = %s, is_active = %s, password_hash = %s WHERE user_id = %s",
                      (email, is_active, pwd_hash, teacher["user_id"]), commit=True)
        log_audit("TEACHER_PASSWORD_RESET", target_type="user", target_id=teacher["user_id"])
    else:
        execute_query("UPDATE users SET email = %s, is_active = %s WHERE user_id = %s",
                      (email, is_active, teacher["user_id"]), commit=True)

    log_audit("TEACHER_UPDATED", target_type="teacher", target_id=teacher_id)
    flash(f"Teacher details for '{full_name}' updated successfully.", "success")
    return redirect(url_for("admin.teachers"))

@admin_bp.route("/teachers/assign/<int:teacher_id>", methods=["POST"])
def assign_subject_teacher(teacher_id):
    subject_id = request.form.get("subject_id")
    section = request.form.get("section", "All").strip().upper()

    if not subject_id:
        flash("Please select a subject to assign.", "error")
        return redirect(url_for("admin.teachers"))

    try:
        execute_query(
            "INSERT INTO teacher_assignments (teacher_id, subject_id, section) VALUES (%s, %s, %s)",
            (teacher_id, subject_id, section),
            commit=True
        )
        log_audit("TEACHER_ASSIGNED_SUBJECT", target_type="teacher", target_id=teacher_id, details=f"Sub {subject_id}, Sec {section}")
        flash("Subject assignment added successfully.", "success")
    except Exception as e:
        flash("This teacher is already assigned to this subject and section.", "warning")

    return redirect(url_for("admin.teachers"))

@admin_bp.route("/teachers/delete/<int:teacher_id>", methods=["POST"])
def delete_teacher(teacher_id):
    teacher = execute_query("SELECT teacher_id, user_id, full_name, employee_id FROM teachers WHERE teacher_id = %s", (teacher_id,), fetch="one")
    if not teacher:
        flash("Teacher not found.", "error")
        return redirect(url_for("admin.teachers"))

    execute_query("DELETE FROM users WHERE user_id = %s", (teacher["user_id"],), commit=True)
    log_audit("TEACHER_DELETED", target_type="teacher", target_id=teacher["employee_id"], details=f"Deleted {teacher['full_name']}")
    flash(f"Teacher account '{teacher['full_name']}' deleted.", "info")
    return redirect(url_for("admin.teachers"))

# ------------------------------------------------------------------------------
# 4. SUBJECT MANAGEMENT
# ------------------------------------------------------------------------------
@admin_bp.route("/subjects")
def subjects():
    subject_list = execute_query(
        """SELECT s.subject_id, s.subject_code, s.subject_name, s.max_marks, s.pass_marks, s.is_active,
                  COUNT(m.mark_id) AS marks_count
           FROM subjects s
           LEFT JOIN marks m ON s.subject_id = m.subject_id
           GROUP BY s.subject_id
           ORDER BY s.subject_code ASC""",
        fetch="all"
    ) or []
    return render_template("admin/subjects.html", subjects=subject_list)

@admin_bp.route("/subjects/add", methods=["POST"])
def add_subject():
    subject_code = request.form.get("subject_code", "").strip().upper()
    subject_name = request.form.get("subject_name", "").strip()
    max_marks = int(request.form.get("max_marks", 100))
    pass_marks = int(request.form.get("pass_marks", 40))

    if not subject_code or not subject_name:
        flash("Subject code and subject name are required.", "error")
        return redirect(url_for("admin.subjects"))

    if pass_marks > max_marks:
        flash("Pass marks cannot exceed maximum marks.", "error")
        return redirect(url_for("admin.subjects"))

    try:
        execute_query(
            "INSERT INTO subjects (subject_code, subject_name, max_marks, pass_marks, is_active) VALUES (%s, %s, %s, %s, 1)",
            (subject_code, subject_name, max_marks, pass_marks),
            commit=True
        )
        log_audit("SUBJECT_CREATED", target_type="subject", target_id=subject_code, details=subject_name)
        flash(f"Subject '{subject_name}' ({subject_code}) created successfully.", "success")
    except Exception:
        flash(f"A subject with code '{subject_code}' already exists.", "error")

    return redirect(url_for("admin.subjects"))

@admin_bp.route("/subjects/edit/<int:subject_id>", methods=["POST"])
def edit_subject(subject_id):
    subject_name = request.form.get("subject_name", "").strip()
    max_marks = int(request.form.get("max_marks", 100))
    pass_marks = int(request.form.get("pass_marks", 40))
    is_active = 1 if request.form.get("is_active") == "1" else 0

    if not subject_name:
        flash("Subject name is required.", "error")
        return redirect(url_for("admin.subjects"))

    execute_query(
        "UPDATE subjects SET subject_name = %s, max_marks = %s, pass_marks = %s, is_active = %s WHERE subject_id = %s",
        (subject_name, max_marks, pass_marks, is_active, subject_id),
        commit=True
    )
    log_audit("SUBJECT_UPDATED", target_type="subject", target_id=subject_id)
    flash("Subject updated successfully.", "success")
    return redirect(url_for("admin.subjects"))

@admin_bp.route("/subjects/delete/<int:subject_id>", methods=["POST"])
def delete_subject(subject_id):
    # Check if marks are associated
    count = execute_query("SELECT COUNT(*) AS c FROM marks WHERE subject_id = %s", (subject_id,), fetch="val")
    if count and count > 0:
        flash(f"Cannot delete subject: {count} student marks are linked. Deactivate it instead.", "error")
        return redirect(url_for("admin.subjects"))

    execute_query("DELETE FROM subjects WHERE subject_id = %s", (subject_id,), commit=True)
    log_audit("SUBJECT_DELETED", target_type="subject", target_id=subject_id)
    flash("Subject deleted successfully.", "info")
    return redirect(url_for("admin.subjects"))

# ------------------------------------------------------------------------------
# 5. EXAMINATION MANAGEMENT
# ------------------------------------------------------------------------------
@admin_bp.route("/examinations")
def examinations():
    exam_list = execute_query(
        """SELECT e.exam_id, e.exam_code, e.exam_name, e.exam_type, e.default_max_marks, e.default_pass_marks,
                  e.academic_term, e.exam_date, e.is_active, COUNT(m.mark_id) AS marks_count
           FROM examinations e
           LEFT JOIN marks m ON e.exam_id = m.exam_id
           GROUP BY e.exam_id
           ORDER BY e.exam_id ASC""",
        fetch="all"
    ) or []
    return render_template("admin/examinations.html", examinations=exam_list)

@admin_bp.route("/examinations/add", methods=["POST"])
def add_examination():
    exam_code = request.form.get("exam_code", "").strip().upper()
    exam_name = request.form.get("exam_name", "").strip()
    exam_type = request.form.get("exam_type", "custom")
    max_marks = int(request.form.get("default_max_marks", 100))
    pass_marks = int(request.form.get("default_pass_marks", 40))
    academic_term = request.form.get("academic_term", "Semester 1").strip()
    exam_date = request.form.get("exam_date", "").strip() or None

    if not exam_code or not exam_name:
        flash("Examination code and name are required.", "error")
        return redirect(url_for("admin.examinations"))

    try:
        execute_query(
            """INSERT INTO examinations (exam_code, exam_name, exam_type, default_max_marks, default_pass_marks, academic_term, exam_date, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)""",
            (exam_code, exam_name, exam_type, max_marks, pass_marks, academic_term, exam_date),
            commit=True
        )
        log_audit("EXAMINATION_CREATED", target_type="examination", target_id=exam_code)
        flash(f"Examination '{exam_name}' created successfully.", "success")
    except Exception:
        flash(f"An examination with code '{exam_code}' already exists.", "error")

    return redirect(url_for("admin.examinations"))

@admin_bp.route("/examinations/edit/<int:exam_id>", methods=["POST"])
def edit_examination(exam_id):
    exam_name = request.form.get("exam_name", "").strip()
    max_marks = int(request.form.get("default_max_marks", 100))
    pass_marks = int(request.form.get("default_pass_marks", 40))
    academic_term = request.form.get("academic_term", "Semester 1").strip()
    exam_date = request.form.get("exam_date", "").strip() or None
    is_active = 1 if request.form.get("is_active") == "1" else 0

    execute_query(
        """UPDATE examinations
           SET exam_name = %s, default_max_marks = %s, default_pass_marks = %s, academic_term = %s, exam_date = %s, is_active = %s
           WHERE exam_id = %s""",
        (exam_name, max_marks, pass_marks, academic_term, exam_date, is_active, exam_id),
        commit=True
    )
    log_audit("EXAMINATION_UPDATED", target_type="examination", target_id=exam_id)
    flash("Examination updated successfully.", "success")
    return redirect(url_for("admin.examinations"))

# ------------------------------------------------------------------------------
# 6. MARKS OVERVIEW
# ------------------------------------------------------------------------------
@admin_bp.route("/marks")
def marks():
    exam_filter = request.args.get("exam_id", "")
    subject_filter = request.args.get("subject_id", "")
    section_filter = request.args.get("section", "")
    search = request.args.get("q", "").strip()

    sql = """
        SELECT m.mark_id, m.marks_obtained, m.max_marks, m.pass_marks, m.remarks, m.created_at,
               s.student_id, s.roll_no, s.full_name, s.section,
               sub.subject_id, sub.subject_code, sub.subject_name,
               e.exam_id, e.exam_code, e.exam_name,
               u.username AS entered_by_user
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        JOIN subjects sub ON m.subject_id = sub.subject_id
        JOIN examinations e ON m.exam_id = e.exam_id
        LEFT JOIN users u ON m.entered_by = u.user_id
        WHERE 1=1
    """
    params = []
    if exam_filter:
        sql += " AND m.exam_id = %s"
        params.append(exam_filter)
    if subject_filter:
        sql += " AND m.subject_id = %s"
        params.append(subject_filter)
    if section_filter:
        sql += " AND s.section = %s"
        params.append(section_filter)
    if search:
        sql += " AND (s.roll_no LIKE %s OR s.full_name LIKE %s)"
        pat = f"%{search}%"
        params.extend([pat, pat])

    sql += " ORDER BY m.created_at DESC LIMIT 150"

    marks_list = execute_query(sql, tuple(params), fetch="all") or []
    all_exams = execute_query("SELECT exam_id, exam_code, exam_name FROM examinations ORDER BY exam_id ASC", fetch="all") or []
    all_subjects = execute_query("SELECT subject_id, subject_code, subject_name FROM subjects ORDER BY subject_name ASC", fetch="all") or []
    sections = execute_query("SELECT DISTINCT section FROM students ORDER BY section ASC", fetch="all") or []

    return render_template(
        "admin/marks.html",
        marks=marks_list,
        examinations=all_exams,
        subjects=all_subjects,
        sections=[s["section"] for s in sections],
        selected_exam=exam_filter,
        selected_subject=subject_filter,
        selected_section=section_filter,
        search=search
    )

@admin_bp.route("/marks/delete/<int:mark_id>", methods=["POST"])
def delete_mark(mark_id):
    execute_query("DELETE FROM marks WHERE mark_id = %s", (mark_id,), commit=True)
    log_audit("MARK_DELETED", target_type="mark", target_id=mark_id)
    flash("Mark entry removed successfully.", "info")
    return redirect(url_for("admin.marks"))

# ------------------------------------------------------------------------------
# 7. INSTITUTIONAL ANALYTICS
# ------------------------------------------------------------------------------
@admin_bp.route("/analytics")
def analytics():
    section = request.args.get("section", "All")
    exam_id = request.args.get("exam_id", "All")
    
    analytics_data = get_institutional_analytics(section_filter=section, exam_filter=exam_id)
    all_exams = execute_query("SELECT exam_id, exam_code, exam_name FROM examinations ORDER BY exam_id ASC", fetch="all") or []
    sections = execute_query("SELECT DISTINCT section FROM students ORDER BY section ASC", fetch="all") or []

    return render_template(
        "admin/analytics.html",
        analytics=analytics_data,
        examinations=all_exams,
        sections=[s["section"] for s in sections],
        selected_section=section,
        selected_exam=exam_id
    )

# ------------------------------------------------------------------------------
# 8. CONTACT ENQUIRIES
# ------------------------------------------------------------------------------
@admin_bp.route("/enquiries")
def enquiries():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")

    sql = "SELECT * FROM contact_enquiries WHERE 1=1"
    params = []
    if search:
        sql += " AND (full_name LIKE %s OR college_name LIKE %s OR phone_number LIKE %s)"
        pat = f"%{search}%"
        params.extend([pat, pat, pat])
    if status_filter == "contacted":
        sql += " AND is_contacted = 1"
    elif status_filter == "pending":
        sql += " AND is_contacted = 0"

    sql += " ORDER BY created_at DESC"
    enquiry_list = execute_query(sql, tuple(params), fetch="all") or []

    return render_template(
        "admin/enquiries.html",
        enquiries=enquiry_list,
        search=search,
        status_filter=status_filter
    )

@admin_bp.route("/enquiries/toggle/<int:enquiry_id>", methods=["POST"])
def toggle_enquiry(enquiry_id):
    enquiry = execute_query("SELECT enquiry_id, is_contacted FROM contact_enquiries WHERE enquiry_id = %s", (enquiry_id,), fetch="one")
    if enquiry:
        new_status = 0 if enquiry["is_contacted"] else 1
        execute_query("UPDATE contact_enquiries SET is_contacted = %s WHERE enquiry_id = %s", (new_status, enquiry_id), commit=True)
        log_audit("ENQUIRY_STATUS_TOGGLED", target_type="enquiry", target_id=enquiry_id, details=f"Status: {new_status}")
        flash("Enquiry status updated.", "success")
    return redirect(url_for("admin.enquiries"))

@admin_bp.route("/enquiries/notes/<int:enquiry_id>", methods=["POST"])
def update_enquiry_notes(enquiry_id):
    notes = request.form.get("follow_up_notes", "").strip()
    execute_query("UPDATE contact_enquiries SET follow_up_notes = %s WHERE enquiry_id = %s", (notes, enquiry_id), commit=True)
    flash("Follow-up notes saved.", "success")
    return redirect(url_for("admin.enquiries"))

@admin_bp.route("/enquiries/delete/<int:enquiry_id>", methods=["POST"])
def delete_enquiry(enquiry_id):
    execute_query("DELETE FROM contact_enquiries WHERE enquiry_id = %s", (enquiry_id,), commit=True)
    log_audit("ENQUIRY_DELETED", target_type="enquiry", target_id=enquiry_id)
    flash("Enquiry record deleted.", "info")
    return redirect(url_for("admin.enquiries"))

# ------------------------------------------------------------------------------
# 9. WEBSITE APPEARANCE & CONTENT MANAGEMENT
# ------------------------------------------------------------------------------
@admin_bp.route("/appearance", methods=["GET", "POST"])
def appearance():
    """
    Dedicated admin management page for website appearance, headlines,
    colors, sections visibility, and brand assets.
    """
    if request.method == "POST":
        # Form field updates
        hero_headline = request.form.get("hero_headline", "").strip()
        hero_subheadline = request.form.get("hero_subheadline", "").strip()
        site_tagline = request.form.get("site_tagline", "").strip()
        about_heading = request.form.get("about_heading", "").strip()
        about_body = request.form.get("about_body", "").strip()
        primary_accent_color = request.form.get("primary_accent_color", "#C8F169").strip()
        
        # Validate hex color
        if not re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", primary_accent_color):
            primary_accent_color = "#C8F169"

        # Toggles
        features_vis = "true" if request.form.get("features_visible") == "1" else "false"
        how_vis = "true" if request.form.get("how_it_works_visible") == "1" else "false"
        benefits_vis = "true" if request.form.get("benefits_visible") == "1" else "false"
        contact_vis = "true" if request.form.get("contact_visible") == "1" else "false"
        announcements_vis = "true" if request.form.get("announcements_visible") == "1" else "false"

        # Contact info
        contact_email = request.form.get("contact_email", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        contact_college_placeholder = request.form.get("contact_college_placeholder", "").strip()
        contact_address = request.form.get("contact_address", "").strip()

        # Save all settings into MySQL
        updates = [
            ("hero_headline", hero_headline, "content"),
            ("hero_subheadline", hero_subheadline, "content"),
            ("site_tagline", site_tagline, "general"),
            ("about_heading", about_heading, "content"),
            ("about_body", about_body, "content"),
            ("primary_accent_color", primary_accent_color, "appearance"),
            ("features_visible", features_vis, "visibility"),
            ("how_it_works_visible", how_vis, "visibility"),
            ("benefits_visible", benefits_vis, "visibility"),
            ("contact_visible", contact_vis, "visibility"),
            ("announcements_visible", announcements_vis, "visibility"),
            ("contact_email", contact_email, "contact"),
            ("contact_phone", contact_phone, "contact"),
            ("contact_college_placeholder", contact_college_placeholder, "contact"),
            ("contact_address", contact_address, "contact")
        ]

        # Handle Logo File Upload if present
        if "logo_file" in request.files and request.files["logo_file"].filename != "":
            try:
                uploaded_logo_url = save_uploaded_file(request.files["logo_file"], folder_prefix="brand_logo")
                if uploaded_logo_url:
                    updates.append(("logo_url", uploaded_logo_url, "appearance"))
                    log_audit("LOGO_UPLOADED", target_type="setting", target_id="logo_url", details=uploaded_logo_url)
            except ValueError as ve:
                flash(str(ve), "error")

        for key, val, cat in updates:
            update_website_setting(key, val, category=cat)

        log_audit("WEBSITE_APPEARANCE_UPDATED", target_type="setting", details="Updated homepage appearance and settings")
        flash("Website appearance and content settings updated successfully! Live changes are now visible on the public website.", "success")
        return redirect(url_for("admin.appearance"))

    settings = get_website_settings(force_refresh=True)
    return render_template("admin/appearance.html", settings=settings)

# ------------------------------------------------------------------------------
# 10. ANNOUNCEMENTS MANAGEMENT
# ------------------------------------------------------------------------------
@admin_bp.route("/announcements")
def announcements():
    items = execute_query("SELECT * FROM announcements ORDER BY priority DESC, created_at DESC", fetch="all") or []
    return render_template("admin/announcements.html", announcements=items)

@admin_bp.route("/announcements/add", methods=["POST"])
def add_announcement():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    badge_text = request.form.get("badge_text", "Notice").strip()
    priority = int(request.form.get("priority", 0))

    if not title or not content:
        flash("Title and content are required.", "error")
        return redirect(url_for("admin.announcements"))

    execute_query(
        "INSERT INTO announcements (title, content, badge_text, priority, is_active) VALUES (%s, %s, %s, %s, 1)",
        (title, content, badge_text, priority),
        commit=True
    )
    log_audit("ANNOUNCEMENT_CREATED", target_type="announcement", details=title)
    flash("Announcement published successfully.", "success")
    return redirect(url_for("admin.announcements"))

@admin_bp.route("/announcements/toggle/<int:announcement_id>", methods=["POST"])
def toggle_announcement(announcement_id):
    item = execute_query("SELECT announcement_id, is_active FROM announcements WHERE announcement_id = %s", (announcement_id,), fetch="one")
    if item:
        new_status = 0 if item["is_active"] else 1
        execute_query("UPDATE announcements SET is_active = %s WHERE announcement_id = %s", (new_status, announcement_id), commit=True)
        flash("Announcement visibility updated.", "info")
    return redirect(url_for("admin.announcements"))

@admin_bp.route("/announcements/delete/<int:announcement_id>", methods=["POST"])
def delete_announcement(announcement_id):
    execute_query("DELETE FROM announcements WHERE announcement_id = %s", (announcement_id,), commit=True)
    log_audit("ANNOUNCEMENT_DELETED", target_type="announcement", target_id=announcement_id)
    flash("Announcement deleted.", "info")
    return redirect(url_for("admin.announcements"))

# ------------------------------------------------------------------------------
# 11. AUDIT LOGS
# ------------------------------------------------------------------------------
@admin_bp.route("/audit-logs")
def audit_logs():
    search = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "")

    sql = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if search:
        sql += " AND (username LIKE %s OR action LIKE %s OR details LIKE %s)"
        pat = f"%{search}%"
        params.extend([pat, pat, pat])
    if role_filter:
        sql += " AND role = %s"
        params.append(role_filter)

    sql += " ORDER BY created_at DESC LIMIT 200"
    logs = execute_query(sql, tuple(params), fetch="all") or []

    return render_template("admin/audit_logs.html", logs=logs, search=search, role_filter=role_filter)

# ------------------------------------------------------------------------------
# 12. GENERAL SETTINGS
# ------------------------------------------------------------------------------
@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        threshold = request.form.get("assistance_threshold_pct", "40.0").strip()
        try:
            val = float(threshold)
            if 10.0 <= val <= 90.0:
                update_website_setting("assistance_threshold_pct", str(val), category="grading")
                flash("Academic assistance threshold updated successfully.", "success")
            else:
                flash("Threshold must be a percentage between 10% and 90%.", "error")
        except ValueError:
            flash("Please enter a valid numeric percentage.", "error")
        return redirect(url_for("admin.settings"))

    current_settings = get_website_settings(force_refresh=True)
    return render_template("admin/settings.html", settings=current_settings)
