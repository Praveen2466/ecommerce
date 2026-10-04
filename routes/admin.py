from flask import Blueprint, jsonify

from db import query
from models import order as orders
from utils import admin_required

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/stats")
@admin_required
def stats():
    def one(sql):
        return list(query(sql, one=True).values())[0]

    by_status = {s: 0 for s in orders.STATUSES}
    for row in query("SELECT status, COUNT(*) AS n FROM orders GROUP BY status"):
        by_status[row["status"]] = row["n"]
    return jsonify(
        products=one("SELECT COUNT(*) FROM products"),
        low_stock=one("SELECT COUNT(*) FROM products WHERE stock <= 5"),
        customers=one("SELECT COUNT(*) FROM users WHERE role = 'user'"),
        orders=sum(by_status.values()),
        by_status=by_status,
        revenue=one("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status <> 'Cancelled'"),
        recent_orders=orders.list_orders()[:5],
    )
