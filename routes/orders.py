from flask import Blueprint, abort, g, jsonify, request

from models import order as orders
from utils import admin_required, as_int, json_body, login_required

bp = Blueprint("orders", __name__, url_prefix="/api")


def _own_or_admin(order_id):
    """Fetch an order the current user may see. Others get a 404 (no hint it exists)."""
    order = orders.get_order(order_id)
    if not order or (g.user["role"] != "admin" and order["user_id"] != g.user["id"]):
        abort(404, "Order not found.")
    return order


@bp.post("/orders")
@login_required
def create_order():
    data = json_body()
    address = str(data.get("shipping_address", "")).strip()
    raw_items = data.get("items")

    errors = []
    if not 5 <= len(address) <= 500:
        errors.append("Enter a shipping address (5 to 500 characters).")
    merged = {}
    if not isinstance(raw_items, list) or not raw_items:
        errors.append("Your cart is empty.")
    elif len(raw_items) > 50:
        errors.append("An order can contain at most 50 different products.")
    else:
        for item in raw_items:
            pid = as_int(item.get("product_id")) if isinstance(item, dict) else None
            qty = as_int(item.get("quantity")) if isinstance(item, dict) else None
            if pid is None or pid < 1 or qty is None or not 1 <= qty <= 1000:
                errors.append("Each item needs a valid product and a quantity of at least 1.")
                break
            merged[pid] = merged.get(pid, 0) + qty
    if errors:
        return jsonify(error=errors[0], errors=errors), 400

    try:
        order_id = orders.create_order(g.user["id"], merged, address)
    except orders.OrderError as e:
        return jsonify(error=e.message), e.status
    return jsonify(order=orders.get_order(order_id)), 201


@bp.get("/orders")
@login_required
def list_orders():
    status = request.args.get("status", "").strip()
    if status and status not in orders.STATUSES:
        abort(400, "Unknown status.")
    owner = None if g.user["role"] == "admin" else g.user["id"]  # users only ever see their own
    return jsonify(orders=orders.list_orders(owner, status or None))


@bp.get("/orders/<int:order_id>")
@login_required
def get_order(order_id):
    return jsonify(order=_own_or_admin(order_id))


@bp.put("/orders/<int:order_id>/status")
@admin_required
def update_status(order_id):
    status = str(json_body().get("status", "")).strip()
    if status not in orders.STATUSES:
        abort(400, "Status must be one of: " + ", ".join(orders.STATUSES) + ".")
    try:
        orders.change_status(order_id, status)
    except orders.OrderError as e:
        return jsonify(error=e.message), e.status
    return jsonify(order=orders.get_order(order_id))


@bp.put("/orders/<int:order_id>/cancel")
@login_required
def cancel_order(order_id):
    order = _own_or_admin(order_id)
    if order["user_id"] != g.user["id"]:
        abort(403, "You can only cancel your own orders.")
    if order["status"] != "Pending":
        return jsonify(error="Only orders that are still Pending can be cancelled."), 409
    try:
        orders.change_status(order_id, "Cancelled")
    except orders.OrderError as e:
        return jsonify(error=e.message), e.status
    return jsonify(order=orders.get_order(order_id))
