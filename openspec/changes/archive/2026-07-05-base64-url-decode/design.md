## Context

Users sometimes encounter mega.nz links that have been base64-encoded — common on forums, paste sites, and link-protection services. Some links are even double-encoded. Currently the add-download form takes each line verbatim as a URL and stores it directly as a `DownloadFile.url`. Lines that aren't valid mega.nz URLs simply fail downstream when megabasterd tries to download them.

The existing URL handling in `mega_urls.py` deals with normalization and folder-ID extraction but has no concept of decoding encoded input. The route handler in `app.py` (`add_download`) splits lines and stores them without any pre-processing.

## Goals / Non-Goals

**Goals:**
- Transparently decode base64-encoded mega.nz URLs (single and double-encoded) at submission time
- Keep the decode logic pure and testable in `mega_urls.py`
- Maintain backward compatibility — raw mega.nz URLs work exactly as before

**Non-Goals:**
- Supporting other encoding schemes (URL-encoded, hex, etc.)
- Client-side decoding or JavaScript-based preview of decoded URLs
- Decoding links from other services (only mega.nz)

## Decisions

### 1. Decode server-side in the route handler, not in the worker

**Decision**: Apply decoding at form submission time in `add_download()`, before creating `DownloadFile` records.

**Rationale**: Storing the decoded URL means the rest of the pipeline (worker, sync, matching) works unchanged. If we stored encoded URLs and decoded later, every component that reads `DownloadFile.url` would need to handle encoding — fragile and unnecessary.

**Alternative considered**: Decode in the worker on first sync. Rejected because it complicates matching logic and means the user sees encoded gibberish in the UI until the worker runs.

### 2. Put decode logic in `mega_urls.py` as a pure function

**Decision**: Add a `maybe_decode_base64(text) -> str` function in `mega_urls.py` that attempts to base64-decode the input and returns a mega.nz URL if found, otherwise returns the original text.

**Rationale**: Keeps the function pure, testable, and co-located with other URL helpers. The route handler calls it per-line before creating `DownloadFile` records.

### 3. Try up to two rounds of decoding

**Decision**: Attempt base64 decode once. If the result still doesn't look like a mega.nz URL, try decoding once more (for double-encoded input). Stop after two rounds.

**Rationale**: Double-encoding is the known real-world case. Deeper nesting is theoretically possible but not seen in practice and risks false positives or decoding random data into something that coincidentally matches.

### 4. Use standard base64 with URL-safe fallback

**Decision**: Try standard base64 decoding first, then URL-safe base64 (`-_` instead of `+/`), with padding tolerance (accept missing `=` padding).

**Rationale**: Both variants appear in the wild. Python's `base64.b64decode` and `base64.urlsafe_b64decode` with `validate=False` handle padding gracefully.

## Risks / Trade-offs

- **False positive decoding** — A random string could theoretically base64-decode to something containing "mega.nz". Mitigated by requiring the decoded result to match a known mega.nz URL pattern (file or folder), not just contain the substring.
- **Non-UTF-8 decode results** — Base64 decoding of arbitrary input may produce bytes that aren't valid UTF-8. Mitigated by catching `UnicodeDecodeError` and treating it as "not a base64 URL".
