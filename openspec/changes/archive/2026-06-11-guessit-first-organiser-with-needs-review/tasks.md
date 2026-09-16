## 0. Restructure (do first, keep tests green at each step)

- [x] 0.1 Create `megaqueue/megaqueue/enums.py` with `DownloadStatus(StrEnum)`, `FileStatus(StrEnum)`, `MediaType(StrEnum)`, `MetadataConfidence(StrEnum)`, `MetadataSource(StrEnum)`. Re-export from `models` for ergonomics.
- [x] 0.2 In `models.py`, change column types to `Enum(DownloadStatus, ...)` etc. Migrate string literals in `app.py`/`worker.py`/templates incrementally (use `DownloadStatus.QUEUED` instead of `"queued"`). Run pytest after each module migrated.
- [x] 0.3 Create `megaqueue/megaqueue/migrations.py` with a `MIGRATIONS = [(name, fn), ...]` list and `run_all(conn)` helper. Move the existing `parent_id` ALTER TABLE into `_add_parent_id_column`. Call `migrations.run_all` from `init_db()`. Verify on a clean DB and a legacy DB.
- [x] 0.4 Create `megaqueue/megaqueue/mega_urls.py`. Move `_normalize_mega_url`, `_extract_folder_id`, `_is_folder_url` (and the regexes they depend on) out of `worker.py`. Export without the leading underscore. Update imports in `worker.py` and tests.
- [x] 0.5 Create `megaqueue/megaqueue/sync.py`. Move `_match_megabasterd_files`, `_maybe_expand_folder_files`, `_update_file_from_megabasterd`, `_resolve_source_paths`, `_submit_pending_downloads`, `_sync_active_downloads`, `_integrity_sweep` out of `worker.py`. Keep names; update imports.
- [x] 0.6 Create `megaqueue/megaqueue/lifecycle.py`. Move `_derive_download_status` and `_post_process` out of `worker.py`. (After Section 4, this is also where the `needs_review` transition lives.)
- [x] 0.7 `megaqueue/megaqueue/worker.py` shrinks to: `start_worker`, `_worker_loop`, `_poll_once`. `_poll_once` calls `sync.submit_pending`, `sync.sync_active`, `sync.integrity_sweep` in order.
- [x] 0.8 Split `tests/test_worker.py` into `test_mega_urls.py`, `test_sync.py`, `test_lifecycle.py`, and a residual `test_worker.py` (poll loop). Pytest must remain green after the split.

## 1. Dependencies

- [x] 1.1 Add `guessit`, `rarfile`, `py7zr` to `megaqueue/requirements.txt`.
- [x] 1.2 Confirm `unrar` is installed on the NUC; document in `scripts/` if not. Remove FileBot install step from `scripts/`.

## 2. Data model

- [x] 2.1 In `models.py`, make `Download.title` nullable, make `Download.media_type` nullable.
- [x] 2.2 Add `NEEDS_REVIEW` to `DownloadStatus` (in `enums.py`) and the SQLAlchemy column type.
- [x] 2.3 Add `Download.metadata_confidence` (`Enum(MetadataConfidence)`, default `LOW`) and `Download.metadata_source` (nullable `Enum(MetadataSource)`).
- [x] 2.4 Add `DownloadFile.is_extra` (Boolean, default False).
- [x] 2.5 In `migrations.py`, register `_add_metadata_columns` (downloads.metadata_confidence default `'high'` for legacy rows, downloads.metadata_source) and `_add_is_extra_column` (download_files.is_extra default 0).
- [x] 2.6 In `migrations.py`, register `_widen_status_enum` using the SQLite table-rebuild pattern if the CHECK constraint blocks `needs_review`; otherwise no-op.

## 3. Metadata resolution module

- [x] 3.1 Create `megaqueue/megaqueue/metadata.py`.
- [x] 3.2 Implement `parse_filename(name) -> dict` that wraps `guessit.guessit` and normalises returned `MatchesDict` to a plain dict with known keys.
- [x] 3.3 Implement `refresh(download)` that:
  - reads every leaf `DownloadFile` with a populated `name`,
  - runs `parse_filename` on each,
  - if `metadata_source == "user"`, only updates `is_extra` on files; otherwise aggregates `title`/`year`/`media_type` and writes them.
- [x] 3.4 Implement `_aggregate_movie(parsed_per_file, leaf_files)` that picks the main feature by (year AND any of screen_size/source/video_codec) with largest-bytes tiebreak, returns `(title, year, main_feature_id)`, and sets `is_extra` on the rest.
- [x] 3.5 Implement `_aggregate_tv(parsed_per_file, leaf_files)` that votes on title, returns `(title, season_hint)`. All files keep `is_extra=False`.
- [x] 3.6 Implement `_score_confidence(download, parsed_per_file)` returning `"high"` or `"low"` per the rules in `metadata-resolution/spec.md`.

## 4. Sync + lifecycle integration

- [x] 4.1 In `sync.py`, after `_update_file_from_megabasterd` sets `df.name`, call `metadata.refresh(download)` for the parent Download.
- [x] 4.2 Extend `lifecycle._derive_download_status` per the new `data-model` rule: all-finished + low confidence → `DownloadStatus.NEEDS_REVIEW`; all-finished + high → `DownloadStatus.PROCESSING`.
- [x] 4.3 In `lifecycle`, when a Download transitions to `NEEDS_REVIEW`, call `notify_needs_review(download)` and skip post-processing.
- [x] 4.4 Ensure `sync.sync_active` does not re-process Downloads already in `NEEDS_REVIEW` (filter them out of the active query, or short-circuit early).

