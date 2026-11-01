-- ==============================================================================
-- EduTrack Database Schema (MySQL 8.0+)
-- Production Schema for Student Academic Performance Management System
-- Compatible with local MySQL and Aiven Managed Cloud MySQL
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS edutrack_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE edutrack_db;

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'teacher', 'student') NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_role (role),
    INDEX idx_users_active (is_active)
) ENGINE=InnoDB;

-- 2. TEACHERS TABLE
CREATE TABLE IF NOT EXISTS teachers (
    teacher_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    employee_id VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL,
    phone VARCHAR(25) NULL,
    department VARCHAR(100) NOT NULL DEFAULT 'Computer Science & Engineering',
    designation VARCHAR(100) NOT NULL DEFAULT 'Assistant Professor',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. STUDENTS TABLE
CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    roll_no VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL,
    phone VARCHAR(25) NULL,
    section VARCHAR(20) NOT NULL DEFAULT 'A',
    batch_year VARCHAR(30) NOT NULL DEFAULT '2024-2028',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_students_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_students_section (section),
    INDEX idx_students_roll (roll_no)
) ENGINE=InnoDB;

-- 4. SUBJECTS TABLE
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_code VARCHAR(30) NOT NULL UNIQUE,
    subject_name VARCHAR(100) NOT NULL,
    max_marks INT NOT NULL DEFAULT 100,
    pass_marks INT NOT NULL DEFAULT 40,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 5. TEACHER SUBJECT ASSIGNMENTS
