## 1. Core Decode Function

- [x] 1.1 Add `maybe_decode_base64(text)` function to `megaqueue/mega_urls.py` — try standard base64, then URL-safe base64, up to two rounds, returning decoded mega.nz URL or original text
- [x] 1.2 Add unit tests for `maybe_decode_base64` in `tests/test_mega_urls.py` covering: passthrough of raw URLs, single-encoded, double-encoded, URL-safe variant, missing padding, non-mega decode, non-decodable input, old-format and folder URLs

## 2. Route Integration

- [x] 2.1 Update `add_download()` in `app.py` to call `maybe_decode_base64()` on each line before creating `DownloadFile` records
- [x] 2.2 Add route tests in `tests/test_routes.py` for submitting base64-encoded and double-encoded links via the add-download form

## 3. Verification

- [x] 3.1 Run the full test suite and confirm all tests pass