## 5. Organiser

- [x] 5.1 Create `megaqueue/megaqueue/organiser.py` (replacing `filebot_organizer.py`).
- [x] 5.2 Implement archive detection + per-format extractor dispatch (`rarfile`/`zipfile`/`py7zr`).
- [x] 5.3 Implement `_route_movie_main(file_path, download)` → `<PLEX_MOVIES_DIR>/<Title> (<Year>)/<Title> (<Year>).<ext>` (year-less fallback per spec).
- [x] 5.4 Implement `_route_movie_extra(file_path, download)` → `<PLEX_MOVIES_DIR>/<Title> (<Year>)/Featurettes/<original-name>`.
- [x] 5.5 Implement `_route_tv(file_path, download_file)` → `<PLEX_TV_DIR>/<Title>/Season <NN>/<Title> - S<NN>E<NN>.<ext>`. Pull season/episode from per-file guessit, not from the Download.
- [x] 5.6 Implement `organize_download(download, source_paths)` orchestrating extract → route → move → return final paths. Per-file failure (e.g., no S/E on a TV file) sets that file's `status="failed"` and `error_message` but does not abort the whole Download.
- [x] 5.7 Delete `megaqueue/megaqueue/filebot_organizer.py`.
- [x] 5.8 Update `lifecycle._post_process` to import from `megaqueue.organiser`.

## 6. Routes

- [x] 6.1 In `megaqueue/megaqueue/app.py`, change the submit route to accept only `links` (textarea). Create `Download(title=None, media_type=None, year=None, metadata_confidence='low')` and one `DownloadFile` per link.
- [x] 6.2 Add `POST /download/<id>/resolve` that accepts `title`, `year`, `media_type`, and a list of `is_extra:<file_id>` toggles. Writes values, sets `metadata_source='user'`, `metadata_confidence='high'`, status → `'processing'`. Reject if Download is not in `needs_review`.
- [x] 6.3 Update `/api/status` to include `metadata_confidence`, `metadata_source`, and per-file `is_extra` in the JSON output.

## 7. Templates

- [x] 7.1 Update `templates/add.html` (or wherever the submit form lives) to a single links textarea.
- [x] 7.2 Update `templates/index.html` dashboard cards: render "Resolving…" when `title is None`; add a "Review" badge for `needs_review` status.
- [x] 7.3 Update `templates/detail.html` to render the resolve form when `download.status == 'needs_review'`. Fields: title, year, media_type radio, per-file `is_extra` checkboxes.
- [x] 7.4 Ensure CSRF tokens are present in the resolve form.

## 8. Notifications

- [x] 8.1 Add `notify_needs_review(download)` to `megaqueue/megaqueue/notifications.py`. Compose the body with the reason strings from `metadata.refresh` (return them or derive from confidence inputs).
- [x] 8.2 Wrap the ntfy POST in the same try/except pattern as the existing helpers so failure logs but does not block.

## 9. Tests

- [x] 9.1 Create `tests/test_metadata.py`: parse_filename for movie, episode, bare extra; aggregate_movie with Birth-like input; aggregate_tv with Gen-V-like input; score_confidence high/low cases.
- [x] 9.2 Create `tests/test_organiser.py`: movie main feature path, movie extra path, TV episode path, no-year fallback, no-S/E per-file failure; archive extraction via mocked `rarfile`/`zipfile`/`py7zr`.
- [x] 9.3 Update `tests/test_sync.py` (created in Section 0): guessit refresh runs on name population; integrity sweep behaviour preserved.
- [x] 9.4 Update `tests/test_lifecycle.py` (created in Section 0): needs_review transition on low confidence; processing transition on high confidence; resolve flips `NEEDS_REVIEW` → `PROCESSING`.
- [x] 9.5 Update `tests/test_routes.py`: submit accepts links only; resolve route writes user values; resolve rejects non-`NEEDS_REVIEW` Downloads.
- [x] 9.6 Update `tests/test_models.py`: new columns persist; status enum accepts `NEEDS_REVIEW`; legacy rows get `metadata_confidence=HIGH` via migration.
- [x] 9.7 Create `tests/test_migrations.py`: each registered migration runs idempotently against an empty DB and a "legacy" DB.
- [x] 9.8 Update `tests/test_notifications.py`: needs_review notification body includes reason.
- [x] 9.9 Delete `tests/test_filebot_organizer.py`.

## 10. Cleanup

- [x] 10.1 Remove `MEGAQUEUE_FILEBOT_BIN` from `megaqueue/megaqueue/config.py`.
- [x] 10.2 Remove the FileBot startup probe from `megaqueue/megaqueue/app.py`.
- [x] 10.3 Remove FileBot-related lines from `megaqueue/CLAUDE.md` and `CLAUDE.md` (parent).
- [x] 10.4 Remove FileBot install/setup from `scripts/`.

## 11. Verify

- [x] 11.1 `cd megaqueue && source .venv/bin/activate && pytest` — full suite passes.
- [ ] 11.2 Manual smoke (locally or NUC): submit a real mega.nz link, watch the dashboard fill in title; force a low-confidence case (an untitled file) and verify needs_review + ntfy push + resolve form.
- [x] 11.3 Bump submodule pointer in parent repo. Confirm rollback path: revert that one commit on the parent.
