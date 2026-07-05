"""Pure helpers for mega.nz URLs. No DB, no IO, no side effects."""

import base64
import re

_MEGA_URL_RE = re.compile(r"https?://mega\.nz/")


def maybe_decode_base64(text):
    """Try to base64-decode text into a mega.nz URL (up to two rounds for double-encoding)."""
    text = text.strip()
    if _MEGA_URL_RE.match(text):
        return text

    decoded = text
    for _ in range(2):
        decoded = _try_b64_decode(decoded)
        if decoded is None:
            return text
        if _MEGA_URL_RE.match(decoded):
            return decoded
    return text


def _try_b64_decode(s):
    padded = s + "=" * (-len(s) % 4)
    for decode_fn in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            return decode_fn(padded).decode("utf-8")
        except Exception:
            continue
    return None


def normalize(url):
    """Extract (id, key) from either mega.nz URL format for comparison.

    Old format: https://mega.nz/#!{id}!{key}
    New format: https://mega.nz/file/{id}#{key}
    Folder file: https://mega.nz/#N!{id}!{key}###n={folderId}
    """
    url = re.sub(r"###n=.+$", "", url)
    m = re.match(r"https?://mega\.nz/#[!N]?!?([^!]+)!(.+)", url)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    m = re.match(r"https?://mega\.nz/file/([^#]+)#(.+)", url)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    return url


def extract_folder_id(url):
    """Extract the mega.nz folder ID from a URL.

    Handles three patterns:
    - New folder URL: https://mega.nz/folder/{folderId}#key  -> folderId
    - Old folder URL: https://mega.nz/#F!{folderId}!{key}    -> folderId
    - Per-file URL with suffix: ...###n={folderId}            -> folderId

    Returns None if no pattern matches.
    """
    m = re.search(r"###n=([^#&]+)", url)
    if m:
        return m.group(1)
    m = re.match(r"https?://mega\.nz/folder/([^#?/]+)", url)
    if m:
        return m.group(1)
    m = re.match(r"https?://mega\.nz/#F!([^!]+)!", url)
    if m:
        return m.group(1)
    return None


def is_folder_url(url):
    """Return True if the URL is a mega.nz folder URL (new or old format)."""
    return "mega.nz/folder/" in url or bool(re.match(r"https?://mega\.nz/#F!", url))
