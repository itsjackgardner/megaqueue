## Context

Today's resolve flow: when a download lands in `needs_review` (low confidence metadata), the detail page shows an inline form to set title/year/media_type/extras. Submitting calls `POST /download/<id>/resolve`, which requires `status == needs_review`. Once metadata is confirmed, the download flips to `downloading` (so the worker can re-derive status) with `metadata_source="user"`, `metadata_confidence="high"`.

The user wants to rename/correct metadata at any point — even when guessit resolved confidently, or while a download is still in progress.

## Goals / Non-Goals

**Goals:**

- Edit title, year, media_type, and per-file is_extra on any download that hasn't completed post-processing (queued, downloading, needs_review).
- Setting metadata via rename marks it as `metadata_source="user"` so guessit won't overwrite it on subsequent poll ticks.
- For `needs_review` downloads, rename also unblocks processing (subsumes resolve).
- Simple, inline UX — an edit button that reveals the form, not a separate page.

**Non-Goals:**

- Re-organising already-completed downloads. The organiser moves files to their final Plex paths; re-organising would mean moving files around on disk. Out of scope for this change.
- Renaming from the dashboard directly (inline edit). The dashboard card links to the detail page; the rename form lives on detail.

## Decisions

### 1. Single `/rename` route replaces `/resolve`

The existing `/resolve` route's logic is a subset of what rename needs. Rather than having two routes with overlapping concerns, consolidate into `POST /download/<id>/rename`:

- Accepts `title`, `year`, `media_type`, per-file `is_extra` overrides — same fields as resolve.
- Status guard: allows `queued`, `downloading`, `needs_review`. Rejects `processing`, `complete`, `failed`, `cancelled` (processing is transient and should not be interrupted; terminal states have already completed or been abandoned).
- Sets `metadata_source="user"`, `metadata_confidence="high"`.
- For `needs_review` downloads: sets status to `downloading` so the worker re-derives (same as current resolve behaviour).
- For `queued`/`downloading` downloads: does not change status — the download keeps downloading, but the metadata is locked in.

The old `/resolve` endpoint is removed. The URL changes from `/download/<id>/resolve` to `/download/<id>/rename`. No backward compatibility needed — there are no external consumers.

### 2. Detail view rename form

The resolve form currently renders inside an orange `needs_review` callout. For rename, the form should be:

- Always available on `queued`, `downloading`, and `needs_review` detail pages.
- Collapsed behind an "Edit details" button for `queued`/`downloading` (not as prominent as the needs_review form, since the metadata is usually correct).
- Expanded by default for `needs_review` (same as today, but now posted to `/rename`).
- Hidden for `processing`, `complete`, `failed`, `cancelled`.

The form fields are identical to the current resolve form: title, year, media_type radio, per-file is_extra checkboxes (shown when media_type is movie or unset).

### 3. No schema or model changes

The existing columns (`metadata_source`, `metadata_confidence`) already support this feature. Setting `metadata_source="user"` prevents guessit from overwriting, and setting `metadata_confidence="high"` prevents the needs_review gate from re-triggering. No migrations needed.

### 4. Dashboard edit affordance

Each card on the dashboard index gets a small pencil/edit icon that links to the detail page. This is a visual hint that the download is editable, not a direct inline edit. Only shown for active statuses (queued, downloading, needs_review).

## Risks / Trade-offs

- **User renames during download, guessit already ran.** The rename sets `metadata_source="user"`, which the existing guard in `metadata.refresh()` respects — it will only update `is_extra` on new files, not overwrite title/year/media_type. No race condition.
- **User renames to wrong media_type while downloading.** The organiser uses the Download's media_type at processing time. If the user sets `movie` but files are actually TV episodes, the organiser will fail per-file (no S/E on a movie path). This is user error and the current resolve flow has the same risk.
- **Removing `/resolve` breaks bookmarks.** Unlikely — this is a single-user app accessed from a phone. The URL is never bookmarked.
