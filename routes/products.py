from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, request

from models import product as products
from utils import admin_required, as_int, json_body

bp = Blueprint("products", __name__, url_prefix="/api")


def validate_product(data):
    """Return (clean_dict, errors)."""
    errors = []
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "") or "").strip()
    category = str(data.get("category", "") or "").strip()
    image_url = str(data.get("image_url", "") or "").strip()

    if not 1 <= len(name) <= 150:
        errors.append("Name is required (up to 150 characters).")
    if len(description) > 5000:
        errors.append("Description is too long (5000 characters max).")
    if len(category) > 60:
        errors.append("Category is too long (60 characters max).")
    if image_url and not (image_url.startswith(("http://", "https://", "/")) and len(image_url) <= 500):
        errors.append("Image URL must start with http://, https:// or / (500 characters max).")

    price = None
    raw = data.get("price")
    if isinstance(raw, bool) or raw in (None, ""):
        errors.append("Price is required.")
    else:
        try:
            price = Decimal(str(raw)).quantize(Decimal("0.01"))
            if not price.is_finite() or price <= 0 or price > Decimal("9999999.99"):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            price = None
            errors.append("Price must be a number greater than 0.")

    stock = as_int(data.get("stock"))
    if stock is None or not 0 <= stock <= 1_000_000:
        errors.append("Stock must be a whole number from 0 to 1,000,000.")

    return {
        "name": name, "description": description, "price": price,
        "category": category, "stock": stock, "image_url": image_url,
    }, errors


@bp.get("/products")
def list_products():
    q = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:60]
    ids = None
    if request.args.get("ids"):
        ids = [as_int(x) for x in request.args["ids"].split(",")[:100]]
        ids = [i for i in ids if i is not None and i > 0]
        if not ids:
            return jsonify(products=[])
    return jsonify(products=products.list_products(q or None, category or None, ids))


@bp.get("/categories")
def list_categories():
    return jsonify(categories=products.categories())


@bp.get("/products/<int:product_id>")
def get_product(product_id):
    product = products.get(product_id)
    if not product:
        abort(404, "Product not found.")
    return jsonify(product=product)


@bp.post("/products")
@admin_required
def create_product():
    clean, errors = validate_product(json_body())
    if errors:
        return jsonify(error=errors[0], errors=errors), 400
    return jsonify(product=products.get(products.create(clean))), 201


@bp.put("/products/<int:product_id>")
@admin_required
def update_product(product_id):
    if not products.get(product_id):
        abort(404, "Product not found.")
    clean, errors = validate_product(json_body())
    if errors:
        return jsonify(error=errors[0], errors=errors), 400
    products.update(product_id, clean)
    return jsonify(product=products.get(product_id))


@bp.delete("/products/<int:product_id>")
@admin_required
def delete_product(product_id):
    if not products.delete(product_id):
        abort(404, "Product not found.")
    return jsonify(message="Product deleted.")
