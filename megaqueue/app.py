import logging

from flask import Flask, render_template, request, redirect, url_for, jsonify, Response

log = logging.getLogger(__name__)
from flask_wtf import CSRFProtect
from flask_talisman import Talisman

from megaqueue import config
from megaqueue.enums import DownloadStatus, FileStatus, MediaType, MetadataConfidence, MetadataSource
from megaqueue.models import db_session, init_db, Download, DownloadFile
from megaqueue.mega_urls import maybe_decode_base64
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
        "style-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com"],
        "connect-src": "'self'",
        "worker-src": "'self'",
        "font-src": ["https://fonts.gstatic.com"],
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
    links = [maybe_decode_base64(l.strip()) for l in links_raw.splitlines() if l.strip()]

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
    log.info("Queued %d link(s) — will submit to megabasterd", len(links))

    return redirect(url_for("index"))


@app.route("/download/<int:download_id>/rename", methods=["POST"])
def rename_download(download_id):
    """Accept user-supplied metadata for an active download."""
    ALLOWED = (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.NEEDS_REVIEW)
    dl = db_session.get(Download, download_id)
    if dl is None or dl.status not in ALLOWED:
        return redirect(url_for("download_detail", download_id=download_id))

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

    extra_ids = set()
    for v in request.form.getlist("is_extra"):
        try:
            extra_ids.add(int(v))
        except ValueError:
            pass
    for df in dl.leaf_files:
        df.is_extra = df.id in extra_ids

    if dl.status == DownloadStatus.NEEDS_REVIEW:
        dl.status = DownloadStatus.DOWNLOADING
    db_session.commit()
    log.info("User set metadata for '%s' — metadata_source=user", dl.title)
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

@app.route("/logs")
def logs_page():
    return render_template("logs.html")


@app.route("/api/logs")
def api_logs():
    limit = min(int(request.args.get("limit", 200)), 1000)
    from megaqueue.models import LogEntry
    entries = db_session.query(LogEntry).order_by(
        LogEntry.id.desc()
    ).limit(limit).all()
    return jsonify([
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "level": e.level,
            "module": e.module,
            "message": e.message,
        }
        for e in reversed(entries)
    ])


@app.route("/api/logs/stream")
def api_logs_stream():
    from megaqueue.log_handler import log_handler

    def generate():
        q = log_handler.subscribe()
        try:
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {event}\n\n"
                except Exception:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            log_handler.unsubscribe(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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

    from megaqueue.log_handler import log_handler
    mq_logger = logging.getLogger("megaqueue")
    mq_logger.addHandler(log_handler)
    mq_logger.setLevel(logging.DEBUG)

    start_worker()
    return app