CREATE TABLE IF NOT EXISTS teacher_assignments (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id INT NOT NULL,
    subject_id INT NOT NULL,
    section VARCHAR(20) NOT NULL DEFAULT 'All',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_teacher_subject_section (teacher_id, subject_id, section),
    CONSTRAINT fk_ta_teacher FOREIGN KEY (teacher_id) 
        REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    CONSTRAINT fk_ta_subject FOREIGN KEY (subject_id) 
        REFERENCES subjects(subject_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. EXAMINATIONS TABLE
CREATE TABLE IF NOT EXISTS examinations (
    exam_id INT AUTO_INCREMENT PRIMARY KEY,
    exam_code VARCHAR(30) NOT NULL UNIQUE,
    exam_name VARCHAR(100) NOT NULL,
    exam_type ENUM('internal_1', 'internal_2', 'semester', 'custom') NOT NULL DEFAULT 'custom',
    default_max_marks INT NOT NULL DEFAULT 100,
    default_pass_marks INT NOT NULL DEFAULT 40,
    academic_term VARCHAR(50) NOT NULL DEFAULT 'Semester 1',
    exam_date DATE NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 7. MARKS TABLE
CREATE TABLE IF NOT EXISTS marks (
    mark_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    subject_id INT NOT NULL,
    exam_id INT NOT NULL,
    marks_obtained DECIMAL(5,2) NOT NULL,
    max_marks INT NOT NULL,
    pass_marks INT NOT NULL,
    remarks VARCHAR(255) NULL,
    entered_by INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_subject_exam (student_id, subject_id, exam_id),
    CONSTRAINT fk_marks_student FOREIGN KEY (student_id) 
        REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_marks_subject FOREIGN KEY (subject_id) 
        REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    CONSTRAINT fk_marks_exam FOREIGN KEY (exam_id) 
        REFERENCES examinations(exam_id) ON DELETE RESTRICT,
    CONSTRAINT fk_marks_entered_by FOREIGN KEY (entered_by) 
        REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_marks_student (student_id),
    INDEX idx_marks_exam (exam_id),
    INDEX idx_marks_subject (subject_id)
) ENGINE=InnoDB;

-- 8. CONTACT ENQUIRIES TABLE
CREATE TABLE IF NOT EXISTS contact_enquiries (
    enquiry_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(30) NOT NULL,
    college_name VARCHAR(150) NOT NULL,
    email_address VARCHAR(120) NULL,
    message TEXT NULL,
    is_contacted TINYINT(1) NOT NULL DEFAULT 0,
    follow_up_notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_enquiries_date (created_at),
    INDEX idx_enquiries_contacted (is_contacted)
) ENGINE=InnoDB;

-- 9. WEBSITE SETTINGS TABLE
CREATE TABLE IF NOT EXISTS website_settings (
    setting_key VARCHAR(64) PRIMARY KEY,
    setting_value TEXT NULL,
    category VARCHAR(32) NOT NULL DEFAULT 'general',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 10. ANNOUNCEMENTS TABLE
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    badge_text VARCHAR(50) NOT NULL DEFAULT 'Notice',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    priority INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 11. AUDIT LOGS TABLE
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    username VARCHAR(50) NOT NULL DEFAULT 'anonymous',
    role VARCHAR(20) NOT NULL DEFAULT 'public',
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NULL,
    target_id VARCHAR(50) NULL,
    details TEXT NULL,
    ip_address VARCHAR(45) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_created (created_at),
    INDEX idx_audit_user (user_id)
) ENGINE=InnoDB;

-- ==============================================================================
-- DEFAULT SEED DATA
-- ==============================================================================

-- Core Default Subjects
INSERT IGNORE INTO subjects (subject_code, subject_name, max_marks, pass_marks, is_active) VALUES
('CS101', 'Data Structures & Algorithms', 100, 40, 1),
('CS102', 'Database Management Systems', 100, 40, 1),
('CS103', 'Operating Systems', 100, 40, 1),
('CS104', 'Computer Networks', 100, 40, 1),
('CS105', 'Object-Oriented Programming (Java)', 100, 40, 1);

-- Default Examinations (Configured as required: Internal 1: 50/20, Internal 2: 50/20, Semester: 100/40)
INSERT IGNORE INTO examinations (exam_code, exam_name, exam_type, default_max_marks, default_pass_marks, academic_term, exam_date, is_active) VALUES
('INT1', 'Internal Examination 1', 'internal_1', 50, 20, 'Semester 1', '2026-09-15', 1),
('INT2', 'Internal Examination 2', 'internal_2', 50, 20, 'Semester 1', '2026-10-20', 1),
('SEM1', 'Semester End Examination', 'semester', 100, 40, 'Semester 1', '2026-12-10', 1);

-- Default Website Settings
INSERT IGNORE INTO website_settings (setting_key, setting_value, category) VALUES
('site_title', 'EduTrack', 'general'),
('site_tagline', 'Academic Performance, Made Visible.', 'general'),
('hero_headline', 'Academic Performance, Made Visible.', 'content'),
('hero_subheadline', 'EduTrack brings students, teachers and academic performance together in one intelligent platform. Track progress, manage results and make better academic decisions.', 'content'),
('about_heading', 'Engineered for Academic Precision', 'content'),
('about_body', 'EduTrack was designed from the ground up to solve the visibility gap in modern collegiate education. By replacing fragmented spreadsheets and delayed score entries with an intuitive, unified performance platform, institutions can identify learning deficits early and accelerate student success.', 'content'),
('features_visible', 'true', 'visibility'),
('how_it_works_visible', 'true', 'visibility'),
('benefits_visible', 'true', 'visibility'),
('contact_visible', 'true', 'visibility'),
('announcements_visible', 'true', 'visibility'),
('primary_accent_color', '#C8F169', 'appearance'),
('contact_email', 'contact@edutrack.edu', 'contact'),
('contact_phone', '+91 (800) 456-7890', 'contact'),
('contact_college_placeholder', 'Malla Reddy University / JNTUH', 'contact'),
('contact_address', 'EduTrack Academic Complex, HITEC City, Hyderabad', 'contact'),
('assistance_threshold_pct', '40.0', 'grading');

-- Default Announcement
INSERT IGNORE INTO announcements (title, content, badge_text, is_active, priority) VALUES
('Academic Portal Active', 'Welcome to the new EduTrack academic performance portal. Examination records for Internal 1, Internal 2 and Semester are now centrally accessible.', 'System Notice', 1, 10);

-- Initial Administrator Account
-- Username: admin
-- Password: AdminPassword@2026
INSERT IGNORE INTO users (user_id, username, email, password_hash, role, is_active) VALUES
(1, 'admin', 'admin@edutrack.edu', 'scrypt:32768:8:1$WpZDUnAoN669A7OI$65abed3aae5f4b8642a2afd3daec753f185d494d9e7b7c3ffc264a97862b9d8eb79db1425e5b8797174a09b995b635fc28ac0fb49a317ffcf4d05be408cab3b5', 'admin', 1);
