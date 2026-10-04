from flask import Blueprint, g, jsonify, session
import pymysql

from models import user as users
from utils import EMAIL_RE, json_body

bp = Blueprint("auth", __name__, url_prefix="/api")


@bp.post("/register")
def register():
    data = json_body()
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    errors = []
    if not 2 <= len(name) <= 100:
        errors.append("Name must be 2 to 100 characters.")
    if len(email) > 255 or not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        errors.append("Password must be 8 to 128 characters.")
    if errors:
        return jsonify(error=errors[0], errors=errors), 400

    if users.get_by_email(email):
        return jsonify(error="An account with this email already exists."), 409
    try:
        user_id = users.create(name, email, password)  # role is always 'user' here
    except pymysql.err.IntegrityError:  # two sign-ups at the same moment
        return jsonify(error="An account with this email already exists."), 409
    return jsonify(user=users.public(users.get_by_id(user_id))), 201


@bp.post("/login")
def login():
    data = json_body()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    user = users.get_by_email(email) if email else None
    if not user or not isinstance(password, str) or not users.check_password(user, password):
        return jsonify(error="Incorrect email or password."), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(user=users.public(user))


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out.")


@bp.get("/me")
def me():
    return jsonify(user=users.public(g.user))
