from functools import wraps

import bcrypt
from flask import session, redirect, url_for, request

import config


def check_password(password):
    """Verify a plaintext password against the stored bcrypt hash."""
    return bcrypt.checkpw(
        password.encode("utf-8"),
        config.PASSWORD_HASH.encode("utf-8"),
    )


def login_required(f):
    """Decorator that redirects unauthenticated requests to /login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated
