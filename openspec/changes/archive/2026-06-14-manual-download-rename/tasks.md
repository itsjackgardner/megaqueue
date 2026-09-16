## 1. Route: replace `/resolve` with `/rename`

- [x] 1.1 In `megaqueue/megaqueue/app.py`, rename the route from `/download/<id>/resolve` to `/download/<id>/rename` and the view function from `resolve_download` to `rename_download`.
- [x] 1.2 Relax the status guard: allow `queued`, `downloading`, `needs_review`. Reject all others (redirect to detail page).
- [x] 1.3 For `needs_review` downloads, keep the existing behaviour: set status to `DOWNLOADING` so the worker re-derives.
- [x] 1.4 For `queued`/`downloading` downloads, do not change the status — only write metadata fields.
- [x] 1.5 Ensure `metadata_source="user"` and `metadata_confidence="high"` are set in all cases.

## 2. Templates

- [x] 2.1 In `detail.html`, extract the resolve form into a reusable rename form block.
- [x] 2.2 Show the rename form (expanded with orange callout) when `status == needs_review` — same visual as today, but POST target changes to `/rename`.
- [x] 2.3 Show the rename form (collapsed behind an "Edit details" button) when `status in (queued, downloading)`. Use a `<details>` element with JS toggle.
- [x] 2.4 Hide the rename form for `processing`, `complete`, `failed`, `cancelled`.
- [x] 2.5 In `index.html`, add a small edit icon/link on dashboard cards for active downloads (queued, downloading, needs_review) that links to the detail page.

## 3. Tests

- [x] 3.1 In `tests/test_routes.py`, update existing resolve tests to use the `/rename` URL.
- [x] 3.2 Add test: rename succeeds for a `downloading` download — metadata fields written, status unchanged.
- [x] 3.3 Add test: rename succeeds for a `queued` download — metadata fields written, status unchanged.
- [x] 3.4 Add test: rename for `needs_review` download — sets status to `DOWNLOADING`, writes metadata.
- [x] 3.5 Add test: rename rejected (redirect) for `complete`, `failed`, `cancelled` downloads.
- [x] 3.6 Add test: rename sets `metadata_source="user"` and `metadata_confidence="high"`.
- [x] 3.7 Verify old `/resolve` URL returns 404 (or at least doesn't match a route).

## 4. Specs

- [x] 4.1 Update `web-ui` spec: replace the resolve form requirement with a rename form requirement covering all active statuses.

## 5. Verify

- [x] 5.1 `cd megaqueue && pytest` — full suite passes (4 pre-existing Windows path-separator failures in test_organiser.py unrelated to this change).
- [ ] 5.2 Manual smoke: submit a download, wait for guessit to resolve title, open detail, click Edit details, change title, verify metadata_source flips to "user" and title persists across poll ticks.
