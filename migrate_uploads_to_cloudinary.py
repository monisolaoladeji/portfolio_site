import hashlib
import json
import mimetypes
import os
import ssl
import sqlite3
import time
import urllib.request
from pathlib import Path

try:
    import certifi
except ImportError:
    certifi = None

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
LOCAL_CONFIG_PATH = BASE_DIR / "local_config.json"
DB_PATH = BASE_DIR / "portfolio.db"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def load_local_config():
    if LOCAL_CONFIG_PATH.exists():
        try:
            return json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def get_env_or_config(key, config):
    return os.getenv(f"PORTFOLIO_{key}", config.get(key, "")).strip()


def cloudinary_enabled(config):
    return all(
        get_env_or_config(name, config)
        for name in ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"]
    )


def _encode_multipart_formdata(fields, files):
    boundary = uuid = hashlib.sha1(str(time.time()).encode("utf-8")).hexdigest()
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, filename, file_data, content_type in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return bytes(body), content_type_header


def upload_file_to_cloudinary(path: Path, config: dict) -> str:
    cloud_name = get_env_or_config("CLOUDINARY_CLOUD_NAME", config)
    api_key = get_env_or_config("CLOUDINARY_API_KEY", config)
    api_secret = get_env_or_config("CLOUDINARY_API_SECRET", config)
    if not (cloud_name and api_key and api_secret):
        return ""

    timestamp = int(time.time())
    signature = hashlib.sha1(
        f"timestamp={timestamp}{api_secret}".encode("utf-8")
    ).hexdigest()

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    image_bytes = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    fields = {
        "api_key": api_key,
        "timestamp": str(timestamp),
        "signature": signature,
    }
    files = [("file", path.name, image_bytes, content_type)]
    body, content_type_header = _encode_multipart_formdata(fields, files)

    request = urllib.request.Request(
        upload_url,
        data=body,
        headers={"Content-Type": content_type_header},
    )
    if certifi:
        context = ssl.create_default_context(cafile=certifi.where())
    else:
        context = ssl._create_unverified_context()

    with urllib.request.urlopen(request, context=context, timeout=60) as response:
        response_data = json.loads(response.read().decode("utf-8"))
        return response_data.get("secure_url", "")


def normalize_local_path(path: str) -> str:
    if not path:
        return ""
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return ""
    if normalized.startswith("static/"):
        normalized = normalized.split("static/", 1)[-1]
    if normalized.startswith("uploads/"):
        normalized = normalized.split("uploads/", 1)[-1].lstrip("/")
    return normalized


def resolve_upload_file(path: str) -> Path | None:
    normalized = normalize_local_path(path)
    if not normalized:
        return None
    candidate = UPLOAD_DIR / normalized
    if candidate.exists():
        return candidate
    candidate = UPLOAD_DIR / Path(normalized).name
    return candidate if candidate.exists() else None


def migrate_paths(connection, config):
    changed = 0
    cursor = connection.cursor()

    def update_row(table, id_col, id_value, path_col, old_path, new_url):
        nonlocal changed
        cursor.execute(
            f"UPDATE {table} SET {path_col} = ? WHERE {id_col} = ?;",
            (new_url, id_value),
        )
        changed += 1

    rows = cursor.execute("SELECT key, value FROM settings WHERE key = 'profile_photo_path';").fetchall()
    for key, value in rows:
        upload_path = resolve_upload_file(value)
        if upload_path:
            print(f"Uploading profile photo: {upload_path.name}")
            new_url = upload_file_to_cloudinary(upload_path, config)
            if new_url:
                update_row("settings", "key", key, "value", value, new_url)
                print(f"  migrated to {new_url}")

    rows = cursor.execute("SELECT id, screenshot_path FROM projects;").fetchall()
    for project_id, screenshot_path in rows:
        upload_path = resolve_upload_file(screenshot_path)
        if upload_path:
            print(f"Uploading project screenshot ({project_id}): {upload_path.name}")
            new_url = upload_file_to_cloudinary(upload_path, config)
            if new_url:
                update_row("projects", "id", project_id, "screenshot_path", screenshot_path, new_url)
                print(f"  migrated to {new_url}")

    rows = cursor.execute("SELECT id, image_path FROM project_screenshots;").fetchall()
    for screenshot_id, image_path in rows:
        upload_path = resolve_upload_file(image_path)
        if upload_path:
            print(f"Uploading screenshot row {screenshot_id}: {upload_path.name}")
            new_url = upload_file_to_cloudinary(upload_path, config)
            if new_url:
                update_row("project_screenshots", "id", screenshot_id, "image_path", image_path, new_url)
                print(f"  migrated to {new_url}")

    connection.commit()
    return changed


def main():
    config = load_local_config()
    if not cloudinary_enabled(config):
        print("Cloudinary credentials are missing. Please set them in local_config.json or environment variables.")
        return

    if not UPLOAD_DIR.exists():
        print(f"Upload directory not found: {UPLOAD_DIR}")
        return

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        count = migrate_paths(conn, config)

    print(f"Migration complete. Updated {count} database rows.")
    print("Your migrated images are now stored in Cloudinary and will be served from the cloud.")


if __name__ == "__main__":
    main()
