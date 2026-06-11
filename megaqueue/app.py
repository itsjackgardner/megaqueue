import logging

from flask import Flask, render_template, request, redirect, url_for, jsonify

log = logging.getLogger(__name__)
from flask_wtf import CSRFProtect
from flask_talisman import Talisman

from megaqueue import config
from megaqueue.enums import DownloadStatus, FileStatus, MediaType, MetadataConfidence, MetadataSource
from megaqueue.models import db_session, init_db, Download, DownloadFile
from megaqueue.megabasterd_client import MegabasterdClient
from megaqueue.worker import start_worker

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
    """Accept one or more mega.nz links. Metadata is resolved later by guessit."""
    links_raw = request.form.get("links", "").strip()
    links = [l.strip() for l in links_raw.splitlines() if l.strip()]

    if not links:
        return redirect(url_for("index"))

    dl = Download(
        title=None, year=None, media_type=None,
        status=DownloadStatus.QUEUED,
        metadata_confidence=MetadataConfidence.LOW,
    )
    for link in links:
        dl.files.append(DownloadFile(url=link))

    db_session.add(dl)
    db_session.commit()
    log.info("Queued %d link(s) — worker will submit to megabasterd, metadata pending", len(links))

    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/resolve", methods=["POST"])
def resolve_download(download_id):
    """Accept user-supplied metadata for a needs_review download and unblock processing."""
    dl = db_session.get(Download, download_id)
    if dl is None or dl.status != DownloadStatus.NEEDS_REVIEW:
        return redirect(url_for("index"))

    title = request.form.get("title", "").strip()
    year_str = request.form.get("year", "").strip()
    media_type_str = request.form.get("media_type", "").strip()

    if not title or media_type_str not in (MediaType.MOVIE.value, MediaType.TV.value):
        return redirect(url_for("download_detail", download_id=download_id))

    dl.title = title
    dl.year = int(year_str) if year_str else None
    dl.media_type = MediaType(media_type_str)
    dl.metadata_source = MetadataSource.USER
    dl.metadata_confidence = MetadataConfidence.HIGH

    # Per-file is_extra overrides: form posts a list of file IDs that should be extras.
    extra_ids = set()
    for v in request.form.getlist("is_extra"):
        try:
            extra_ids.add(int(v))
        except ValueError:
            pass
    for df in dl.leaf_files:
        df.is_extra = df.id in extra_ids

    # Flip back to DOWNLOADING; the next worker tick will re-derive — either
    # PROCESSING (if every file is finished, post_process runs inline) or
    # DOWNLOADING (if files are still in flight). Setting PROCESSING here
    # would strand the download because the organiser is only run from the
    # worker thread.
    dl.status = DownloadStatus.DOWNLOADING
    db_session.commit()
    log.info("User resolved metadata for download %d (%s) — sync will continue", dl.id, dl.title)
    return redirect(url_for("download_detail", download_id=download_id))


@app.route("/download/<int:download_id>")
def download_detail(download_id):
    dl = db_session.get(Download, download_id)
    if dl is None:
        return redirect(url_for("index"))
    return render_template("detail.html", download=dl)


@app.route("/download/<int:download_id>/retry", methods=["POST"])
def retry_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl and dl.status in (DownloadStatus.FAILED, DownloadStatus.CANCELLED):
        dl.status = DownloadStatus.QUEUED
        dl.downloading_since = None
        dl.error_message = None
        for f in dl.files:
            f.status = FileStatus.QUEUED
            f.progress_bytes = 0
            f.total_bytes = 0
            f.speed = 0
            f.error_message = None
        db_session.commit()
    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/cancel", methods=["POST"])
def cancel_download(download_id):
    dl = db_session.get(Download, download_id)
    if dl and dl.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING):
        dl.status = DownloadStatus.CANCELLED
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

def create_app():
    """Initialize database and start worker, return app."""
    config.validate()
    init_db()
    start_worker()
    return app


