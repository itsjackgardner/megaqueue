import logging

import requests

from megaqueue import config

log = logging.getLogger(__name__)


def _send(title, message, priority="default"):
    """Send a push notification via ntfy.sh."""
    url = f"{config.NTFY_SERVER}/{config.NTFY_TOPIC}"
    try:
        requests.post(
            url,
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
        log.info("Push notification sent: %s — %s", title, message)
    except Exception as e:
        log.error("Failed to send notification: %s", e)


def notify_completion(download):
    """Send notification when a download completes."""
    title_str = download.title
    if download.year:
        title_str = f"{download.title} ({download.year})"

    _send("Download Complete", f"{title_str} is ready in Plex")


def notify_failure(download):
    """Send notification when a download fails."""
    title_str = download.title
    if download.year:
        title_str = f"{download.title} ({download.year})"

    reason = download.error_message or "Unknown error"
    _send("Download Failed", f"{title_str} — {reason}", priority="high")


def notify_needs_review(download):
    """Send notification when a download finishes but metadata needs user review."""
    title_str = download.title or "(unresolved)"
    if download.year:
        title_str = f"{title_str} ({download.year})"

    reasons = _needs_review_reasons(download)
    body = f"{title_str} — {', '.join(reasons)}" if reasons else title_str
    _send("Review needed", body, priority="default")


def _needs_review_reasons(download):
    """Compose human-readable reasons for why this download needs review."""
    reasons = []
    if download.title is None:
        reasons.append("no title detected")
    if download.media_type is None:
        reasons.append("mixed or unknown file types")
    elif download.media_type == "movie" and download.year is None:
        reasons.append("no year detected")
    return reasons
