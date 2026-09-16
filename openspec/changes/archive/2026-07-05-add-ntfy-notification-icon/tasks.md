## 1. Config

- [x] 1.1 Add optional `NTFY_ICON_URL = _env("NTFY_ICON_URL")` to `megaqueue/megaqueue/config.py` (do not add to `_REQUIRED`).

## 2. Notification sending

- [x] 2.1 In `megaqueue/megaqueue/notifications.py`'s `_send()`, conditionally add `headers["Icon"] = config.NTFY_ICON_URL` when `config.NTFY_ICON_URL` is truthy.

## 3. Tests

- [x] 3.1 Add a test in `megaqueue/tests/test_notifications.py` that sets `config.NTFY_ICON_URL` (e.g. via `monkeypatch`) and asserts the outbound request includes the `Icon` header with the expected value, for at least one notification type.
- [x] 3.2 Add a test asserting no `Icon` header is present when `config.NTFY_ICON_URL` is unset (or confirm existing tests already cover this since they don't set the var).
- [x] 3.3 Run `pytest` from `megaqueue/` and confirm the full suite passes.

## 4. Manual verification (user, outside repo)

- [x] 4.1 Host the moviedog PNG on the user's public root-domain website.
- [x] 4.2 Set `MEGAQUEUE_NTFY_ICON_URL` in the deployment environment to that image's URL.
- [x] 4.3 Trigger a real notification and confirm the icon renders in the ntfy iOS app.
