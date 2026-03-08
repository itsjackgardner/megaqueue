import logging

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_wtf import CSRFProtect
from flask_talisman import Talisman

import config
from models import db_session, init_db, Download
from auth import check_password, login_required
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
    content_security_policy={
        "default-src": "'self'",
        "script-src": ["'self'", "https://cdn.tailwindcss.com"],
        "style-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com"],
    },
)

mb_client = MegabasterdClient()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


# --- Auth routes ---

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if check_password(request.form.get("password", "")):
            session["authenticated"] = True
            next_url = request.args.get("next", "/")
            return redirect(next_url)
        error = "Invalid password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Dashboard ---

@app.route("/")
@login_required
def index():
    downloads = db_session.query(Download).order_by(
        # downloading first, then queued, then processing, then complete/failed
        Download.status.desc(),
        Download.created_at.desc(),
    ).all()
    return render_template("index.html", downloads=downloads)


# --- Download CRUD ---

@app.route("/download/add")
@login_required
def add_download_form():
    return render_template("add.html")


@app.route("/download", methods=["POST"])
@login_required
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
    dl.links = links
    db_session.add(dl)
    db_session.commit()

    return redirect(url_for("index"))


@app.route("/download/<int:download_id>")
@login_required
def download_detail(download_id):
    dl = db_session.get(Download, download_id)
    if dl is None:
        return redirect(url_for("index"))
    return render_template("detail.html", download=dl)


@app.route("/download/<int:download_id>/retry", methods=["POST"])
@login_required
def retry_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl and dl.status in ("failed", "cancelled"):
        dl.status = "queued"
        dl.error_message = None
        dl.progress_bytes = 0
        dl.total_bytes = 0
        dl.speed = 0
        db_session.commit()
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/cancel", methods=["POST"])
@login_required
def cancel_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl and dl.status in ("queued", "downloading"):
        dl.status = "cancelled"
        db_session.commit()
        # If downloading, the worker loop will detect the status change and stop via API
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/delete", methods=["POST"])
@login_required
def delete_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl:
        db_session.delete(dl)
        db_session.commit()
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/clear509", methods=["POST"])
@login_required
def clear509(download_id):
    try:
        mb_client.clear509()
    except Exception:
        pass
    return redirect(url_for("index"))


# --- API ---

@app.route("/api/status")
@login_required
def api_status():
    downloads = db_session.query(Download).order_by(
        Download.status.desc(),
        Download.created_at.desc(),
    ).all()
    return jsonify([dl.to_dict() for dl in downloads])


# --- Entry point ---

def create_app():
    """Initialize database and start worker, return app."""
    config.validate()
    init_db()
    start_worker()
    return app


if __name__ == "__main__":
    from waitress import serve

    application = create_app()
    logging.getLogger().info("Starting MegaQueue on %s:%d", config.HOST, config.PORT)
    serve(application, host=config.HOST, port=config.PORT)
