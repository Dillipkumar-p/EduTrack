from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
import csv
import io
from werkzeug.security import generate_password_hash
from backend.auth import login_required, role_required
from backend.database import execute_query
from backend.utilities import log_audit, validate_email
from backend.analytics import get_institutional_analytics, get_student_academic_summary, calculate_grade

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")

@teacher_bp.before_request
@login_required
@role_required("teacher")
def ensure_teacher():
    """Restricted to authenticated faculty / teacher accounts."""
    pass

def get_current_teacher_id():
    """Retrieve teacher_id from session or database."""
    tid = session.get("teacher_id")
    if tid:
        return tid
    uid = session.get("user_id")
    row = execute_query("SELECT teacher_id FROM teachers WHERE user_id = %s", (uid,), fetch="one")
    if row:
        session["teacher_id"] = row["teacher_id"]
        return row["teacher_id"]
    return None

# ------------------------------------------------------------------------------
# 1. TEACHER DASHBOARD
# ------------------------------------------------------------------------------
@teacher_bp.route("/dashboard")
def dashboard():
    teacher_id = get_current_teacher_id()
    
    # Assigned subjects
    assigned_sql = """
        SELECT s.subject_id, s.subject_code, s.subject_name, ta.section
        FROM teacher_assignments ta
        JOIN subjects s ON ta.subject_id = s.subject_id
        WHERE ta.teacher_id = %s
    """
    assigned_subjects = execute_query(assigned_sql, (teacher_id,), fetch="all") or []

    # Total students count
    total_students = execute_query("SELECT COUNT(*) AS c FROM students WHERE roll_no != 'DEMO2026MBU'", fetch="val") or 0

    # Analytics for student alerts
    analytics = get_institutional_analytics()

    # Recent marks entered by this faculty member
    recent_marks_sql = """
        SELECT m.mark_id, m.marks_obtained, m.max_marks, m.created_at,
               s.roll_no, s.full_name, s.section, sub.subject_name, e.exam_name
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        JOIN subjects sub ON m.subject_id = sub.subject_id
        JOIN examinations e ON m.exam_id = e.exam_id
        WHERE m.entered_by = %s AND s.roll_no != 'DEMO2026MBU'
        ORDER BY m.created_at DESC LIMIT 8
    """
    recent_marks = execute_query(recent_marks_sql, (session.get("user_id"),), fetch="all") or []

    return render_template(
        "teacher/dashboard.html",
        assigned_subjects=assigned_subjects,
        total_students=total_students,
        analytics=analytics,
        recent_marks=recent_marks
    )

# ------------------------------------------------------------------------------
# 2. STUDENT MANAGEMENT FOR TEACHERS
# ------------------------------------------------------------------------------
@teacher_bp.route("/students")
def students():
    search = request.args.get("q", "").strip()
    section = request.args.get("section", "").strip()

    sql = """
        SELECT s.student_id, s.roll_no, s.full_name, s.email, s.phone, s.section, s.batch_year
        FROM students s
        WHERE s.roll_no != 'DEMO2026MBU'
    """
    params = []
    if search:
        sql += " AND (s.roll_no LIKE %s OR s.full_name LIKE %s)"
        pat = f"%{search}%"
        params.extend([pat, pat])
    if section:
        sql += " AND s.section = %s"
        params.append(section)
    sql += " ORDER BY s.roll_no ASC"

    student_list = execute_query(sql, tuple(params), fetch="all") or []
    sections = execute_query("SELECT DISTINCT section FROM students ORDER BY section ASC", fetch="all") or []

    return render_template(
        "teacher/students.html",
        students=student_list,
        sections=[s["section"] for s in sections],
        search=search,
        selected_section=section
    )

@teacher_bp.route("/students/profile/<int:student_id>")
def student_profile(student_id):
    summary = get_student_academic_summary(student_id)
    if not summary:
        flash("Student record not found.", "error")
        return redirect(url_for("teacher.students"))

    return render_template("teacher/student_profile.html", summary=summary)

