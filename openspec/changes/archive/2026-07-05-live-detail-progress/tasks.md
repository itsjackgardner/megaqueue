## 1. Template Changes

- [x] 1.1 Add `id="detail-card"`, `data-id`, and `data-status` attributes to the main card div in `detail.html`
- [x] 1.2 Add `id="overall-progress"` to the overall progress bar wrapper div
- [x] 1.3 Add `data-progress` to the overall progress stats div
- [x] 1.4 Add `data-file-id` to each per-file card div
- [x] 1.5 Add `data-file-progress` to each per-file progress stats div

## 2. Client-Side Polling

- [x] 2.1 Add polling logic to `static/detail.js` — fetch `/api/status` every 5 seconds, find current download by ID
- [x] 2.2 Update overall progress bar: width, byte counts, percentage, speed
- [x] 2.3 Update per-file progress bars: width, byte counts, percentage, speed
- [x] 2.4 Trigger `location.reload()` on status change or when progress bars need to appear for the first time
- [x] 2.5 Only activate polling when initial status is `downloading` or `queued`

## 3. Spec Updates

- [x] 3.1 Update `web-ui` spec with the new live detail progress requirement and scenarios
