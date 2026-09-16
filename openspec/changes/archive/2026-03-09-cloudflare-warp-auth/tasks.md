## 1. Remove Auth Code

- [x] 1.1 Delete `auth.py` module
- [x] 1.2 Delete `hashpw.py` utility script
- [x] 1.3 Delete `templates/login.html`
- [x] 1.4 Remove `/login` and `/logout` routes from `app.py`
- [x] 1.5 Remove `@login_required` decorator from all routes in `app.py`
- [x] 1.6 Remove login/logout links from `templates/base.html` navigation

## 2. Dependencies & Config

- [x] 2.1 Remove `bcrypt` from `requirements.txt`
- [x] 2.2 Remove `MEGAQUEUE_PASSWORD_HASH` from `config.py`
- [x] 2.3 Check if `flask-wtf` / `MEGAQUEUE_SECRET_KEY` are still needed (keep if add-download form uses CSRF, remove otherwise)

## 3. Documentation

- [x] 3.1 Rewrite README Cloudflare Tunnel section: add Zero Trust Access setup (create Access Application, configure WARP-only policy, enroll devices)
- [x] 3.2 Update README environment variables section: remove `MEGAQUEUE_PASSWORD_HASH`, update `MEGAQUEUE_SECRET_KEY` status
- [x] 3.3 Add instructions for granting a friend access (add their email to WARP enrollment policy)
