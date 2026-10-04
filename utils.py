import re
from functools import wraps

from flask import abort, g, redirect, request, url_for

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "Request body must be a JSON object.")
    return data


def as_int(value):
    """Return an int for ints or digit-only strings, otherwise None (bools rejected)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value)
    return None


# ---- API guards (respond with JSON errors) ----
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            abort(401, "Please log in to continue.")
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            abort(401, "Please log in to continue.")
        if g.user["role"] != "admin":
            abort(403, "Admin access required.")
        return view(*args, **kwargs)
    return wrapper


# ---- Page guards (redirect / HTML error pages) ----
def page_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("pages.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def page_admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("pages.login", next=request.path))
        if g.user["role"] != "admin":
            abort(403, "You need an admin account to view this page.")
        return view(*args, **kwargs)
    return wrapper
