import logging
import subprocess

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_wtf import CSRFProtect
from flask_talisman import Talisman

from datetime import datetime

import config
from models import db_session, init_db, Download, DownloadFile
from megabasterd_client import MegabasterdClient
from worker import start_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# CSRF protection
csrf = CSRFProtect(app)

# Security headers — force_https=False because Cloudflare handles TLS
Talisman(
    app,
    force_https=False,
    session_cookie_secure=False,
    content_security_policy={
        "default-src": "'self'",
        "script-src": ["'self'", "https://cdn.tailwindcss.com"],
        "style-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com"],
        "worker-src": "'self'",
    },
)

mb_client = MegabasterdClient()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


# --- Dashboard ---

@app.route("/")
def index():
    downloads = db_session.query(Download).order_by(
        # downloading first, then queued, then processing, then complete/failed
        Download.status.desc(),
        Download.created_at.desc(),
    ).all()
    return render_template("index.html", downloads=downloads)


# --- Download CRUD ---

@app.route("/download/add")
def add_download_form():
    return render_template("add.html")


@app.route("/download", methods=["POST"])
def add_download():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("index"))

    year_str = request.form.get("year", "").strip()
    year = int(year_str) if year_str else None
    media_type = request.form.get("media_type", "movie")
    links_raw = request.form.get("links", "").strip()
    links = [l.strip() for l in links_raw.splitlines() if l.strip()]

    if not links:
        return redirect(url_for("index"))

    dl = Download(title=title, year=year, media_type=media_type)
    for link in links:
        dl.files.append(DownloadFile(url=link))

    try:
        mb_client.start(links)
        dl.status = "queued"
        dl.downloading_since = datetime.utcnow()
    except Exception as e:
        dl.status = "failed"
        dl.error_message = f"Failed to submit to megabasterd: {e}"

    db_session.add(dl)
    db_session.commit()

    return redirect(url_for("index"))


@app.route("/download/<int:download_id>")
def download_detail(download_id):
    dl = db_session.get(Download, download_id)
    if dl is None:
        return redirect(url_for("index"))
    return render_template("detail.html", download=dl)


@app.route("/download/<int:download_id>/retry", methods=["POST"])
def retry_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl and dl.status in ("failed", "cancelled"):
        try:
            mb_client.start(dl.links)
            dl.status = "queued"
            dl.downloading_since = datetime.utcnow()
            dl.error_message = None
            for f in dl.files:
                f.status = "queued"
                f.progress_bytes = 0
                f.total_bytes = 0
                f.speed = 0
                f.error_message = None
        except Exception as e:
            dl.error_message = f"Failed to submit to megabasterd: {e}"
        db_session.commit()
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/cancel", methods=["POST"])
def cancel_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl and dl.status in ("queued", "downloading"):
        dl.status = "cancelled"
        db_session.commit()
        try:
            for link in dl.links:
                mb_client.stop(link, delete=True)
        except Exception:
            pass
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/delete", methods=["POST"])
def delete_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl:
        db_session.delete(dl)
        db_session.commit()
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/clear509", methods=["POST"])
def clear509(download_id):
    try:
        mb_client.clear509()
    except Exception:
        pass
    return redirect(url_for("index"))


# --- API ---

@app.route("/api/status")
def api_status():
    downloads = db_session.query(Download).order_by(
        Download.status.desc(),
        Download.created_at.desc(),
    ).all()
    return jsonify([dl.to_dict() for dl in downloads])


# --- Entry point ---

def _validate_filebot():
    """Check that the FileBot binary is accessible. Logs a warning if not."""
    try:
        subprocess.run(
            [config.FILEBOT_BIN, "--version"],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "FileBot binary not accessible at: %s — file organization will fail",
            config.FILEBOT_BIN,
        )


def create_app():
    """Initialize database and start worker, return app."""
    config.validate()
    init_db()
    _validate_filebot()
    start_worker()
    return app


if __name__ == "__main__":
    from waitress import serve

    application = create_app()
    logging.getLogger().info("Starting MegaQueue on %s:%d", config.HOST, config.PORT)
    serve(application, host=config.HOST, port=config.PORT)
