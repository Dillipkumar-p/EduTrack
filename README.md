# EduTrack – Academic Performance Management Platform
> **Tagline:** Academic Performance, Made Visible.  
> **Brand Palette:** Premium Dark (`#090A0C`, `#141619`, `#1B1E21`, `#292D30`) with Lime Green Accent (`#C8F169`).

EduTrack is an institutional Student Academic Performance Management Platform built with **Python 3**, **Flask**, **Jinja2**, **Vanilla JavaScript**, and **MySQL**. It provides a unified data platform for administrators, faculty, and students to evaluate continuous assessments (Internal 1, Internal 2) and Semester results with automated early detection of learning deficits.

---

## 1. Key System Capabilities

- **Public Institutional Portal:**
  - Dynamic content managed directly from MySQL (`website_settings`, `announcements`).
  - Active SVG performance cohort trajectory graphic.
  - Institutional partnership contact form with phone format validation, MySQL persistence, anti-spam honeypot, and resilient SMTP notifications.
- **Admin Portal (`/admin`):**
  - Cohort analytics: class average, pass percentage, at-risk count.
  - Student & faculty profile enrollment and secure credential management.
  - Subject curriculum configuration (max marks, pass thresholds).
  - Examination tiers (Internal 1: 50/20, Internal 2: 50/20, Semester: 100/40, or custom).
  - **Website Appearance & Content Management**: Live editing of headline, description, brand accent colors, logo upload, and public section visibility toggles.
  - Audit trail logging every administrative and faculty intervention.
- **Teacher Portal (`/teacher`):**
  - Section student roster and evaluation console.
  - Real-time marks entry with dynamic boundary enforcement and duplicate prevention.
  - Automatic identification of students requiring assistance (failed subjects or aggregate below benchmark).
  - Subject averages and pass proportions.
- **Student Portal (`/student`):**
  - Identity strictly derived from authenticated server session (tamper-proof).
  - Individual examination scorecards (Internal 1, Internal 2, Semester).
  - Subject strengths (&ge;65%) and targeted focus areas (<60%).
  - Official print-ready academic transcript and downloadable PDF scorecard.

---

## 2. Technology Stack

- **Backend:** Python 3.10+, Flask 3+, Flask-WTF (CSRF Protection), Werkzeug (Password Hashing).
- **Database:** MySQL 8.0+ / Aiven Cloud MySQL with `mysql-connector-python` connection pooling.
- **Analytics:** Pandas, NumPy, Matplotlib.
- **Frontend:** HTML5, CSS3 Custom Properties, Vanilla JavaScript (no external runtime dependencies).
- **Production Server:** Gunicorn.
- **Cloud Hosting:** Render (Web Service) + Aiven (Managed MySQL).

---

## 3. Local Development Setup

### Prerequisites
- Python 3.10 or higher.
- MySQL Server 8.0+ running locally (or an Aiven Cloud MySQL service).

### Steps

1. **Clone repository & navigate to project:**
   ```bash
   git clone https://github.com/Dillipkumar-p/edutrack-student-performance.git
   cd edutrack
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Fill in your MySQL credentials:
   ```ini
   FLASK_SECRET_KEY=your-secure-random-secret-key-32-chars
   FLASK_ENV=development

   MYSQL_HOST=127.0.0.1
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DATABASE=edutrack_db
   MYSQL_SSL_CA=

   ADMIN_EMAIL=admin@edutrack.edu
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=
   SMTP_PASSWORD=
   SMTP_FROM_EMAIL=notifications@edutrack.edu
   ```

5. **Initialize Database Schema & Default Admin:**
   ```bash
   python app.py init-db
   ```
   *Default Admin Credentials:*
   - **Username:** `admin`
   - **Password:** `AdminPassword@2026`

6. **Run Database Health Diagnostic:**
   ```bash
   python check_db.py
   ```

7. **Run Unit Tests:**
   ```bash
   python -m unittest tests/test_edutrack.py
   ```

8. **Start Development Server:**
   ```bash
   python app.py
   ```
   Open `http://127.0.0.1:5000` in your web browser.

---

## 4. Production Deployment Guide (Aiven MySQL + Render)

### Step 1: Provision Aiven Managed MySQL
1. Sign in to [Aiven.io](https://aiven.io) and create a **MySQL** service (MySQL 8.0 or 8.4).
2. Once the service status turns **Running**, go to the **Overview** tab.
3. Note down the following connection parameters:
   - **Host:** e.g., `mysql-xxxx-edutrack.aivencloud.com`
   - **Port:** e.g., `20186`
   - **User:** `avnadmin`
   - **Password:** `<Aiven Generated Password>`
   - **Default Database:** `defaultdb` (or create `edutrack_db` under the **Databases** tab)
4. Download the **CA Certificate** (`ca.pem`) from the Aiven console if required by your network policy, or use Aiven's automatic SSL handshake.

### Step 2: Import Database Schema to Aiven
You can import the schema using MySQL Workbench, MySQL Shell, or the CLI:
```bash
mysql -h mysql-xxxx-edutrack.aivencloud.com -P 20186 -u avnadmin -p defaultdb < database.sql
```
Alternatively, deploy on Render and run `python app.py init-db` via the Render Shell.

### Step 3: Deploy Flask App on Render
1. Push your repository to **GitHub** (never commit your `.env` file).
2. Go to [Render.com](https://render.com) and click **New + &rarr; Web Service**.
3. Select your GitHub repository.
4. Set the following build settings:
   - **Name:** `edutrack`
   - **Environment:** `Python`
   - **Region:** Choose the region closest to your Aiven MySQL service.
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`

### Step 4: Configure Environment Variables in Render
Under the **Environment** tab in your Render Web Service dashboard, add the following variables:

| Environment Variable | Value / Description |
|----------------------|---------------------|
| `FLASK_SECRET_KEY`   | Strong random 32+ character string |
| `FLASK_ENV`          | `production` |
| `MYSQL_HOST`         | `<Aiven Host, e.g. mysql-xxxx.aivencloud.com>` |
| `MYSQL_PORT`         | `<Aiven Port, e.g. 20186>` |
| `MYSQL_USER`         | `avnadmin` |
| `MYSQL_PASSWORD`     | `<Aiven Password>` |
| `MYSQL_DATABASE`     | `defaultdb` (or `edutrack_db`) |
| `DB_SSL`             | `true` |
| `ADMIN_EMAIL`        | `admin@yourinstitution.edu` |
| `SMTP_HOST`          | `smtp.gmail.com` |
| `SMTP_PORT`          | `587` |
| `SMTP_USERNAME`      | `<Your institutional email username>` |
| `SMTP_PASSWORD`      | `<Your email app password>` |
| `SMTP_FROM_EMAIL`    | `notifications@yourinstitution.edu` |

Click **Save Changes**. Render will automatically build and deploy the container.

### Step 5: Verify Live Deployment
1. Open your live Render URL (e.g., `https://edutrack.onrender.com`).
2. Log in using the administrator credentials (`admin` / `AdminPassword@2026`).
3. Under **Website Appearance & Content**, customize your campus name and accent color.
4. Add faculty members, students, and curriculum subjects.
5. Record marks and verify that student transcripts render and print cleanly.

---

## 5. Security Architecture

- **Password Hashing:** Implemented with Werkzeug's adaptive `scrypt` hashing algorithm.
- **Role Isolation:** Strict server-side route decorators (`@role_required('admin')`, `@role_required('teacher')`, `@role_required('student')`). Browser-submitted roles are never trusted.
- **Student Privacy:** Student endpoints derive identity purely from `session['user_id']`. URL tampering or parameter spoofing is fundamentally impossible.
- **SQL Injection Prevention:** 100% parameterized queries via `mysql-connector-python`.
- **CSRF Defense:** Global CSRF protection across all forms via Flask-WTF.
- **Brute-Force Rate Limiting:** Enforces cooldowns on repeated invalid login attempts and contact submissions.
- **Audit Logging:** Every administrative mutation, score change, and login event is logged with IP address and timestamp in `audit_logs`.

---

## 6. Project Structure

```
edutrack/
├── app.py                      # Application factory & CLI entrypoint
├── config.py                   # Environment configuration & pooling setup
├── database.sql                # Complete normalized MySQL 8 schema & seeds
├── check_db.py                 # Interactive database health diagnostic script
├── requirements.txt            # Python dependencies (Gunicorn, Flask, Pandas, etc.)
├── Procfile                    # Render production process definition
├── .env.example                # Template for environment credentials
├── .gitignore                  # Git exclusions (credentials, uploads, pycache)
├── README.md                   # System documentation & deployment manual
│
├── backend/                    # Core modular application packages
│   ├── __init__.py             # Flask app factory, CSRF & context processor
│   ├── database.py             # MySQL connection pooling & transaction manager
│   ├── auth.py                 # Authentication, session security & role decorators
│   ├── public.py               # Landing page & contact form submission handler
│   ├── admin.py                # Admin portal routes & website appearance manager
│   ├── teacher.py              # Teacher roster & marks evaluation console
│   ├── student.py              # Student scorecard & transcript generator
│   ├── analytics.py            # Pandas/NumPy cohort grading & deficit detector
│   ├── email_service.py        # Resilient SMTP institutional enquiry alerts
│   └── utilities.py            # Audit logger, file upload handler, phone validator
│
├── templates/                  # Jinja2 template hierarchy
│   ├── base.html               # Master shell, dynamic accent injection, alerts
│   ├── error.html              # Custom 400/403/404/500 dark error template
│   ├── public/
│   │   └── index.html          # Public landing page with live SVG trajectory chart
│   ├── auth/
│   │   └── login.html          # Unified dark portal login screen
│   ├── admin/                  # Administrative management screens (12 views)
│   ├── teacher/                # Faculty management screens (7 views)
│   └── student/                # Student personal scorecard screens (5 views)
│
├── static/                     # Frontend static assets
│   ├── css/
│   │   ├── design-system.css   # Dark + Lime Green design system & typography
│   │   ├── public.css          # Landing page layout, grid, and hero visual
│   │   ├── portal.css          # Unified sidebar portal & scorecard layouts
│   │   └── print.css           # Clean black-and-white academic transcript print stylesheet
│   ├── js/
│   │   ├── main.js             # Flash toasts, mobile navigation & modal handlers
│   │   └── portal.js           # Live marks calculation & boundary validation
│   ├── images/
│   │   └── default-logo.svg    # Vector brand icon and monogram
│   └── uploads/                # Sanitized user brand asset storage
│
└── tests/
    └── test_edutrack.py        # Automated test suite (12 comprehensive tests)
```

---

## 7. License & Credits

Built for institutional academic excellence. Licensed under the MIT License.
