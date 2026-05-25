import os
import json
import sqlite3
import uuid
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_cors import CORS


BASE_DIR = Path(__file__).resolve().parent

def _is_platform_runtime() -> bool:
    return bool(os.getenv("VERCEL") or os.getenv("RENDER") or os.getenv("NETLIFY"))

DB_PATH = Path(os.getenv("PORTFOLIO_DB_PATH", "/tmp/portfolio.db" if _is_platform_runtime() else str(BASE_DIR / "portfolio.db")))
UPLOAD_DIR = Path(os.getenv("PORTFOLIO_UPLOAD_DIR", "/tmp/uploads" if _is_platform_runtime() else str(BASE_DIR / "static" / "uploads")))
LOCAL_CONFIG_PATH = Path(os.getenv("PORTFOLIO_LOCAL_CONFIG_PATH", "/tmp/local_config.json" if _is_platform_runtime() else str(BASE_DIR / "local_config.json")))
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def load_local_config() -> dict:
    default_config = {
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "change-me-now",
        "SECRET_KEY": "change-this-secret-key",
        "SMTP_ENABLED": False,
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "SMTP_USE_TLS": True,
        "NOTIFY_TO_EMAIL": "",
        "NOTIFY_FROM_EMAIL": "",
    }

    if not LOCAL_CONFIG_PATH.exists():
        try:
            LOCAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOCAL_CONFIG_PATH.write_text(
                json.dumps(default_config, indent=2), encoding="utf-8"
            )
        except OSError:
            # When deployed to platforms with read-only app storage,
            # just use defaults and avoid creating the file.
            pass
        return default_config

    try:
        file_config = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default_config

    return {
        "ADMIN_USERNAME": str(
            file_config.get("ADMIN_USERNAME", default_config["ADMIN_USERNAME"])
        ),
        "ADMIN_PASSWORD": str(
            file_config.get("ADMIN_PASSWORD", default_config["ADMIN_PASSWORD"])
        ),
        "SECRET_KEY": str(file_config.get("SECRET_KEY", default_config["SECRET_KEY"])),
        "SMTP_ENABLED": bool(file_config.get("SMTP_ENABLED", default_config["SMTP_ENABLED"])),
        "SMTP_HOST": str(file_config.get("SMTP_HOST", default_config["SMTP_HOST"])),
        "SMTP_PORT": int(file_config.get("SMTP_PORT", default_config["SMTP_PORT"])),
        "SMTP_USERNAME": str(file_config.get("SMTP_USERNAME", default_config["SMTP_USERNAME"])),
        "SMTP_PASSWORD": str(file_config.get("SMTP_PASSWORD", default_config["SMTP_PASSWORD"])),
        "SMTP_USE_TLS": bool(file_config.get("SMTP_USE_TLS", default_config["SMTP_USE_TLS"])),
        "NOTIFY_TO_EMAIL": str(file_config.get("NOTIFY_TO_EMAIL", default_config["NOTIFY_TO_EMAIL"])),
        "NOTIFY_FROM_EMAIL": str(file_config.get("NOTIFY_FROM_EMAIL", default_config["NOTIFY_FROM_EMAIL"])),
    }


local_config = load_local_config()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("PORTFOLIO_SECRET_KEY", local_config["SECRET_KEY"])
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
app.config["ADMIN_USERNAME"] = os.getenv(
    "PORTFOLIO_ADMIN_USERNAME", local_config["ADMIN_USERNAME"]
)
app.config["ADMIN_PASSWORD"] = os.getenv(
    "PORTFOLIO_ADMIN_PASSWORD", local_config["ADMIN_PASSWORD"]
)
app.config["SMTP_ENABLED"] = bool(local_config["SMTP_ENABLED"])
app.config["SMTP_HOST"] = local_config["SMTP_HOST"]
app.config["SMTP_PORT"] = local_config["SMTP_PORT"]
app.config["SMTP_USERNAME"] = local_config["SMTP_USERNAME"]
app.config["SMTP_PASSWORD"] = local_config["SMTP_PASSWORD"]
app.config["SMTP_USE_TLS"] = bool(local_config["SMTP_USE_TLS"])
app.config["NOTIFY_TO_EMAIL"] = local_config["NOTIFY_TO_EMAIL"]
app.config["NOTIFY_FROM_EMAIL"] = local_config["NOTIFY_FROM_EMAIL"]

CORS(app)


