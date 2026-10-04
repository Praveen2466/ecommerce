from db import execute, query


def list_products(q=None, category=None, ids=None):
    sql = "SELECT * FROM products WHERE 1=1"
    args = []
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE %s OR description LIKE %s OR category LIKE %s)"
        args += [like, like, like]
    if category:
        sql += " AND category = %s"
        args.append(category)
    if ids:
        sql += " AND id IN (%s)" % ",".join(["%s"] * len(ids))
        args += list(ids)
    sql += " ORDER BY created_at DESC, id DESC"
    return query(sql, args)


def categories():
    rows = query("SELECT DISTINCT category FROM products WHERE category <> '' ORDER BY category")
    return [r["category"] for r in rows]


def get(product_id):
    return query("SELECT * FROM products WHERE id = %s", (product_id,), one=True)


def create(d):
    pid, _ = execute(
        "INSERT INTO products (name, description, price, category, stock, image_url) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (d["name"], d["description"], d["price"], d["category"], d["stock"], d["image_url"]),
    )
    return pid


def update(product_id, d):
    _, n = execute(
        "UPDATE products SET name=%s, description=%s, price=%s, category=%s, stock=%s, image_url=%s "
        "WHERE id=%s",
        (d["name"], d["description"], d["price"], d["category"], d["stock"], d["image_url"], product_id),
    )
    return n


def delete(product_id):
    _, n = execute("DELETE FROM products WHERE id = %s", (product_id,))
    return n
