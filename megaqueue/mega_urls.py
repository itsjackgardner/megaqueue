"""Pure helpers for mega.nz URLs. No DB, no IO, no side effects."""

import re


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
