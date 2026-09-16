## 1. Megabasterd: Async /start endpoint

- [x] 1.1 Add a thread-safe pending queue (e.g., `ConcurrentLinkedQueue<String>`) to `RemoteAPI` for raw URLs awaiting resolution
- [x] 1.2 Refactor `/start` handler to add URLs to the pending queue and return immediately with `{"message": "N links queued", "urls": [...]}`
- [x] 1.3 Create a background thread in `RemoteAPI` that processes the pending queue: resolves folder links (via `FolderLinkDialog`/`GENERATE_N_LINKS`), creates `Download` objects, and adds them to the download manager
- [x] 1.4 Store `sourceUrl` on `Download` objects created from folder splits (the original folder URL)

## 2. Megabasterd: /status enhancements

- [x] 2.1 Include pending queue entries in `/status` response with `status: "Pending"`, `finished: false`, `bytesLoaded: 0`, `bytesTotal: 0`, `speed: 0`, and the original URL
- [x] 2.2 Add `sourceUrl` field to each download entry in `/status` (non-null for folder-split downloads, null/omitted for single-file)
- [x] 2.3 Remove pending entry from the queue once its downloads are created and added to the download manager

## 3. Megaqueue: Simplify worker submission

- [x] 3.1 Replace `_do_submit`/`_submitting_ids` background thread with synchronous `client.start()` call in `_submit_pending_downloads` (safe now that `/start` is async)
- [x] 3.2 Reduce `megabasterd_client.py` start timeout back to 10s (async endpoint returns fast)
- [x] 3.3 Update `_submit_pending_downloads` to stamp `downloading_since` on success, mark failed on error

## 4. Megaqueue: Worker matching improvements

- [x] 4.1 Update `_match_megabasterd_files` to use `sourceUrl` field for Tier 2 matching (normalize and look up against `DownloadFile` URLs)
- [x] 4.2 Keep Tier 3 folder-ID matching as fallback for backward compatibility
- [x] 4.3 Handle `status: "Pending"` entries: match to `DownloadFile` records, keep status as "queued", count as matched for integrity sweep

## 5. Megaqueue: Integrity sweep fix

- [x] 5.1 Exclude downloads with `downloading_since=None` from the integrity sweep in `_integrity_sweep`

## 6. Tests

- [x] 6.1 Add worker test: `_submit_pending_downloads` calls `client.start()` and stamps `downloading_since`
- [x] 6.2 Add worker test: submission failure marks download as failed
- [x] 6.3 Add worker test: pending megabasterd entry matches `DownloadFile` and prevents integrity sweep failure
- [x] 6.4 Add worker test: `sourceUrl` matching for folder-split entries
- [x] 6.5 Add worker test: integrity sweep skips downloads with `downloading_since=None`
- [x] 6.6 Update existing tests that mock `_submitting_ids` or background submission thread
