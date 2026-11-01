import numpy as np
import pandas as pd
from backend.database import execute_query
from backend.utilities import get_website_settings

def calculate_grade(percentage):
    """
    Standard academic grading scale:
    >= 90%: O  (Outstanding)
    >= 80%: A+ (Excellent)
    >= 70%: A  (Very Good)
    >= 60%: B  (Good)
    >= 50%: C  (Average)
    >= 40%: P  (Pass)
    < 40%:  F  (Fail)
    """
    if percentage is None or np.isnan(percentage):
        return "N/A"
    p = float(percentage)
    if p >= 90.0:
        return "O"
    elif p >= 80.0:
        return "A+"
    elif p >= 70.0:
        return "A"
    elif p >= 60.0:
        return "B"
    elif p >= 50.0:
        return "C"
    elif p >= 40.0:
        return "P"
    else:
        return "F"

def get_assistance_threshold():
    """Retrieve configurable performance threshold below which assistance is recommended."""
    settings = get_website_settings()
    try:
        return float(settings.get("assistance_threshold_pct", 40.0))
    except (ValueError, TypeError):
        return 40.0

def get_student_academic_summary(student_id):
    """
    Compute comprehensive student performance report based on verified marks.
    Returns:
      {
        'student': dict,
        'exams': dict_of_exam_data,
        'overall': dict_of_cumulative_stats,
        'strengths': list,
        'improvements': list
      }
    """
    # 1. Fetch student info
    student_sql = """
        SELECT s.student_id, s.roll_no, s.full_name, s.email, s.phone, s.section, s.batch_year, u.username
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.student_id = %s
    """
    student = execute_query(student_sql, (student_id,), fetch="one")
    if not student:
        return None

    # 2. Fetch marks
    marks_sql = """
        SELECT 
            m.mark_id, m.marks_obtained, m.max_marks, m.pass_marks, m.remarks,
            sub.subject_id, sub.subject_code, sub.subject_name,
            e.exam_id, e.exam_code, e.exam_name, e.exam_type
        FROM marks m
        JOIN subjects sub ON m.subject_id = sub.subject_id
        JOIN examinations e ON m.exam_id = e.exam_id
        WHERE m.student_id = %s
        ORDER BY e.exam_id ASC, sub.subject_name ASC
    """
    marks_rows = execute_query(marks_sql, (student_id,), fetch="all")

    threshold = get_assistance_threshold()

    if not marks_rows:
        return {
            "student": student,
            "has_records": False,
            "exams": {},
            "overall": {
                "total_obtained": 0,
                "total_max": 0,
                "percentage": 0.0,
                "grade": "N/A",
                "status": "No Records",
                "assistance_needed": False,
                "failed_subjects_count": 0,
                "total_entries": 0
            },
            "strengths": [],
            "improvements": []
        }

    df = pd.DataFrame(marks_rows)
    df["marks_obtained"] = pd.to_numeric(df["marks_obtained"])
    df["max_marks"] = pd.to_numeric(df["max_marks"])
    df["pass_marks"] = pd.to_numeric(df["pass_marks"])
    df["subject_pct"] = np.where(df["max_marks"] > 0, (df["marks_obtained"] / df["max_marks"]) * 100, 0)
    df["is_passed"] = df["marks_obtained"] >= df["pass_marks"]
    df["subject_grade"] = df["subject_pct"].apply(calculate_grade)

    # Group by examination
    exams_data = {}
    for exam_name, exam_group in df.groupby("exam_name", sort=False):
        exam_id = int(exam_group["exam_id"].iloc[0])
        exam_code = exam_group["exam_code"].iloc[0]
        exam_type = exam_group["exam_type"].iloc[0]
        tot_obtained = float(exam_group["marks_obtained"].sum())
        tot_max = float(exam_group["max_marks"].sum())
        exam_pct = round((tot_obtained / tot_max * 100), 2) if tot_max > 0 else 0.0
        failed_count = int((~exam_group["is_passed"]).sum())
        status = "PASSED" if failed_count == 0 else "NEEDS IMPROVEMENT"

        subject_list = []
        for _, row in exam_group.iterrows():
            subject_list.append({
                "subject_id": row["subject_id"],
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "marks_obtained": float(row["marks_obtained"]),
                "max_marks": int(row["max_marks"]),
                "pass_marks": int(row["pass_marks"]),
                "percentage": round(row["subject_pct"], 1),
                "grade": row["subject_grade"],
                "is_passed": bool(row["is_passed"]),
                "remarks": row["remarks"]
            })

        exams_data[exam_code] = {
            "exam_id": exam_id,
            "exam_name": exam_name,
            "exam_code": exam_code,
            "exam_type": exam_type,
            "total_obtained": tot_obtained,
            "total_max": tot_max,
            "percentage": exam_pct,
            "grade": calculate_grade(exam_pct),
            "status": status,
            "failed_count": failed_count,
            "subjects": subject_list
        }

    # Cumulative calculations
    total_obtained = float(df["marks_obtained"].sum())
    total_max = float(df["max_marks"].sum())
    overall_pct = round((total_obtained / total_max * 100), 2) if total_max > 0 else 0.0
    total_failed = int((~df["is_passed"]).sum())
    overall_status = "PASSED" if total_failed == 0 else "FAIL"
    assistance_needed = (total_failed > 0) or (overall_pct < threshold)

    # Strengths and areas for improvement based on subject-level aggregates
    subject_summary = df.groupby(["subject_name", "subject_code"]).agg(
        avg_pct=("subject_pct", "mean"),
        total_obtained=("marks_obtained", "sum"),
        total_max=("max_marks", "sum")
    ).reset_index()

    subject_summary = subject_summary.sort_values(by="avg_pct", ascending=False)
    strengths = subject_summary[subject_summary["avg_pct"] >= 65.0][["subject_name", "avg_pct"]].to_dict("records")
    improvements = subject_summary[subject_summary["avg_pct"] < 60.0][["subject_name", "avg_pct"]].to_dict("records")

    for item in strengths:
        item["avg_pct"] = round(item["avg_pct"], 1)
    for item in improvements:
        item["avg_pct"] = round(item["avg_pct"], 1)

    return {
        "student": student,
        "has_records": True,
        "exams": exams_data,
        "overall": {
            "total_obtained": total_obtained,
            "total_max": total_max,
            "percentage": overall_pct,
            "grade": calculate_grade(overall_pct),
            "status": overall_status,
            "assistance_needed": assistance_needed,
            "failed_subjects_count": total_failed,
            "total_entries": len(df)
        },
        "strengths": strengths,
        "improvements": improvements
    }

