"""Create the database and tables from schema.sql.

Usage:
    python init_db.py           # create database + tables
    python init_db.py --seed    # ...and add sample products (only if the table is empty)
"""
import argparse
import re
from pathlib import Path

import pymysql

from config import Config

SAMPLE_PRODUCTS = [
    ("Linen Throw Blanket", "Stonewashed linen, soft after one wash. 130 x 170 cm.", 59.00, "Home", 25),
    ("Beeswax Taper Candles (6)", "Hand-dipped, about 8 hours of burn time each.", 18.50, "Home", 60),
    ("Glazed Stoneware Mug", "350 ml, dishwasher safe, each one slightly different.", 14.00, "Kitchen", 80),
    ("Ceramic Pour-Over Set", "Dripper and carafe for two cups of filter coffee.", 42.00, "Kitchen", 18),
    ("Oak Cutting Board", "Solid oak with a juice groove. Oiled, ready to use.", 36.00, "Kitchen", 30),
    ("Cast Iron Skillet 26 cm", "Pre-seasoned and oven safe. Lasts decades.", 48.00, "Kitchen", 12),
    ("Dot-Grid Notebook", "A5, 160 pages of 100 gsm paper that takes fountain pen.", 12.00, "Stationery", 120),
    ("Brass Mechanical Pencil", "0.5 mm lead, weighted brass body.", 24.00, "Stationery", 40),
    ("Walnut Desk Tray", "Holds pens, cards and the small things that wander.", 29.00, "Stationery", 22),
    ("Braided Charging Cable 2 m", "USB-C to USB-C, 100 W, braided nylon.", 16.00, "Tech", 150),
    ("Aluminium Laptop Stand", "Folds flat, raises your screen to eye level.", 39.00, "Tech", 3),
    ("Wireless Mouse", "Quiet clicks, 6-month battery, works on most surfaces.", 27.00, "Tech", 0),
]


def run_schema(conn):
    text = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    text = re.sub(r"^\s*--.*$", "", text, flags=re.M)
    cur = conn.cursor()
    for stmt in (s.strip() for s in text.split(";")):
        if not stmt or stmt.upper().startswith(("CREATE DATABASE", "USE ")):
            continue  # the database is created/selected below using DB_NAME from .env
        try:
            cur.execute(stmt)
        except pymysql.err.OperationalError as e:
            if e.args[0] != 1061:  # 1061 = index already exists (script was run before)
                raise
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="insert sample products")
    args = parser.parse_args()

    base = dict(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                password=Config.DB_PASSWORD, charset="utf8mb4")
    conn = pymysql.connect(**base)
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.close()

    conn = pymysql.connect(database=Config.DB_NAME, **base)
    run_schema(conn)
    print(f"Tables are ready in database '{Config.DB_NAME}'.")

    if args.seed:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products")
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    "INSERT INTO products (name, description, price, category, stock) "
                    "VALUES (%s, %s, %s, %s, %s)", SAMPLE_PRODUCTS)
                conn.commit()
                print(f"Added {len(SAMPLE_PRODUCTS)} sample products.")
            else:
                print("Products table already has data; skipped seeding.")
    conn.close()


if __name__ == "__main__":
    main()
