import logging

import requests

import config

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
