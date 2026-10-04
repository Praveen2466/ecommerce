"""Tiny MySQL helper: one connection per request, plain SQL with %s placeholders."""
from datetime import date, datetime
from decimal import Decimal

import pymysql
import pymysql.cursors
from flask import current_app, g


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()  # uncommitted work is rolled back


def clean(row):
    """Make a DB row JSON-friendly (Decimal -> float, datetime -> string)."""
    if row is None:
        return None
    out = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, (datetime, date)):
            value = value.strftime("%Y-%m-%d %H:%M")
        out[key] = value
    return out


def query(sql, args=(), one=False):
    cur = get_db().cursor()
    try:
        cur.execute(sql, args)
        if one:
            return clean(cur.fetchone())
        return [clean(r) for r in cur.fetchall()]
    finally:
        cur.close()


def execute(sql, args=()):
    """Run INSERT/UPDATE/DELETE and commit. Returns (lastrowid, rowcount)."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, args)
        conn.commit()
        return cur.lastrowid, cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
