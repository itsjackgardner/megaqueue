## Context

Megabasterd's `/start` endpoint resolves mega.nz folder links synchronously — it opens a `FolderLinkDialog`, waits for the Mega API to enumerate all files, then creates `Download` objects. For large folders this blocks for minutes, causing HTTP timeouts in megaqueue.

The current megaqueue codebase has layered workarounds: the Flask route saves to DB without calling megabasterd, a background worker thread (`_do_submit`/`_submitting_ids`) submits asynchronously, and the integrity sweep has a grace period to avoid false-failing downloads that haven't appeared in megabasterd yet. These workarounds are fragile — the integrity sweep still races with slow submissions, and the worker blocks its polling loop if the submission thread hasn't finished.

The megabasterd API also lacks `sourceUrl` on `/status` entries, forcing megaqueue to use a three-tier URL matching strategy with folder-ID extraction as a fallback (Tier 3), which is brittle.

## Goals / Non-Goals

**Goals:**
- `/start` returns immediately (<1s) regardless of link type or folder size
- megaqueue can track pending submissions via `/status` without special-case logic
- Folder-split downloads are traceable to their source URL via `sourceUrl` field
- Remove background submission thread machinery from megaqueue worker
- Integrity sweep correctly handles the submission lifecycle

**Non-Goals:**
- Changing the mega.nz link resolution logic itself (FolderLinkDialog stays)
- Adding job/task tracking IDs for submissions (overkill for single-user system)
- Modifying the `/stop`, `/pause`, `/resume`, or `/rename` endpoints
- Changing how megaqueue routes handle cancellation (still direct to megabasterd)

## Decisions

### 1. Megabasterd `/start` queues URLs and returns immediately

The `/start` handler will add raw URLs to a thread-safe pending queue and return `{"message": "N links queued", "urls": [...]}` immediately. A background thread processes the queue: resolving folder links, creating `Download` objects, and adding them to the download manager.

**Alternative considered**: Have megaqueue submit one URL at a time to avoid long-running requests. Rejected because folder URL resolution is the bottleneck and can't be split — megabasterd needs the folder URL to enumerate its contents.

### 2. `/status` includes pending entries

The `/status` response will include entries from the pending queue with `status: "Pending"` and `finished: false`. This lets megaqueue distinguish "submitted but not yet resolving" from "disappeared." Once the background thread resolves and starts a pending URL, it transitions from pending to the normal download lifecycle.

### 3. `/status` includes `sourceUrl` on folder-split entries

When megabasterd creates per-file downloads from a folder URL, each download's `/status` entry will include `sourceUrl` set to the original folder URL. This enables direct Tier 2 matching in megaqueue without folder-ID extraction.

**Implementation**: Store the source URL on the `Download` object at creation time. For non-folder downloads, `sourceUrl` is omitted (or null).

### 4. Megaqueue worker removes submission thread, uses `/status` pending entries

The worker drops `_submitting_ids`, `_do_submit`, and the background submission thread. Instead:
- Routes save downloads as `queued` with `downloading_since=None` (already done)
- Worker calls `client.start()` synchronously (fast now — async API)
- Worker stamps `downloading_since` after successful start
- `/status` pending entries prevent integrity sweep false-failures

### 5. Integrity sweep skips downloads with `downloading_since=None`

Downloads that haven't been submitted yet (`downloading_since is None`) are excluded from the integrity sweep entirely. This is simpler than the current grace period workaround for unsubmitted downloads.

## Risks / Trade-offs

- **Pending queue is in-memory**: If megabasterd crashes after `/start` returns but before processing the queue, the URLs are lost. Megaqueue will detect this (files never appear in `/status`) and the integrity sweep will fail them after the grace period. User can retry. → Acceptable for a single-user self-hosted system.

- **Race between pending and resolved entries**: A URL might briefly appear as both "Pending" and as a started download during the transition. → Megaqueue's matching handles this: pending entries match by URL, and once resolved, the real download entries take over.

- **`sourceUrl` requires storing extra state in megabasterd**: Each `Download` object needs a new field. → Minimal change; `Download` class already has URL, path, and other metadata fields.

- **Backward compatibility during rollout**: If megaqueue is updated before megabasterd, the old synchronous `/start` still works (just slow). If megabasterd is updated first, the old megaqueue won't see pending entries but won't break. → Deploy megabasterd first, then megaqueue.
