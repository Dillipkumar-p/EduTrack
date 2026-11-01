import unittest
from backend import create_app
from backend.database import execute_query
from backend.analytics import calculate_grade, get_student_academic_summary, get_institutional_analytics
from backend.utilities import validate_phone, validate_email, get_website_settings
from config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False  # Disable CSRF in automated unit tests for direct POST assertions

class EduTrackTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()
        # Restore default settings
        execute_query(
            "UPDATE website_settings SET setting_value = 'Academic Performance, Made Visible.' WHERE setting_key = 'hero_headline'",
            commit=True
        )
        execute_query(
            "UPDATE website_settings SET setting_value = 'Academic Performance, Made Visible.' WHERE setting_key = 'site_tagline'",
            commit=True
        )

    def setUp(self):
        self.client = self.app.test_client()

    # --------------------------------------------------------------------------
    # 1. PUBLIC HOMEPAGE & CONTACT TESTS
    # --------------------------------------------------------------------------
    def test_01_public_homepage_renders(self):
        """Test public homepage loads successfully with branding and dynamic settings."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Academic Performance, Made Visible", response.data)
        self.assertIn(b"Explore Features", response.data)
        self.assertIn(b"Bring EduTrack to Your Institution", response.data)

    def test_02_phone_and_email_validation(self):
        """Test utility validations for phone and email formats."""
        self.assertTrue(validate_phone("+91 9876543210"))
        self.assertTrue(validate_phone("9876543210"))
        self.assertTrue(validate_phone("+1 (555) 234-5678"))
        self.assertFalse(validate_phone("123"))  # too short
        self.assertFalse(validate_phone("abc-invalid-phone"))

        self.assertTrue(validate_email("principal@college.edu"))
        self.assertTrue(validate_email("admin.office@jntu.ac.in"))
        self.assertFalse(validate_email("not-an-email"))
        self.assertFalse(validate_email("missing@domain"))

    def test_03_contact_enquiry_submission(self):
        """Test submitting an institutional contact enquiry and MySQL persistence."""
        payload = {
            "full_name": "Dean Academic Affairs",
            "phone_number": "+91 9123456789",
            "college_name": "Hyderabad Institute of Technology",
            "email_address": "dean.academics@hit.edu",
            "message": "Interested in evaluating EduTrack for semester 1 examinations."
        }
        response = self.client.post("/contact", data=payload, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Thank you for reaching out", response.data)

        # Verify record exists in MySQL
        row = execute_query(
            "SELECT * FROM contact_enquiries WHERE college_name = %s ORDER BY created_at DESC LIMIT 1",
            (payload["college_name"],),
            fetch="one"
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["full_name"], payload["full_name"])
        self.assertEqual(row["phone_number"], payload["phone_number"])

    def test_04_contact_enquiry_invalid_phone_rejected(self):
        """Test rejection when phone number format is invalid."""
        payload = {
            "full_name": "Testing Invalid",
            "phone_number": "123",  # Invalid
            "college_name": "Test College"
        }
        response = self.client.post("/contact", data=payload, follow_redirects=True)
        self.assertIn(b"Please enter a valid phone number", response.data)

    # --------------------------------------------------------------------------
    # 2. AUTHENTICATION & ROLE PROTECTION TESTS
    # --------------------------------------------------------------------------
    def test_05_admin_login_success(self):
        """Test initial admin login with verified Werkzeug password hash."""
        response = self.client.post("/auth/login", data={
            "username": "admin",
            "password": "AdminPassword@2026"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/dashboard"))

    def test_06_invalid_credentials_rejected(self):
        """Test that invalid password attempts are rejected."""
        response = self.client.post("/auth/login", data={
            "username": "admin",
            "password": "WrongPassword999"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid credentials", response.data)

    def test_07_unauthorized_route_protection(self):
        """Verify unauthenticated user cannot access protected admin dashboard."""
        client = self.app.test_client()
        response = client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    # --------------------------------------------------------------------------
    # 3. ADMIN PORTAL OPERATIONS
    # --------------------------------------------------------------------------
    def test_08_admin_creates_teacher_and_student(self):
        """Test admin creating teacher and student accounts in MySQL."""
        # 1. Admin login
        with self.client as c:
            c.post("/auth/login", data={"username": "admin", "password": "AdminPassword@2026"})
            
            # 2. Create Teacher
            teacher_data = {
                "full_name": "Prof. Ananya Sen",
                "employee_id": "TEST_EMP01",
                "email": "ananya.sen.test@institution.edu",
                "phone": "+91 9876500001",
                "department": "Computer Science & Engineering",
                "designation": "Associate Professor",
                "password": "TeacherPass@2026"
            }
            res_t = c.post("/admin/teachers/add", data=teacher_data, follow_redirects=True)
            self.assertEqual(res_t.status_code, 200)
            self.assertIn(b"registered successfully", res_t.data)

            # Verify in DB
            teacher_rec = execute_query("SELECT * FROM teachers WHERE employee_id = %s", ("TEST_EMP01",), fetch="one")
            self.assertIsNotNone(teacher_rec)

            # 3. Create Student
            student_data = {
                "full_name": "Karthik Verma",
                "roll_no": "TEST_24CSE001",
                "email": "karthik.test@institution.edu",
                "phone": "+91 9876500002",
                "section": "A",
                "batch_year": "2024-2028",
                "password": "StudentPass@2026"
            }
            res_s = c.post("/admin/students/add", data=student_data, follow_redirects=True)
            self.assertEqual(res_s.status_code, 200)
            self.assertIn(b"created successfully", res_s.data)

            # Verify in DB
            student_rec = execute_query("SELECT * FROM students WHERE roll_no = %s", ("TEST_24CSE001",), fetch="one")
            self.assertIsNotNone(student_rec)

    def test_09_admin_appearance_management(self):
        """Test admin updating homepage headline and accent color stored in MySQL."""
        with self.client as c:
            c.post("/auth/login", data={"username": "admin", "password": "AdminPassword@2026"})
            
            appearance_data = {
                "hero_headline": "Academic Performance, Engineered for Excellence.",
                "hero_subheadline": "Updated descriptive text through admin management.",
                "site_tagline": "Real Visibility.",
                "primary_accent_color": "#C8F169",
                "features_visible": "1",
                "how_it_works_visible": "1",
                "benefits_visible": "1",
                "contact_visible": "1",
                "announcements_visible": "1",
                "about_heading": "Engineered for Clarity",
                "about_body": "Updated about section text.",
                "contact_email": "dean@EduTrack.edu",
                "contact_phone": "+91 800 123456",
                "contact_college_placeholder": "Test University",
                "contact_address": "Main Academic Block"
            }
            res = c.post("/admin/appearance", data=appearance_data, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"settings updated successfully", res.data)

            # Verify on public homepage
            public_res = self.client.get("/")
            self.assertIn(b"Academic Performance, Engineered for Excellence", public_res.data)

    # --------------------------------------------------------------------------
    # 4. TEACHER OPERATIONS & MARKS VALIDATION
    # --------------------------------------------------------------------------
    def test_10_teacher_login_and_marks_entry(self):
        """Test teacher login, entering marks, and validation boundaries."""
        with self.client as c:
            # 1. Login as teacher
            c.post("/auth/login", data={"username": "TEST_EMP01", "password": "TeacherPass@2026"})
            dash = c.get("/teacher/dashboard")
            self.assertEqual(dash.status_code, 200)
            self.assertIn(b"Welcome, Prof. Ananya Sen", dash.data)

            # 2. Get student and subject IDs
            student = execute_query("SELECT student_id FROM students WHERE roll_no = 'TEST_24CSE001'", fetch="one")
            subject = execute_query("SELECT subject_id, max_marks FROM subjects LIMIT 1", fetch="one")
            exam = execute_query("SELECT exam_id, default_max_marks FROM examinations WHERE exam_code = 'INT1'", fetch="one")

            # 3. Attempt to enter marks exceeding maximum (e.g. 99 in a 50 mark exam)
            exceeding_data = {
                "student_id": student["student_id"],
                "subject_id": subject["subject_id"],
                "exam_id": exam["exam_id"],
                "marks_obtained": "99.0",
                "remarks": "Invalid test"
            }
            res_invalid = c.post("/teacher/marks", data=exceeding_data, follow_redirects=True)
            self.assertIn(b"cannot exceed", res_invalid.data)

            # 4. Enter valid marks (e.g. 44.0 out of 50)
            valid_data = {
                "student_id": student["student_id"],
                "subject_id": subject["subject_id"],
                "exam_id": exam["exam_id"],
                "marks_obtained": "44.0",
                "remarks": "Consistent performance"
            }
            res_valid = c.post("/teacher/marks", data=valid_data, follow_redirects=True)
            self.assertEqual(res_valid.status_code, 200)
            self.assertIn(b"Marks saved successfully", res_valid.data)

            # Verify mark in MySQL
            mark = execute_query(
                "SELECT * FROM marks WHERE student_id = %s AND subject_id = %s AND exam_id = %s",
                (student["student_id"], subject["subject_id"], exam["exam_id"]),
                fetch="one"
            )
            self.assertIsNotNone(mark)
            self.assertEqual(float(mark["marks_obtained"]), 44.0)

    # --------------------------------------------------------------------------
    # 5. STUDENT PORTAL & ACCESS ISOLATION
    # --------------------------------------------------------------------------
    def test_11_student_portal_and_access_boundary(self):
        """Test student login, viewing own marks, and verified session derivation."""
        with self.client as c:
            # 1. Login as student
            res = c.post("/auth/login", data={"username": "TEST_24CSE001", "password": "StudentPass@2026"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Karthik Verma", res.data)
            self.assertIn(b"TEST_24CSE001", res.data)

            # 2. View results
            res_results = c.get("/student/results")
            self.assertEqual(res_results.status_code, 200)
            self.assertIn(b"44", res_results.data)

            # 3. View performance
            res_perf = c.get("/student/performance")
            self.assertEqual(res_perf.status_code, 200)
            self.assertIn(b"Performance Analysis", res_perf.data)

            # 4. Attempt to access unauthorized teacher dashboard -> must be blocked
            res_blocked = c.get("/teacher/dashboard", follow_redirects=False)
            self.assertEqual(res_blocked.status_code, 302)
            self.assertTrue(res_blocked.location.endswith("/student/dashboard"))

    # --------------------------------------------------------------------------
    # 6. ANALYTICS & TEACHER ASSISTANCE CALCULATION
    # --------------------------------------------------------------------------
    def test_12_grading_and_assistance_logic(self):
        """Test calculation of grades, percentages, and assistance triggering."""
        self.assertEqual(calculate_grade(95.0), "O")
        self.assertEqual(calculate_grade(85.0), "A+")
        self.assertEqual(calculate_grade(72.0), "A")
        self.assertEqual(calculate_grade(65.0), "B")
        self.assertEqual(calculate_grade(52.0), "C")
        self.assertEqual(calculate_grade(42.0), "P")
        self.assertEqual(calculate_grade(35.0), "F")

        # Test student summary
        student = execute_query("SELECT student_id FROM students WHERE roll_no = 'TEST_24CSE001'", fetch="one")
        summary = get_student_academic_summary(student["student_id"])
        self.assertIsNotNone(summary)
        self.assertTrue(summary["has_records"])
        self.assertEqual(summary["overall"]["status"], "PASSED")
        self.assertEqual(summary["overall"]["percentage"], 88.0)

    @classmethod
    def tearDownClass(cls):
        """Clean up test records."""
        try:
            # Delete test student user (cascades student and marks)
            s_user = execute_query("SELECT user_id FROM users WHERE username = 'TEST_24CSE001'", fetch="one")
            if s_user:
                execute_query("DELETE FROM users WHERE user_id = %s", (s_user["user_id"],), commit=True)

            # Delete test teacher user
            t_user = execute_query("SELECT user_id FROM users WHERE username = 'TEST_EMP01'", fetch="one")
            if t_user:
                execute_query("DELETE FROM users WHERE user_id = %s", (t_user["user_id"],), commit=True)

            # Clean test enquiry
            execute_query("DELETE FROM contact_enquiries WHERE college_name = 'Hyderabad Institute of Technology'", commit=True)
            execute_query("DELETE FROM contact_enquiries WHERE full_name = 'Testing Invalid'", commit=True)
            # Restore default settings
            execute_query(
                "UPDATE website_settings SET setting_value = 'Academic Performance, Made Visible.' WHERE setting_key = 'hero_headline'",
                commit=True
            )
            execute_query(
                "UPDATE website_settings SET setting_value = 'Academic Performance, Made Visible.' WHERE setting_key = 'site_tagline'",
                commit=True
            )
        except Exception as e:
            print("Cleanup notice:", e)

if __name__ == "__main__":
    unittest.main()