DEFAULT_PROJECTS = [
    {
        "title": "Finance Tracker",
        "description": "Track income and expenses with charts and spending insights.",
        "technologies": "Python, Flask, SQLite, JavaScript, REST API",
        "github_url": "https://github.com/monisolaoladeji/finance_tracker",
        "demo_url": "#",
        "sort_order": 1,
    },
    {
        "title": "E-commerce Cart App",
        "description": "A mini e-commerce app with cart updates and product browsing.",
        "technologies": "Python, Flask, Flask-SocketIO, JavaScript, HTML/CSS",
        "github_url": "https://github.com/monisolaoladeji/ecommerce",
        "demo_url": "#",
        "sort_order": 2,
    },
    {
        "title": "Blog App",
        "description": "A full CRUD blog platform with SQLite-backed post management.",
        "technologies": "Python, Flask, SQLite, HTML, CSS",
        "github_url": "https://github.com/monisolaoladeji/blog",
        "demo_url": "#",
        "sort_order": 3,
    },
    {
        "title": "Real-Time Chat App",
        "description": "A messaging app with image upload and real-time chat using SocketIO.",
        "technologies": "Python, Flask, Flask-SocketIO, JavaScript, HTML/CSS",
        "github_url": "https://github.com/monisolaoladeji/chat--app",
        "demo_url": "#",
        "sort_order": 4,
    },
    {
        "title": "To-Do List App",
        "description": "A simple and clean task manager for daily task tracking.",
        "technologies": "HTML, CSS, JavaScript",
        "github_url": "https://github.com/monisolaoladeji/todolist",
        "demo_url": "#",
        "sort_order": 5,
    },
]


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                technologies TEXT NOT NULL,
                github_url TEXT NOT NULL,
                demo_url TEXT NOT NULL,
                screenshot_path TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitor_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_name TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                message_body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0
            );
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM projects;").fetchone()[0]
        if count == 0:
            for project in DEFAULT_PROJECTS:
                conn.execute(
                    """
                    INSERT INTO projects
                    (title, description, technologies, github_url, demo_url, screenshot_path, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        project["title"],
                        project["description"],
                        project["technologies"],
                        project["github_url"],
                        project["demo_url"],
                        "",
                        project["sort_order"],
                    ),
                )
        setting_defaults = {
            "profile_photo_path": "",
            "contact_email": "",
            "contact_phone": "",
            "contact_location": "",
            "contact_linkedin": "",
            "contact_github": "",
        }
        for key, value in setting_defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                (key, value),
            )


def get_settings_map(db):
    rows = db.execute("SELECT key, value FROM settings;").fetchall()
    return {row["key"]: row["value"] for row in rows}


def allowed_image(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def save_image(file_obj) -> str:
    if not file_obj or not getattr(file_obj, "filename", ""):
        return ""
    if not allowed_image(file_obj.filename):
        raise ValueError("Only image files are allowed.")

    ext = file_obj.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest_path = UPLOAD_DIR / filename
    file_obj.save(dest_path)
    return f"uploads/{filename}"


def is_admin_logged_in() -> bool:
    return bool(session.get("is_admin"))


def admin_required(route_handler):
    @wraps(route_handler)
    def wrapper(*args, **kwargs):
        if not is_admin_logged_in():
            return redirect(url_for("admin_login"))
        return route_handler(*args, **kwargs)

    return wrapper


def send_new_message_notification(sender_name: str, sender_email: str, message_body: str, created_at: str) -> bool:
    if not app.config.get("SMTP_ENABLED"):
        return False

    notify_to = (app.config.get("NOTIFY_TO_EMAIL") or "").strip()
    notify_from = (app.config.get("NOTIFY_FROM_EMAIL") or "").strip()
    smtp_host = (app.config.get("SMTP_HOST") or "").strip()
    smtp_username = (app.config.get("SMTP_USERNAME") or "").strip()
    smtp_password = app.config.get("SMTP_PASSWORD") or ""

    if not (notify_to and notify_from and smtp_host and smtp_username and smtp_password):
        return False

    msg = EmailMessage()
    msg["Subject"] = "New portfolio visitor message"
    msg["From"] = notify_from
    msg["To"] = notify_to
    msg["Reply-To"] = sender_email
    msg.set_content(
        f"New visitor message received.\n\n"
        f"Name: {sender_name}\n"
        f"Email: {sender_email}\n"
        f"Time (UTC): {created_at}\n\n"
        f"Message:\n{message_body}\n"
    )

    try:
        with smtplib.SMTP(smtp_host, int(app.config.get("SMTP_PORT", 587)), timeout=15) as server:
            if app.config.get("SMTP_USE_TLS"):
                server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"Email notification failed: {exc}")
        return False


def get_project_screenshots(db, project_id):
    return db.execute(
        """
        SELECT id, image_path, caption, sort_order
        FROM project_screenshots
        WHERE project_id = ?
        ORDER BY sort_order ASC, id ASC;
        """,
        (project_id,),
    ).fetchall()


@app.route("/")
def index():
    db = get_db()
    projects = db.execute(
        """
        SELECT id, title, description, technologies, github_url, demo_url, screenshot_path
        FROM projects
        ORDER BY sort_order ASC, id ASC;
        """
    ).fetchall()
    projects_with_screenshots = []
    for project in projects:
        screenshots = get_project_screenshots(db, project["id"])
        projects_with_screenshots.append({
            **project,
            "screenshots": screenshots
        })
    settings = get_settings_map(db)
    return render_template(
        "index.html",
        projects=projects_with_screenshots,
        profile_photo_path=settings.get("profile_photo_path", ""),
        contact_email=settings.get("contact_email", ""),
        contact_phone=settings.get("contact_phone", ""),
        contact_location=settings.get("contact_location", ""),
        contact_linkedin=settings.get("contact_linkedin", ""),
        contact_github=settings.get("contact_github", ""),
    )


@app.post("/contact-messages")
def submit_contact_message():
    sender_name = (request.form.get("name") or "").strip()
    sender_email = (request.form.get("email") or "").strip()
    message_body = (request.form.get("message") or "").strip()

    if not sender_name or not sender_email or not message_body:
        flash("Please fill in name, email, and message before sending.", "error")
        return redirect(url_for("index", _anchor="contact"))

    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db = get_db()
    db.execute(
        """
        INSERT INTO visitor_messages (sender_name, sender_email, message_body, created_at, is_read)
        VALUES (?, ?, ?, ?, 0);
        """,
        (sender_name, sender_email, message_body, created_at),
    )
    db.commit()

    send_new_message_notification(sender_name, sender_email, message_body, created_at)
    flash("Thanks! Your message has been sent.", "success")
    return redirect(url_for("index", _anchor="contact"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if (
            username == app.config["ADMIN_USERNAME"]
            and password == app.config["ADMIN_PASSWORD"]
        ):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("admin_login.html")


@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
    db = get_db()
    projects = db.execute(
        """
        SELECT id, title, description, technologies, github_url, demo_url, screenshot_path, sort_order
        FROM projects
        ORDER BY sort_order ASC, id ASC;
        """
    ).fetchall()
    projects_with_screenshots = []
    for project in projects:
        screenshots = get_project_screenshots(db, project["id"])
        projects_with_screenshots.append({
            **project,
            "screenshots": screenshots
        })
    visitor_messages = db.execute(
        """
        SELECT id, sender_name, sender_email, message_body, created_at, is_read
        FROM visitor_messages
        ORDER BY id DESC;
        """
    ).fetchall()
    settings = get_settings_map(db)
    return render_template(
        "admin_dashboard.html",
        projects=projects_with_screenshots,
        visitor_messages=visitor_messages,
        profile_photo_path=settings.get("profile_photo_path", ""),
        settings=settings,
        admin_username=app.config["ADMIN_USERNAME"],
    )


@app.post("/admin/projects/<int:project_id>/screenshots/add")
@admin_required
def add_project_screenshot(project_id: int):
    screenshot = request.files.get("screenshot")
    caption = (request.form.get("caption") or "").strip()
    sort_order = int((request.form.get("sort_order") or "999").strip())
    
    if not screenshot or not screenshot.filename:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": "Please choose a screenshot."}), 400
        flash("Please choose a screenshot.", "error")
        return redirect(url_for("admin_dashboard"))
    
    db = get_db()
    existing = db.execute("SELECT id FROM projects WHERE id = ?;", (project_id,)).fetchone()
    if not existing:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": "Project not found."}), 404
        flash("Project not found.", "error")
        return redirect(url_for("admin_dashboard"))
    
    try:
        image_path = save_image(screenshot)
    except ValueError as exc:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("admin_dashboard"))
    
    db.execute(
        "INSERT INTO project_screenshots (project_id, image_path, caption, sort_order) VALUES (?, ?, ?, ?);",
        (project_id, image_path, caption, sort_order),
    )
    db.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "message": "Screenshot added.",
            "screenshot": {
                "id": db.execute("SELECT last_insert_rowid()").fetchone()[0],
                "image_path": image_path,
                "caption": caption,
                "sort_order": sort_order
            }
        })
    
    flash("Screenshot added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/projects/<int:project_id>/screenshots/<int:screenshot_id>/delete")
@admin_required
def delete_project_screenshot(project_id: int, screenshot_id: int):
    db = get_db()
    db.execute("DELETE FROM project_screenshots WHERE id = ? AND project_id = ?;", (screenshot_id, project_id))
    db.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "message": "Screenshot deleted."
        })
    
    flash("Screenshot deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/profile-photo")
@admin_required
def update_profile_photo():
    file_obj = request.files.get("profile_photo")
    if not file_obj or not file_obj.filename:
        flash("Please choose a profile photo.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        photo_path = save_image(file_obj)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    db.execute(
        "UPDATE settings SET value = ? WHERE key = 'profile_photo_path';", (photo_path,)
    )
    db.commit()
    flash("Profile photo updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/projects/create")
@admin_required
def create_project():
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    technologies = (request.form.get("technologies") or "").strip()
    github_url = (request.form.get("github_url") or "").strip() or "#"
    demo_url = (request.form.get("demo_url") or "").strip() or "#"
    sort_order = int((request.form.get("sort_order") or "999").strip())
    screenshot = request.files.get("screenshot")

    if not title or not description or not technologies:
        flash("Title, description, and technologies are required.", "error")
        return redirect(url_for("admin_dashboard"))

    screenshot_path = ""
    if screenshot and screenshot.filename:
        try:
            screenshot_path = save_image(screenshot)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_dashboard"))

    db = get_db()
    db.execute(
        """
        INSERT INTO projects (title, description, technologies, github_url, demo_url, screenshot_path, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (title, description, technologies, github_url, demo_url, screenshot_path, sort_order),
    )
    db.commit()
    flash("Project added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/projects/<int:project_id>/update")
@admin_required
def update_project(project_id: int):
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    technologies = (request.form.get("technologies") or "").strip()
    github_url = (request.form.get("github_url") or "").strip() or "#"
    demo_url = (request.form.get("demo_url") or "").strip() or "#"
    sort_order = int((request.form.get("sort_order") or "999").strip())
    screenshot = request.files.get("screenshot")

    if not title or not description or not technologies:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": "Title, description, and technologies are required."}), 400
        flash("Title, description, and technologies are required.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    existing = db.execute(
        "SELECT screenshot_path FROM projects WHERE id = ?;", (project_id,)
    ).fetchone()
    if not existing:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": "Project not found."}), 404
        flash("Project not found.", "error")
        return redirect(url_for("admin_dashboard"))

    screenshot_path = existing["screenshot_path"]
    if screenshot and screenshot.filename:
        try:
            screenshot_path = save_image(screenshot)
        except ValueError as exc:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "message": str(exc)}), 400
            flash(str(exc), "error")
            return redirect(url_for("admin_dashboard"))

    db.execute(
        """
        UPDATE projects
        SET title = ?, description = ?, technologies = ?, github_url = ?, demo_url = ?, screenshot_path = ?, sort_order = ?
        WHERE id = ?;
        """,
        (
            title,
            description,
            technologies,
            github_url,
            demo_url,
            screenshot_path,
            sort_order,
            project_id,
        ),
    )
    db.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True, 
            "message": "Project updated.",
            "project": {
                "id": project_id,
                "title": title,
                "description": description,
                "technologies": technologies,
                "github_url": github_url,
                "demo_url": demo_url,
                "sort_order": sort_order,
                "screenshot_path": screenshot_path
            }
        })
    
    flash("Project updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/projects/<int:project_id>/delete")
