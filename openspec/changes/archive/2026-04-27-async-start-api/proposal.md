## Why

Megabasterd's `/start` endpoint blocks while resolving mega.nz folder links (opening `FolderLinkDialog`, iterating files), which can take minutes for large folders. This causes HTTP timeouts that cascade into failed downloads in megaqueue. The current workarounds (longer timeouts, background threads in the worker) add complexity without fixing the root cause. Additionally, the worker's integrity sweep falsely fails downloads that are still being submitted because it can't distinguish "not yet submitted" from "disappeared."

## What Changes

- **Async `/start` in megabasterd**: The `/start` endpoint returns immediately with an acknowledgment. Link resolution and download creation happen asynchronously in a background thread. A new `pending` status in `/status` allows megaqueue to track submissions in progress.
- **`sourceUrl` field on `/status` entries**: When megabasterd splits a folder URL into per-file downloads, each entry includes the original folder URL as `sourceUrl`. This replaces the fragile folder-ID extraction matching (Tier 3) with a direct lookup (Tier 2).
- **Resolved links returned in `/status`**: Pending entries in `/status` include the original URL so megaqueue can correlate them before downloads start.
- **Simplify megaqueue worker submission**: Remove the background submission thread (`_submitting_ids`, `_do_submit`) and the integrity sweep grace period workaround. The worker saves downloads as queued; the async `/start` handles the rest. The worker matches pending/active entries from `/status` naturally.
- **Worker skips integrity sweep for unsubmitted downloads**: Downloads with `downloading_since=None` are excluded from the integrity sweep, preventing false failures during the submission window.

## Capabilities

### New Capabilities

_(none — all changes modify existing capabilities)_

### Modified Capabilities

- `download-engine`: Worker submission moves from synchronous route/background-thread to async megabasterd API; integrity sweep excludes unsubmitted downloads; Tier 2 matching becomes primary for folder splits via new `sourceUrl` field

## Impact

- **megabasterd RemoteAPI.java**: `/start` endpoint refactored to async; `/status` adds `sourceUrl` and `pending` entries
- **megaqueue worker.py**: Remove `_submitting_ids`/`_do_submit` thread machinery; update `_match_megabasterd_files` to use `sourceUrl`; update `_integrity_sweep` to skip unsubmitted downloads
- **megaqueue megabasterd_client.py**: Start timeout can be reduced back to normal (async returns fast)
- **megaqueue app.py**: No changes needed (routes already save-and-return)
- **Backward compatibility**: megaqueue worker must handle both old (no `sourceUrl`) and new `/status` responses during rollout