def get_institutional_analytics(section_filter=None, exam_filter=None):
    """
    Compute comprehensive institutional analytics using Pandas/NumPy.
    Includes empty state handling when few or no marks exist.
    """
    threshold = get_assistance_threshold()

    # Counts
    total_students = execute_query("SELECT COUNT(*) AS c FROM students", fetch="val") or 0
    total_teachers = execute_query("SELECT COUNT(*) AS c FROM teachers", fetch="val") or 0
    total_subjects = execute_query("SELECT COUNT(*) AS c FROM subjects WHERE is_active = 1", fetch="val") or 0
    total_exams = execute_query("SELECT COUNT(*) AS c FROM examinations WHERE is_active = 1", fetch="val") or 0

    # Query all marks
    base_sql = """
        SELECT 
            m.mark_id, m.marks_obtained, m.max_marks, m.pass_marks,
            s.student_id, s.roll_no, s.full_name, s.section,
            sub.subject_id, sub.subject_name, sub.subject_code,
            e.exam_id, e.exam_code, e.exam_name
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        JOIN subjects sub ON m.subject_id = sub.subject_id
        JOIN examinations e ON m.exam_id = e.exam_id
        WHERE 1=1
    """
    params = []
    if section_filter and section_filter != "All":
        base_sql += " AND s.section = %s"
        params.append(section_filter)
    if exam_filter and exam_filter != "All":
        base_sql += " AND e.exam_id = %s"
        params.append(exam_filter)

    rows = execute_query(base_sql, tuple(params), fetch="all")

    if not rows:
        return {
            "counts": {
                "students": total_students,
                "teachers": total_teachers,
                "subjects": total_subjects,
                "examinations": total_exams,
                "marks_records": 0
            },
            "overall_avg": 0.0,
            "overall_pass_pct": 0.0,
            "students_needing_assistance": [],
            "top_performers": [],
            "subject_analytics": [],
            "exam_analytics": [],
            "has_data": False
        }

    df = pd.DataFrame(rows)
    df["marks_obtained"] = pd.to_numeric(df["marks_obtained"])
    df["max_marks"] = pd.to_numeric(df["max_marks"])
    df["pass_marks"] = pd.to_numeric(df["pass_marks"])
    df["pct"] = np.where(df["max_marks"] > 0, (df["marks_obtained"] / df["max_marks"]) * 100, 0)
    df["is_passed"] = df["marks_obtained"] >= df["pass_marks"]

    overall_avg = round(float(df["pct"].mean()), 2)
    overall_pass_pct = round(float((df["is_passed"].sum() / len(df)) * 100), 2)

    # Student-level aggregation
    student_group = df.groupby(["student_id", "roll_no", "full_name", "section"]).agg(
        avg_pct=("pct", "mean"),
        total_obtained=("marks_obtained", "sum"),
        total_max=("max_marks", "sum"),
        failed_count=("is_passed", lambda x: int((~x).sum())),
        total_subjects=("mark_id", "count")
    ).reset_index()

    student_group["grade"] = student_group["avg_pct"].apply(calculate_grade)
    student_group["needs_assistance"] = (student_group["failed_count"] > 0) | (student_group["avg_pct"] < threshold)

    # Top performers
    top_df = student_group.sort_values(by="avg_pct", ascending=False).head(5)
    top_performers = []
    for _, r in top_df.iterrows():
        top_performers.append({
            "student_id": int(r["student_id"]),
            "roll_no": r["roll_no"],
            "full_name": r["full_name"],
            "section": r["section"],
            "avg_pct": round(float(r["avg_pct"]), 1),
            "grade": r["grade"],
            "failed_count": int(r["failed_count"])
        })

    # Students needing assistance
    assist_df = student_group[student_group["needs_assistance"]].sort_values(by="avg_pct", ascending=True)
    needing_assistance = []
    for _, r in assist_df.iterrows():
        reasons = []
        if r["failed_count"] > 0:
            reasons.append(f"Failed {int(r['failed_count'])} assessment(s)")
        if r["avg_pct"] < threshold:
            reasons.append(f"Aggregate {round(float(r['avg_pct']), 1)}% is below threshold ({threshold}%)")

        needing_assistance.append({
            "student_id": int(r["student_id"]),
            "roll_no": r["roll_no"],
            "full_name": r["full_name"],
            "section": r["section"],
            "avg_pct": round(float(r["avg_pct"]), 1),
            "grade": r["grade"],
            "failed_count": int(r["failed_count"]),
            "reason": "; ".join(reasons)
        })

    # Subject-wise analytics
    subject_group = df.groupby(["subject_id", "subject_code", "subject_name"]).agg(
        avg_pct=("pct", "mean"),
        highest_mark=("marks_obtained", "max"),
        lowest_mark=("marks_obtained", "min"),
        total_entries=("mark_id", "count"),
        passed_count=("is_passed", "sum")
    ).reset_index()

    subject_analytics = []
    for _, r in subject_group.iterrows():
        pass_rate = round((float(r["passed_count"]) / float(r["total_entries"])) * 100, 1) if r["total_entries"] > 0 else 0.0
        subject_analytics.append({
            "subject_id": int(r["subject_id"]),
            "subject_code": r["subject_code"],
            "subject_name": r["subject_name"],
            "avg_pct": round(float(r["avg_pct"]), 1),
            "highest_mark": float(r["highest_mark"]),
            "lowest_mark": float(r["lowest_mark"]),
            "total_entries": int(r["total_entries"]),
            "pass_rate": pass_rate
        })

    # Examination-wise analytics
    exam_group = df.groupby(["exam_id", "exam_code", "exam_name"]).agg(
        avg_pct=("pct", "mean"),
        total_entries=("mark_id", "count"),
        passed_count=("is_passed", "sum")
    ).reset_index()

    exam_analytics = []
    for _, r in exam_group.iterrows():
        pass_rate = round((float(r["passed_count"]) / float(r["total_entries"])) * 100, 1) if r["total_entries"] > 0 else 0.0
        exam_analytics.append({
            "exam_id": int(r["exam_id"]),
            "exam_code": r["exam_code"],
            "exam_name": r["exam_name"],
            "avg_pct": round(float(r["avg_pct"]), 1),
            "total_entries": int(r["total_entries"]),
            "pass_rate": pass_rate
        })

    return {
        "counts": {
            "students": total_students,
            "teachers": total_teachers,
            "subjects": total_subjects,
            "examinations": total_exams,
            "marks_records": len(df)
        },
        "overall_avg": overall_avg,
        "overall_pass_pct": overall_pass_pct,
        "students_needing_assistance": needing_assistance,
        "top_performers": top_performers,
        "subject_analytics": subject_analytics,
        "exam_analytics": exam_analytics,
        "has_data": True
    }