@admin_required
def delete_project(project_id: int):
    db = get_db()
    db.execute("DELETE FROM projects WHERE id = ?;", (project_id,))
    db.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/contact")
@admin_required
def update_contact_info():
    contact_email = (request.form.get("contact_email") or "").strip()
    contact_phone = (request.form.get("contact_phone") or "").strip()
    contact_location = (request.form.get("contact_location") or "").strip()
    contact_linkedin = (request.form.get("contact_linkedin") or "").strip()
    contact_github = (request.form.get("contact_github") or "").strip()

    db = get_db()
    updates = {
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "contact_location": contact_location,
        "contact_linkedin": contact_linkedin,
        "contact_github": contact_github,
    }
    for key, value in updates.items():
        db.execute("UPDATE settings SET value = ? WHERE key = ?;", (value, key))
    db.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "message": "Contact details updated.",
            "settings": updates
        })

    flash("Contact details updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/messages/<int:message_id>/read")
@admin_required
def mark_message_as_read(message_id: int):
    db = get_db()
    db.execute(
        "UPDATE visitor_messages SET is_read = 1 WHERE id = ?;",
        (message_id,),
    )
    db.commit()
    flash("Message marked as read.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/messages/<int:message_id>/delete")
@admin_required
def delete_message(message_id: int):
    db = get_db()
    db.execute("DELETE FROM visitor_messages WHERE id = ?;", (message_id,))
    db.commit()
    flash("Message deleted.", "success")
    return redirect(url_for("admin_dashboard"))


init_db()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
