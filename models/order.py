from decimal import Decimal

from db import get_db, query

STATUSES = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]

# Allowed status changes. Delivered and Cancelled are final.
TRANSITIONS = {
    "Pending": ["Confirmed", "Cancelled"],
    "Confirmed": ["Shipped", "Cancelled"],
    "Shipped": ["Delivered"],
    "Delivered": [],
    "Cancelled": [],
}


class OrderError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _attach_items(orders):
    if not orders:
        return orders
    ids = [o["id"] for o in orders]
    items = query(
        "SELECT * FROM order_items WHERE order_id IN (%s) ORDER BY id" % ",".join(["%s"] * len(ids)),
        ids,
    )
    by_order = {}
    for item in items:
        by_order.setdefault(item["order_id"], []).append(item)
    for o in orders:
        o["items"] = by_order.get(o["id"], [])
        o["next_statuses"] = TRANSITIONS.get(o["status"], [])
    return orders


_BASE = (
    "SELECT o.*, u.name AS customer_name, u.email AS customer_email "
    "FROM orders o JOIN users u ON u.id = o.user_id"
)


def list_orders(user_id=None, status=None):
    sql, args = _BASE + " WHERE 1=1", []
    if user_id is not None:
        sql += " AND o.user_id = %s"
        args.append(user_id)
    if status:
        sql += " AND o.status = %s"
        args.append(status)
    sql += " ORDER BY o.created_at DESC, o.id DESC"
    return _attach_items(query(sql, args))


def get_order(order_id):
    rows = _attach_items(query(_BASE + " WHERE o.id = %s", (order_id,)))
    return rows[0] if rows else None


def create_order(user_id, items, address):
    """Create an order in ONE transaction. `items` is {product_id: quantity}.

    Rows are locked, stock is checked and decreased, and the order is saved together.
    If anything fails, nothing is saved.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        total = Decimal("0.00")
        lines = []
        for pid in sorted(items):  # fixed order avoids deadlocks between two shoppers
            qty = items[pid]
            cur.execute("SELECT id, name, price, stock FROM products WHERE id = %s FOR UPDATE", (pid,))
            p = cur.fetchone()
            if not p:
                raise OrderError("A product in your cart is no longer available. Please review your cart.", 400)
            if p["stock"] < qty:
                msg = (f'Only {p["stock"]} of "{p["name"]}" left in stock.'
                       if p["stock"] > 0 else f'"{p["name"]}" is out of stock.')
                raise OrderError(msg, 409)
            cur.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s", (qty, pid, qty)
            )
            if cur.rowcount != 1:
                raise OrderError(f'"{p["name"]}" just sold out. Please review your cart.', 409)
            price = Decimal(str(p["price"]))
            total += price * qty
            lines.append((pid, p["name"], price, qty))

        total = total.quantize(Decimal("0.01"))
        cur.execute(
            "INSERT INTO orders (user_id, total_amount, status, shipping_address) "
            "VALUES (%s, %s, 'Pending', %s)",
            (user_id, total, address),
        )
        order_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity) "
            "VALUES (%s, %s, %s, %s, %s)",
            [(order_id, *line) for line in lines],
        )
        conn.commit()
        return order_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def change_status(order_id, new_status):
    """Move an order to a new status (validated). Cancelling puts the stock back."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, status FROM orders WHERE id = %s FOR UPDATE", (order_id,))
        order = cur.fetchone()
        if not order:
            raise OrderError("Order not found.", 404)
        if new_status not in TRANSITIONS.get(order["status"], []):
            raise OrderError(f'A {order["status"]} order cannot be changed to {new_status}.', 409)
        cur.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
        if new_status == "Cancelled":
            cur.execute(
                "SELECT product_id, quantity FROM order_items WHERE order_id = %s AND product_id IS NOT NULL",
                (order_id,),
            )
            for item in cur.fetchall():
                cur.execute(
                    "UPDATE products SET stock = stock + %s WHERE id = %s",
                    (item["quantity"], item["product_id"]),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
