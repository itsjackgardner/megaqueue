## Context

When megabasterd receives a `mega.nz/folder/{id}#key` URL it splits it into individual per-file downloads. Each per-file entry has a distinct URL of the form `https://mega.nz/#N!{fileId}!{fileKey}###n={folderId}` — the `###n={folderId}` suffix encodes the source folder ID.

The worker's existing Tier 2 matching path reads a `sourceUrl` field from megabasterd's status response, but megabasterd does not return this field. The `###n=` suffix is the only signal in the response that links a per-file entry back to its parent folder.

The previous spec assumed a Java-side change (adding `sourceUrl` to megabasterd's REST API) as the fix. That change was never made. This design instead fixes the problem entirely on the Python side by parsing the `###n=` suffix.

## Goals / Non-Goals

**Goals:**
- Folder downloads correctly match all of their per-file megabasterd entries to the single `DownloadFile` record
- No changes required to the megabasterd Java fork
- Existing single-file and old-format URL matching is unaffected

**Non-Goals:**
- Adding `sourceUrl` to megabasterd's REST API
- Handling nested folders or complex folder structures beyond what megabasterd already flattens

## Decisions

### Decision: Tier 3 folder-ID matching instead of sourceUrl

Add a third tier to `_match_megabasterd_files()`:

1. **Tier 1** (unchanged): direct normalized URL match
2. **Tier 2** (keep, but it's effectively dead): `sourceUrl` field match
3. **Tier 3** (new): extract folder ID from `###n={folderId}` in the megabasterd entry URL; match against folder ID extracted from `mega.nz/folder/{id}` DownloadFile URLs

**Rationale:** The folder ID is already embedded in each per-file URL by megabasterd. Parsing it avoids any Java change and is a one-liner regex. Keeping Tier 2 costs nothing and would work if a future megabasterd version ever does return `sourceUrl`.

### Decision: Separate `_extract_folder_id()` helper

Extract the folder ID from a URL via two patterns:
- From a `###n={folderId}` suffix (megabasterd per-file URL)
- From a `mega.nz/folder/{id}#key` URL (DownloadFile stored URL)

Build a secondary lookup dict `file_by_folder_id: {folderId → DownloadFile}` during match setup, populated only for DownloadFiles whose URL contains `mega.nz/folder/`.

**Rationale:** Keeps the normalization logic isolated and testable. The secondary dict avoids O(n²) scanning.

## Risks / Trade-offs

- [Regex fragility] The `###n=` format is an undocumented megabasterd URL convention → Mitigation: pattern is already present in the existing `_normalize_mega_url` strip logic, confirming it's stable.
- [Tier 2 dead code] `sourceUrl` matching is never exercised → Mitigation: leave it in place as a no-cost forward-compatibility shim; document it.
