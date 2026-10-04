"""Create an admin account (or promote an existing user to admin).

Usage:
    python create_admin.py --name "Store Admin" --email admin@example.com
    (you will be asked for the password; it is never stored in plain text)
"""
import argparse
import getpass
import sys

from app import app
from models import user as users
from utils import EMAIL_RE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="optional; omit to be prompted securely")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not EMAIL_RE.match(email):
        sys.exit("That email address is not valid.")

    with app.app_context():
        existing = users.get_by_email(email)
        if existing:
            users.set_role(existing["id"], "admin")
            print(f"{email} already existed and is now an admin.")
            return
        password = args.password or getpass.getpass("Admin password (min 8 characters): ")
        if len(password) < 8:
            sys.exit("Password must be at least 8 characters.")
        users.create(args.name.strip() or "Admin", email, password, role="admin")
        print(f"Admin account created for {email}.")


if __name__ == "__main__":
    main()
