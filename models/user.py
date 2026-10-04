from werkzeug.security import check_password_hash, generate_password_hash

from db import execute, query


def get_by_id(user_id):
    return query("SELECT * FROM users WHERE id = %s", (user_id,), one=True)


def get_by_email(email):
    return query("SELECT * FROM users WHERE email = %s", (email,), one=True)


def create(name, email, password, role="user"):
    user_id, _ = execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        (name, email, generate_password_hash(password), role),
    )
    return user_id


def set_role(user_id, role):
    execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))


def check_password(user, password):
    return check_password_hash(user["password_hash"], password)


def public(user):
    """The only user fields that are ever sent to the browser."""
    if not user:
        return None
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
