#!/usr/bin/env python3
"""
MarkItDown Web — a local/self-hosted web interface for converting files to Markdown.

Uses Microsoft's markitdown library (https://github.com/microsoft/markitdown).
Files are converted in memory and never leave the machine this runs on.

Optional admin login:
  Set ADMIN_USERNAME and ADMIN_PASSWORD (and ideally SECRET_KEY) as environment
  variables to require a login. If they are not set, the app runs open — which is
  what you want for purely local use. When exposed to the public internet, set
  them so only you can get in.
"""

import io
import os
import hmac
import zipfile
import secrets
import traceback
from functools import wraps

from flask import (
    Flask, request, jsonify, send_file, Response,
    session, redirect, url_for,
)
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Make audio (.mp3/.wav) "just work" without a system ffmpeg install.
# imageio-ffmpeg ships a static ffmpeg binary via pip; point pydub at it.
# A system-installed ffmpeg (if present) still takes priority.
# ---------------------------------------------------------------------------
try:
    import shutil
    if not shutil.which("ffmpeg"):
        import imageio_ffmpeg
        _ff = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["PATH"] = os.path.dirname(_ff) + os.pathsep + os.environ.get("PATH", "")
        try:
            from pydub import AudioSegment
            AudioSegment.converter = _ff
            AudioSegment.ffmpeg = _ff
        except Exception:
            pass
except Exception:
    pass  # audio just falls back to metadata-only if nothing is available

from markitdown import MarkItDown

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB per request
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# --- Auth config -----------------------------------------------------------
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
AUTH_ENABLED = bool(ADMIN_USERNAME and ADMIN_PASSWORD)

# Optional API key for programmatic (agent/script) access to /api/ routes.
# Agents send it as a header:  X-API-Key: <key>   (or  Authorization: Bearer <key>).
# Browser users still use the normal login. If unset, the API key path is off.
API_KEY = os.environ.get("API_KEY")

_md = MarkItDown(enable_plugins=False)


def _valid_api_key() -> bool:
    """True if the request carries a correct API key. Constant-time compare."""
    if not API_KEY:
        return False
    key = request.headers.get("X-API-Key")
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            key = auth[7:]
    return bool(key) and hmac.compare_digest(key, API_KEY)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if AUTH_ENABLED and not session.get("logged_in"):
            # Agents authenticate with an API key on the API routes.
            if request.path.startswith("/api/") and _valid_api_key():
                return f(*args, **kwargs)
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def convert_one(filename: str, data: bytes) -> str:
    stream = io.BytesIO(data)
    result = _md.convert_stream(stream, file_extension=os.path.splitext(filename)[1])
    return result.text_content


# --- Routes ----------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_ENABLED:
        return redirect(url_for("index"))
    error = ""
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        # constant-time comparison to avoid timing leaks
        ok = hmac.compare_digest(u, ADMIN_USERNAME) & hmac.compare_digest(p, ADMIN_PASSWORD)
        if ok:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Incorrect username or password."
    return Response(LOGIN_HTML.replace("{{ERROR}}", error), mimetype="text/html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login") if AUTH_ENABLED else url_for("index"))


@app.route("/")
@login_required
def index():
    html = INDEX_HTML.replace("{{AUTH}}", "true" if AUTH_ENABLED else "false")
    return Response(html, mimetype="text/html")


@app.route("/api/convert", methods=["POST"])
@login_required
def api_convert():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded."}), 400

    results = []
    for f in files:
        name = secure_filename(f.filename) or "file"
        try:
            data = f.read()
            md_text = convert_one(f.filename, data)
            results.append({"name": os.path.splitext(name)[0] + ".md",
                            "source": f.filename, "markdown": md_text, "error": None})
        except Exception as e:  # noqa: BLE001
            results.append({"name": os.path.splitext(name)[0] + ".md",
                            "source": f.filename, "markdown": "",
                            "error": f"{type(e).__name__}: {e}"})
            app.logger.error("Conversion failed for %s\n%s", f.filename, traceback.format_exc())

    return jsonify({"results": results})


@app.route("/api/zip", methods=["POST"])
@login_required
def api_zip():
    payload = request.get_json(silent=True) or {}
    entries = payload.get("files", [])
    if not entries:
        return jsonify({"error": "Nothing to zip."}), 400

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        seen = {}
        for e in entries:
            name = e.get("name") or "file.md"
            if name in seen:
                seen[name] += 1
                base, ext = os.path.splitext(name)
                name = f"{base}_{seen[name]}{ext}"
            else:
                seen[name] = 0
            zf.writestr(name, e.get("markdown", ""))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True, download_name="markdown.zip")


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "Upload too large (limit 100 MB per request)."}), 413


def _load(name, fallback):
    try:
        with open(os.path.join(os.path.dirname(__file__), name), encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return fallback


INDEX_HTML = _load("index.html", "<h1>index.html missing</h1>")
LOGIN_HTML = _load("login.html", "<h1>login.html missing</h1>")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5005"))
    host = os.environ.get("HOST", "127.0.0.1")
    mode = "WITH admin login" if AUTH_ENABLED else "open (no login)"
    print(f"\n  MarkItDown Web — {mode}")
    print(f"  Running at  http://{host}:{port}\n")
    app.run(host=host, port=port, debug=False)
