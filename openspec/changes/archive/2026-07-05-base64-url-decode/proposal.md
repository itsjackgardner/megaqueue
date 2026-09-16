## Why

Users sometimes receive mega.nz links that have been base64-encoded (or even double-encoded) — common in forums, paste sites, and link-protection services. Currently, pasting an encoded link into the add-download form results in a rejected or broken submission. The system should transparently decode these links so users can paste them directly without manual decoding.

## What Changes

- Add base64 URL decoding to the link submission pipeline — when a submitted line doesn't look like a mega.nz URL, attempt base64 decoding (and a second pass for double-encoding) to recover a valid mega.nz link
- The decoding happens server-side during form submission, before download creation
- Invalid lines that don't decode to mega.nz URLs are still rejected as before

## Capabilities

### New Capabilities
- `base64-url-decode`: Transparent decoding of base64-encoded (and double-encoded) mega.nz URLs during link submission

### Modified Capabilities
- `web-ui`: The add-download form accepts base64-encoded mega.nz links in addition to raw URLs

## Impact

- **Code**: `mega_urls.py` (new decode function), `app.py` (route handler applies decoding before creating downloads)
- **Tests**: New tests for the decode logic, updated route tests for encoded input
- **No breaking changes**: Raw mega.nz URLs continue to work exactly as before
