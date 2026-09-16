## Why

Once guessit resolves a download's metadata, there's no way to correct it unless the download happens to land in `needs_review` (low confidence). If guessit resolves confidently but *wrong* — e.g. pulling the wrong title from a scene-tagged filename, or classifying a movie as TV — the user has no recourse except deleting and re-submitting. Worse, there's no way to rename a download that's still actively downloading: you have to wait for it to finish, fail at organising, and then retry.

The user needs to be able to edit a download's title, year, and media_type at any point in its lifecycle — while it's queued, downloading, needs_review, or even after completion (for re-organising).

## What Changes

- **NEW**: `POST /download/<id>/rename` route accepts `title`, `year`, `media_type`, and per-file `is_extra` overrides. Works for any active download status (queued, downloading, needs_review, processing), not just `needs_review`. Sets `metadata_source="user"` and `metadata_confidence="high"` so guessit won't overwrite. For `needs_review` downloads, also unblocks processing (same as the existing resolve route).
- **MODIFIED**: Detail view gets an "Edit" button/section that expands the same title/year/type/extras form currently only shown for `needs_review`. Available on all downloads except `complete`, `failed`, and `cancelled`.
- **MODIFIED**: The existing `/resolve` route is removed — the new `/rename` route subsumes its functionality.
- **MODIFIED**: Dashboard download cards get a small edit/pencil affordance for quick access to the detail page rename.

## Capabilities

### Modified Capabilities

- `web-ui`: Detail view rename form available on all active statuses. Resolve form replaced by rename form. Dashboard cards link to rename.
- `data-model`: No schema changes — existing `metadata_source` and `metadata_confidence` columns are sufficient.
- `metadata-resolution`: No logic changes — the `metadata_source="user"` guard already prevents guessit from overwriting user values.

## Impact

- Code (megaqueue submodule):
  - `megaqueue/app.py` — new `/rename` route replacing `/resolve`; relaxed status guard.
  - `megaqueue/templates/detail.html` — rename form visible for active downloads, not just `needs_review`.
  - `megaqueue/templates/index.html` — small edit affordance on cards.
- Tests:
  - `tests/test_routes.py` — update resolve tests → rename tests; test rename works in queued/downloading/needs_review states; test rename rejected for complete/failed/cancelled.
- Specs: delta on `web-ui`.
