from flask import Blueprint, g, redirect, render_template

from utils import page_admin_required, page_login_required

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/login")
def login():
    return redirect("/") if g.user else render_template("login.html")


@bp.get("/register")
def register():
    return redirect("/") if g.user else render_template("register.html")


@bp.get("/product/<int:product_id>")
def product(product_id):
    return render_template("product.html", product_id=product_id)


@bp.get("/cart")
def cart():
    return render_template("cart.html")


@bp.get("/checkout")
@page_login_required
def checkout():
    return render_template("checkout.html")


@bp.get("/orders")
@page_login_required
def orders():
    return render_template("orders.html")


@bp.get("/admin")
@page_admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")


@bp.get("/admin/products")
@page_admin_required
def admin_products():
    return render_template("admin/products.html")


@bp.get("/admin/orders")
@page_admin_required
def admin_orders():
    return render_template("admin/orders.html")
