import os
import json
import time
import uuid
import hashlib
import mimetypes
import urllib.request
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
from functools import wraps
from email.message import EmailMessage
import smtplib

from pymongo import MongoClient
from bson.objectid import ObjectId

# ========================
# CONFIG
# ========================

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

CORS(app)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "portfolio_site")

if not MONGODB_URI:
    raise Exception("MONGODB_URI is missing in environment variables")

# ========================
# MONGODB (ONLY SOURCE OF TRUTH)
# ========================

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

try:
    mongo_client.server_info()
except Exception as e:
    raise Exception(f"MongoDB connection failed: {e}")

db = mongo_client[MONGO_DB_NAME]

projects_collection = db["projects"]
screenshots_collection = db["project_screenshots"]
settings_collection = db["settings"]
messages_collection = db["visitor_messages"]

# ========================
# CLOUDINARY
# ========================

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

CLOUDINARY_ENABLED = all([
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
])

# ========================
# HELPERS
# ========================

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "png", "jpg", "jpeg", "gif", "webp"
    }


def encode_multipart(fields, files):
    boundary = uuid.uuid4().hex
    body = bytearray()

    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.extend(str(v).encode())
        body.extend(b"\r\n")

    for f in files:
        field, filename, data, content_type = f
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())

    return bytes(body), f"multipart/form-data; boundary={boundary}"


def upload_to_cloudinary(file):
    if not CLOUDINARY_ENABLED:
        return ""

    timestamp = int(time.time())
    signature = hashlib.sha1(
        f"timestamp={timestamp}{CLOUDINARY_API_SECRET}".encode()
    ).hexdigest()

    file_bytes = file.read()
    file.stream.seek(0)

    content_type = file.mimetype or "application/octet-stream"

    fields = {
        "api_key": CLOUDINARY_API_KEY,
        "timestamp": timestamp,
        "signature": signature
    }

    files = [("file", file.filename, file_bytes, content_type)]

    body, content_type_header = encode_multipart(fields, files)

    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": content_type_header
    })

    try:
        res = urllib.request.urlopen(req)
        data = json.loads(res.read().decode())
        return data.get("secure_url", "")
    except Exception as e:
        print("Cloudinary error:", e)
        return ""


def save_image(file):
    if not file or not file.filename:
        return ""

    if not allowed(file.filename):
        raise Exception("Invalid image type")

    if CLOUDINARY_ENABLED:
        url = upload_to_cloudinary(file)
        if url:
            return url

    # fallback (NOT recommended but kept safe)
    filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.',1)[1]}"
    path = f"static/uploads/{filename}"
    os.makedirs("static/uploads", exist_ok=True)
    file.save(path)
    return path


# ========================
# ROUTES
# ========================

@app.route("/")
def index():
    projects = list(projects_collection.find().sort("sort_order", 1))

    for p in projects:
        p["id"] = str(p["_id"])
        p["screenshots"] = list(
            screenshots_collection.find({"project_id": p["id"]})
        )

    settings = {s["key"]: s["value"] for s in settings_collection.find()}

    return render_template("index.html",
        projects=projects,
        settings=settings
    )


# ========================
# ADMIN AUTH
# ========================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/login", methods=["POST", "GET"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == os.getenv("ADMIN_USER") and \
           request.form["password"] == os.getenv("ADMIN_PASS"):
            session["admin"] = True
            return redirect("/admin")
        flash("Wrong login")
    return render_template("login.html")


@app.route("/admin")
@login_required
def admin():
    projects = list(projects_collection.find().sort("sort_order", 1))
    return render_template("admin.html", projects=projects)


# ========================
# PROJECT CREATE
# ========================

@app.route("/admin/projects/create", methods=["POST"])
@login_required
def create_project():
    data = request.form

    screenshot = request.files.get("screenshot")
    image_url = save_image(screenshot) if screenshot else ""

    projects_collection.insert_one({
        "title": data["title"],
        "description": data["description"],
        "technologies": data["technologies"],
        "github_url": data.get("github_url", "#"),
        "demo_url": data.get("demo_url", "#"),
        "screenshot": image_url,
        "sort_order": int(data.get("sort_order", 999))
    })

    return redirect("/admin")


# ========================
# SCREENSHOTS
# ========================

@app.route("/admin/projects/<pid>/screenshots", methods=["POST"])
@login_required
def add_screenshot(pid):
    file = request.files.get("file")
    caption = request.form.get("caption", "")

    url = save_image(file)

    screenshots_collection.insert_one({
        "project_id": pid,
        "image": url,
        "caption": caption
    })

    return jsonify({"success": True})


# ========================
# CONTACT MESSAGES
# ========================

@app.route("/contact", methods=["POST"])
def contact():
    messages_collection.insert_one({
        "name": request.form["name"],
        "email": request.form["email"],
        "message": request.form["message"],
        "created_at": datetime.utcnow().isoformat(),
        "read": False
    })

    return redirect("/")


# ========================
# RUN
# ========================

if __name__ == "__main__":
    app.run()
