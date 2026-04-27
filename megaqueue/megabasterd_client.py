import logging

import requests

from megaqueue import config

log = logging.getLogger(__name__)


class MegabasterdClient:
    """HTTP client wrapper for the megabasterd REST API."""

    def __init__(self, base_url=None, timeout=10):
        self.base_url = (base_url or config.MEGABASTERD_API_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self.session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            log.error("Megabasterd API unreachable at %s", self.base_url)
            raise
        except requests.HTTPError as e:
            log.error("Megabasterd API error: %s %s -> %s", method, path, e)
            raise
        except requests.JSONDecodeError:
            return resp.text

    def status(self):
        """GET /status — returns system status and all downloads."""
        return self._request("GET", "/status")

    def start(self, urls, dest=None):
        """POST /start — queue new downloads.

        Args:
            urls: Newline-separated mega.nz URLs string, or list of URLs.
            dest: Optional subfolder under megabasterd's default download path.
        """
        if isinstance(urls, list):
            urls = "\n".join(urls)
        body = {"urls": urls}
        if dest:
            body["dest"] = dest
        return self._request("POST", "/start", json=body)

    def stop(self, url, delete=True):
        """POST /stop — stop a download by its mega.nz URL."""
        return self._request("POST", "/stop", json={"url": url, "delete": delete})

    def pause(self):
        """POST /pause — pause all downloads."""
        return self._request("POST", "/pause")

    def resume(self):
        """POST /resume — resume all downloads."""
        return self._request("POST", "/resume")

    def clear509(self):
        """POST /clear509 — clear 509 bandwidth limit errors."""
        return self._request("POST", "/clear509")

    def rename(self, url, new_name):
        """POST /rename — rename a completed download's file."""
        return self._request("POST", "/rename", json={"url": url, "newName": new_name})

    def is_reachable(self):
        """Check if the megabasterd API is reachable."""
        try:
            self.status()
            return True
        except Exception:
            return False