@teacher_bp.route("/students/add", methods=["POST"])
def add_student():
    full_name = request.form.get("full_name", "").strip()
    roll_no = request.form.get("roll_no", "").strip().upper()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    section = request.form.get("section", "A").strip().upper()
    batch_year = request.form.get("batch_year", "2024-2028").strip()
    raw_password = request.form.get("password", "").strip() or f"EduTrack@{roll_no}"

    if not full_name or not roll_no or not email:
        flash("Full Name, Roll Number, and Email are mandatory.", "error")
        return redirect(url_for("teacher.students"))

    if not validate_email(email):
        flash("Invalid email format.", "error")
        return redirect(url_for("teacher.students"))

    dup_user = execute_query("SELECT user_id FROM users WHERE username = %s OR email = %s", (roll_no, email), fetch="one")
    if dup_user:
        flash(f"Roll Number '{roll_no}' or Email '{email}' is already registered.", "error")
        return redirect(url_for("teacher.students"))

    password_hash = generate_password_hash(raw_password)
    user_res = execute_query(
        "INSERT INTO users (username, email, password_hash, role, is_active) VALUES (%s, %s, %s, 'student', 1)",
        (roll_no, email, password_hash),
        commit=True
    )
    user_id = user_res["lastrowid"]

    execute_query(
        """INSERT INTO students (user_id, roll_no, full_name, email, phone, section, batch_year)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, roll_no, full_name, email, phone or None, section, batch_year),
        commit=True
    )

    log_audit("STUDENT_CREATED_BY_TEACHER", target_type="student", target_id=roll_no, details=f"Added {full_name}")
    flash(f"Student '{full_name}' ({roll_no}) added. Initial password: {raw_password}", "success")
    return redirect(url_for("teacher.students"))

@teacher_bp.route("/students/edit/<int:student_id>", methods=["POST"])
def edit_student(student_id):
    student = execute_query("SELECT student_id, user_id, roll_no FROM students WHERE student_id = %s", (student_id,), fetch="one")
    if not student:
        flash("Student record not found.", "error")
        return redirect(url_for("teacher.students"))

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    section = request.form.get("section", "A").strip().upper()
    batch_year = request.form.get("batch_year", "2024-2028").strip()

    if not full_name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("teacher.students"))

    # Update
    execute_query(
        """UPDATE students SET full_name = %s, email = %s, phone = %s, section = %s, batch_year = %s
           WHERE student_id = %s""",
        (full_name, email, phone or None, section, batch_year, student_id),
        commit=True
    )
    execute_query("UPDATE users SET email = %s WHERE user_id = %s", (email, student["user_id"]), commit=True)
    log_audit("STUDENT_UPDATED_BY_TEACHER", target_type="student", target_id=student_id)
    flash(f"Student '{full_name}' updated successfully.", "success")
    return redirect(url_for("teacher.students"))

@teacher_bp.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    student = execute_query("SELECT student_id, user_id, full_name, roll_no FROM students WHERE student_id = %s", (student_id,), fetch="one")
    if not student:
        flash("Student record not found.", "error")
        return redirect(url_for("teacher.students"))

    # Referential integrity cascade through user
    execute_query("DELETE FROM users WHERE user_id = %s", (student["user_id"],), commit=True)
    log_audit("STUDENT_DELETED_BY_TEACHER", target_type="student", target_id=student["roll_no"], details=student["full_name"])
    flash(f"Student record for '{student['full_name']}' removed.", "info")
    return redirect(url_for("teacher.students"))

# ------------------------------------------------------------------------------
# 3. MARKS ENTRY & MANAGEMENT
# ------------------------------------------------------------------------------
@teacher_bp.route("/marks", methods=["GET", "POST"])
def marks():
    if request.method == "POST":
        student_id = request.form.get("student_id")
        subject_id = request.form.get("subject_id")
        exam_id = request.form.get("exam_id")
        marks_obtained_str = request.form.get("marks_obtained", "").strip()
        remarks = request.form.get("remarks", "").strip()

        if not student_id or not subject_id or not exam_id or marks_obtained_str == "":
            flash("All fields (Student, Subject, Examination, and Marks Obtained) are required.", "error")
            return redirect(url_for("teacher.marks"))

        try:
            marks_obtained = float(marks_obtained_str)
        except ValueError:
            flash("Marks obtained must be a valid number.", "error")
            return redirect(url_for("teacher.marks"))

        if marks_obtained < 0:
            flash("Marks obtained cannot be negative.", "error")
            return redirect(url_for("teacher.marks"))

        # Look up exam default max marks and pass marks
        exam = execute_query("SELECT default_max_marks, default_pass_marks, exam_name, exam_type FROM examinations WHERE exam_id = %s", (exam_id,), fetch="one")
        if not exam:
            flash("Invalid examination selected.", "error")
            return redirect(url_for("teacher.marks"))

        max_marks = exam["default_max_marks"]
        pass_marks = exam["default_pass_marks"]

        # Internal exams (internal_1 / internal_2) are capped at 50 marks
        INTERNAL_TYPES = ("internal_1", "internal_2")
        if exam["exam_type"] in INTERNAL_TYPES and max_marks > 50:
            max_marks = 50
        if exam["exam_type"] in INTERNAL_TYPES and marks_obtained > 50:
            flash(f"Internal examination marks cannot exceed 50. Entered: {marks_obtained}.", "error")
            return redirect(url_for("teacher.marks"))

        # Validate marks against maximum marks
        if marks_obtained > max_marks:
            flash(f"Marks obtained ({marks_obtained}) cannot exceed the examination maximum of {max_marks}.", "error")
            return redirect(url_for("teacher.marks"))

        # Check for existing duplicate entry
        existing = execute_query(
            "SELECT mark_id FROM marks WHERE student_id = %s AND subject_id = %s AND exam_id = %s",
            (student_id, subject_id, exam_id),
            fetch="one"
        )
        if existing:
            # Update existing mark entry instead of crashing
            execute_query(
                """UPDATE marks SET marks_obtained = %s, max_marks = %s, pass_marks = %s, remarks = %s, entered_by = %s
                   WHERE mark_id = %s""",
                (marks_obtained, max_marks, pass_marks, remarks or None, session.get("user_id"), existing["mark_id"]),
                commit=True
            )
            log_audit("MARK_UPDATED", target_type="mark", target_id=existing["mark_id"], details=f"Updated to {marks_obtained}/{max_marks}")
            flash(f"Existing mark record updated successfully: {marks_obtained}/{max_marks}.", "success")
        else:
            execute_query(
                """INSERT INTO marks (student_id, subject_id, exam_id, marks_obtained, max_marks, pass_marks, remarks, entered_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (student_id, subject_id, exam_id, marks_obtained, max_marks, pass_marks, remarks or None, session.get("user_id")),
                commit=True
            )
            log_audit("MARK_ENTERED", target_type="mark", details=f"Score: {marks_obtained}/{max_marks}")
            flash(f"Marks saved successfully: {marks_obtained} out of {max_marks}.", "success")

        return redirect(url_for("teacher.marks"))

    # GET filters
    exam_filter = request.args.get("exam_id", "")
    subject_filter = request.args.get("subject_id", "")
    section_filter = request.args.get("section", "")
    search = request.args.get("q", "").strip()

    sql = """
        SELECT m.mark_id, m.marks_obtained, m.max_marks, m.pass_marks, m.remarks, m.created_at,
               s.student_id, s.roll_no, s.full_name, s.section,
               sub.subject_id, sub.subject_code, sub.subject_name,
               e.exam_id, e.exam_code, e.exam_name
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        JOIN subjects sub ON m.subject_id = sub.subject_id
        JOIN examinations e ON m.exam_id = e.exam_id
        WHERE s.roll_no != 'DEMO2026MBU'
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

    sql += " ORDER BY m.created_at DESC LIMIT 100"

    marks_list = execute_query(sql, tuple(params), fetch="all") or []
    all_students = execute_query("SELECT student_id, roll_no, full_name, section FROM students WHERE roll_no != 'DEMO2026MBU' ORDER BY roll_no ASC", fetch="all") or []
    all_subjects = execute_query("SELECT subject_id, subject_code, subject_name, max_marks FROM subjects WHERE is_active = 1 ORDER BY subject_name ASC", fetch="all") or []
    all_exams = execute_query("SELECT exam_id, exam_code, exam_name, exam_type, default_max_marks, default_pass_marks FROM examinations WHERE is_active = 1 ORDER BY exam_id ASC", fetch="all") or []
    sections = execute_query("SELECT DISTINCT section FROM students ORDER BY section ASC", fetch="all") or []

    return render_template(
        "teacher/marks_entry.html",
        marks=marks_list,
        students=all_students,
        subjects=all_subjects,
        examinations=all_exams,
        sections=[s["section"] for s in sections],
        selected_exam=exam_filter,
        selected_subject=subject_filter,
        selected_section=section_filter,
        search=search
    )

@teacher_bp.route("/marks/edit/<int:mark_id>", methods=["POST"])
def edit_mark(mark_id):
    mark = execute_query("SELECT mark_id, max_marks FROM marks WHERE mark_id = %s", (mark_id,), fetch="one")
    if not mark:
        flash("Mark record not found.", "error")
        return redirect(url_for("teacher.marks"))

    new_marks_str = request.form.get("marks_obtained", "").strip()
    remarks = request.form.get("remarks", "").strip()

    try:
        new_marks = float(new_marks_str)
        if new_marks < 0 or new_marks > mark["max_marks"]:
            flash(f"Marks must be between 0 and {mark['max_marks']}.", "error")
            return redirect(url_for("teacher.marks"))
    except ValueError:
        flash("Invalid marks value.", "error")
        return redirect(url_for("teacher.marks"))

    execute_query("UPDATE marks SET marks_obtained = %s, remarks = %s WHERE mark_id = %s", (new_marks, remarks or None, mark_id), commit=True)
    log_audit("MARK_EDITED_BY_TEACHER", target_type="mark", target_id=mark_id, details=f"New: {new_marks}")
    flash("Mark entry updated.", "success")
    return redirect(url_for("teacher.marks"))

@teacher_bp.route("/marks/delete/<int:mark_id>", methods=["POST"])
def delete_mark(mark_id):
    execute_query("DELETE FROM marks WHERE mark_id = %s", (mark_id,), commit=True)
    log_audit("MARK_DELETED_BY_TEACHER", target_type="mark", target_id=mark_id)
    flash("Mark entry removed.", "info")
    return redirect(url_for("teacher.marks"))

# ------------------------------------------------------------------------------
# 4. RESULTS & ANALYTICS
# ------------------------------------------------------------------------------
@teacher_bp.route("/results")
def results():
    section_filter = request.args.get("section", "All")
    exam_filter = request.args.get("exam_id", "All")

    analytics_data = get_institutional_analytics(section_filter=section_filter, exam_filter=exam_filter)
    all_exams = execute_query("SELECT exam_id, exam_code, exam_name FROM examinations ORDER BY exam_id ASC", fetch="all") or []
    sections = execute_query("SELECT DISTINCT section FROM students ORDER BY section ASC", fetch="all") or []

    return render_template(
        "teacher/results.html",
        analytics=analytics_data,
        examinations=all_exams,
        sections=[s["section"] for s in sections],
        selected_section=section_filter,
        selected_exam=exam_filter
    )

@teacher_bp.route("/analytics")
def analytics():
    analytics_data = get_institutional_analytics()
    return render_template("teacher/analytics.html", analytics=analytics_data)

@teacher_bp.route("/export-marks-excel")
def export_marks_excel():
    """
    Exports section marks in Excel-compatible CSV format with UTF-8 BOM.
    Filtered by section, exam, and/or subject.
    """
    section_filter = request.args.get("section", "All").strip()
    exam_filter = request.args.get("exam_id", "All").strip()
    subject_filter = request.args.get("subject_id", "All").strip()

    sql = """
        SELECT s.roll_no, s.full_name, s.section,
               sub.subject_code, sub.subject_name,
               e.exam_code, e.exam_name,
               m.marks_obtained, m.max_marks, m.pass_marks,
               ROUND((m.marks_obtained / m.max_marks) * 100, 1) AS percentage,
               CASE WHEN m.marks_obtained >= m.pass_marks THEN 'Pass' ELSE 'Fail' END AS status,
               m.remarks
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        JOIN subjects sub ON m.subject_id = sub.subject_id
        JOIN examinations e ON m.exam_id = e.exam_id
        WHERE s.roll_no != 'DEMO2026MBU'
    """
    params = []
    if section_filter and section_filter != "All":
        sql += " AND s.section = %s"
        params.append(section_filter)
    if exam_filter and exam_filter != "All":
        sql += " AND e.exam_id = %s"
        params.append(exam_filter)
    if subject_filter and subject_filter != "All":
        sql += " AND sub.subject_id = %s"
        params.append(subject_filter)

    sql += " ORDER BY s.section ASC, s.roll_no ASC, sub.subject_code ASC, e.exam_id ASC"

    rows = execute_query(sql, tuple(params), fetch="all") or []

    # Build CSV output in memory
    output = io.StringIO()
    # Write UTF-8 BOM so Excel opens with proper character rendering
    output.write("\ufeff")
    writer = csv.writer(output)

    # Title & Metadata banner
    writer.writerow(["Mohan Babu University - Academic Performance Record"])
    writer.writerow([f"Section: {section_filter}", f"Exam Filter: {exam_filter}", f"Subject Filter: {subject_filter}"])
    writer.writerow([])

    # Header Row
    writer.writerow([
        "Roll Number",
        "Student Name",
        "Section",
        "Course Code",
        "Course Name",
        "Examination",
        "Marks Scored",
        "Max Marks",
        "Pass Marks",
        "Percentage (%)",
        "Grade",
        "Status",
        "Faculty Remarks"
    ])

    for r in rows:
        pct = float(r["percentage"]) if r["percentage"] is not None else 0.0
        grade = calculate_grade(pct)
        writer.writerow([
            r["roll_no"],
            r["full_name"],
            r["section"],
            r["subject_code"],
            r["subject_name"],
            f"{r['exam_name']} ({r['exam_code']})",
            r["marks_obtained"],
            r["max_marks"],
            r["pass_marks"],
            pct,
            grade,
            r["status"],
            r["remarks"] or ""
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"MBU_Section_{section_filter}_Marks.csv" if section_filter != "All" else "MBU_Marks_Export.csv"

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )
