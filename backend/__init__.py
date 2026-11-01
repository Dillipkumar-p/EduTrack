import logging
from flask import Flask, render_template, session
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import Config
from backend.database import init_pool, init_database_schema
from backend.utilities import get_website_settings

# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("edutrack")

csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )
    app.config.from_object(config_class)

    # Initialize extensions
    csrf.init_app(app)

    # Initialize database pool
    with app.app_context():
        try:
            init_pool()
        except Exception as e:
            logger.warning(f"Database pool lazy initialization scheduled: {e}")

    # Register Blueprints
    from backend.public import public_bp
    from backend.auth import auth_bp
    from backend.admin import admin_bp
    from backend.teacher import teacher_bp
    from backend.student import student_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    # Global Jinja Context Processor
    @app.context_processor
    def inject_global_data():
        try:
            settings = get_website_settings()
        except Exception:
            settings = {}
        
        current_user = {
            "is_authenticated": bool(session.get("user_id")),
            "user_id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role"),
            "full_name": session.get("full_name", session.get("username", "Guest")),
            "roll_no": session.get("roll_no"),
            "section": session.get("section")
        }
        return dict(settings=settings, current_user=current_user)

    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("error.html", error_code=403, error_title="Access Forbidden",
                               error_message="You do not have administrative authorization to view this area."), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("error.html", error_code=404, error_title="Page Not Found",
                               error_message="The requested academic resource or page could not be located."), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("error.html", error_code=500, error_title="Internal System Notice",
                               error_message="An unexpected system anomaly occurred. The event has been logged for review."), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        return render_template("error.html", error_code=400, error_title="Security Verification Expired",
                               error_message="Your security session token expired. Please return to the previous screen, refresh, and submit again."), 400

    return app
