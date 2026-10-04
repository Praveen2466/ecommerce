"""End-to-end checks of the user flow, admin flow and authorization rules.

Run from the project folder (with your .env pointing at a test/dev database):
    python tests/test_flows.py
It creates its own uniquely named users and products and deletes them afterwards.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from db import execute, query  # noqa: E402
from models import user as users  # noqa: E402

TAG = uuid.uuid4().hex[:8]
PASSWORD = "correct-horse-1"
results = []


def check(name, condition):
    results.append((name, bool(condition)))
    print(("PASS  " if condition else "FAIL  ") + name)


def main():
    anon, alice, bob, admin = (app.test_client() for _ in range(4))
    a_mail, b_mail, adm_mail = (f"{n}-{TAG}@test.example" for n in ("alice", "bob", "admin"))

    with app.app_context():
        users.create("Test Admin", adm_mail, PASSWORD, role="admin")

    # ---- logged-out access ----
    check("Logged-out user is redirected from /orders", anon.get("/orders").status_code == 302)
    check("Logged-out user is redirected from /checkout", anon.get("/checkout").status_code == 302)
    check("Logged-out user is redirected from /admin", anon.get("/admin").status_code == 302)
    check("Logged-out GET /api/orders -> 401", anon.get("/api/orders").status_code == 401)
    check("Logged-out POST /api/orders -> 401", anon.post("/api/orders", json={}).status_code == 401)
    check("Logged-out POST /api/products -> 401", anon.post("/api/products", json={}).status_code == 401)
    check("Public pages load (/, /cart, /login, /register)",
          all(anon.get(p).status_code == 200 for p in ("/", "/cart", "/login", "/register")))

    # ---- registration & login ----
    reg = lambda **kw: anon.post("/api/register", json={"name": "Alice", "email": a_mail, "password": PASSWORD, **kw})
    check("Register rejects bad email", reg(email="nope").status_code == 400)
    check("Register rejects short password", reg(password="123").status_code == 400)
    r = reg()
    check("Register succeeds (201) and role is 'user'", r.status_code == 201 and r.json["user"]["role"] == "user")
    check("Register never exposes the password hash", "password" not in str(r.json))
    check("Duplicate email -> 409", reg().status_code == 409)
    check("Register can't self-assign admin role",
          bob.post("/api/register", json={"name": "Bob", "email": b_mail, "password": PASSWORD, "role": "admin"}).json["user"]["role"] == "user")
    with app.app_context():
        stored = users.get_by_email(a_mail)["password_hash"]
    check("Password is stored hashed, not plain text", stored != PASSWORD and PASSWORD not in stored)
    check("Wrong password -> 401", alice.post("/api/login", json={"email": a_mail, "password": "wrong-wrong"}).status_code == 401)
    check("Login succeeds", alice.post("/api/login", json={"email": a_mail, "password": PASSWORD}).status_code == 200)
    check("Bob can log in", bob.post("/api/login", json={"email": b_mail, "password": PASSWORD}).status_code == 200)
    check("Admin can log in via the same endpoint",
          admin.post("/api/login", json={"email": adm_mail, "password": PASSWORD}).json["user"]["role"] == "admin")
    check("/api/me returns the logged-in user", alice.get("/api/me").json["user"]["email"] == a_mail)

    # ---- admin product management ----
    prod = {"name": f"Test Lamp {TAG}", "description": "A lamp", "price": "19.99", "category": f"Testing{TAG}", "stock": 5, "image_url": ""}
    check("Admin dashboard page loads for admin", admin.get("/admin").status_code == 200)
    check("Admin stats endpoint works", admin.get("/api/admin/stats").status_code == 200)
    check("Admin product/order pages load",
          admin.get("/admin/products").status_code == 200 and admin.get("/admin/orders").status_code == 200)
    check("Add product rejects negative price", admin.post("/api/products", json={**prod, "price": -1}).status_code == 400)
    check("Add product rejects bad stock", admin.post("/api/products", json={**prod, "stock": "lots"}).status_code == 400)
    r = admin.post("/api/products", json=prod)
    pid = r.json["product"]["id"]
    check("Admin adds product (201)", r.status_code == 201 and r.json["product"]["price"] == 19.99)
    r = admin.put(f"/api/products/{pid}", json={**prod, "name": f"Test Lamp XL {TAG}", "price": 24.5})
    check("Admin edits product", r.status_code == 200 and r.json["product"]["price"] == 24.5)

    # ---- authorization: normal users ----
    check("User cannot open /admin pages (403)", alice.get("/admin").status_code == 403 and alice.get("/admin/products").status_code == 403)
    check("User cannot create product (403)", alice.post("/api/products", json=prod).status_code == 403)
    check("User cannot edit product (403)", alice.put(f"/api/products/{pid}", json=prod).status_code == 403)
    check("User cannot delete product (403)", alice.delete(f"/api/products/{pid}").status_code == 403)
    check("User cannot read admin stats (403)", alice.get("/api/admin/stats").status_code == 403)

    # ---- browsing ----
    check("Product list includes the product", any(p["id"] == pid for p in anon.get("/api/products").json["products"]))
    check("Search finds the product", [p["id"] for p in anon.get(f"/api/products?q=Lamp XL {TAG}").json["products"]] == [pid])
    check("Search with no match returns empty", anon.get(f"/api/products?q=zzzz{TAG}").json["products"] == [])
    check("Category filter works", [p["id"] for p in anon.get(f"/api/products?category=Testing{TAG}").json["products"]] == [pid])
    check("Product details endpoint works", anon.get(f"/api/products/{pid}").json["product"]["stock"] == 5)
    check("Unknown product -> 404 JSON", anon.get("/api/products/99999999").status_code == 404)
    check("Product page loads", anon.get(f"/product/{pid}").status_code == 200)
    check("Cart lookup by ids works", len(anon.get(f"/api/products?ids={pid}").json["products"]) == 1)

    # ---- ordering ----
    addr = "1 Test Street, Testville 12345"
    stock = lambda: anon.get(f"/api/products/{pid}").json["product"]["stock"]
    check("Order with empty cart -> 400", alice.post("/api/orders", json={"items": [], "shipping_address": addr}).status_code == 400)
    check("Order without address -> 400", alice.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 1}], "shipping_address": ""}).status_code == 400)
    check("Order with quantity 0 -> 400", alice.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 0}], "shipping_address": addr}).status_code == 400)
    check("Order for missing product -> 400", alice.post("/api/orders", json={"items": [{"product_id": 99999999, "quantity": 1}], "shipping_address": addr}).status_code == 400)
    r = alice.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 6}], "shipping_address": addr})
    check("Ordering more than stock -> 409", r.status_code == 409)
    check("Stock unchanged after rejected order", stock() == 5)
    r = alice.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 2}, {"product_id": pid, "quantity": 1}], "shipping_address": addr})
    oid = r.json["order"]["id"]
    check("Valid order created (201), status Pending", r.status_code == 201 and r.json["order"]["status"] == "Pending")
    check("Duplicate lines merged and total computed on the server (3 x 24.50)",
          r.json["order"]["items"][0]["quantity"] == 3 and r.json["order"]["total_amount"] == 73.5)
    check("Stock decreased after order (5 -> 2)", stock() == 2)
    check("Client cannot set its own price", alice.post("/api/orders", json={"items": [{"product_id": pid, "quantity": 1, "price": 0.01}], "shipping_address": addr}).json["order"]["total_amount"] == 24.5)
    check("Stock decreased again (2 -> 1)", stock() == 1)

    # ---- order visibility ----
    check("Alice sees her orders", len(alice.get("/api/orders").json["orders"]) == 2)
    check("Alice can open her order", alice.get(f"/api/orders/{oid}").status_code == 200)
    check("Bob sees none of Alice's orders", bob.get("/api/orders").json["orders"] == [])
    check("Bob cannot open Alice's order (404)", bob.get(f"/api/orders/{oid}").status_code == 404)
    check("Bob cannot cancel Alice's order", bob.put(f"/api/orders/{oid}/cancel").status_code == 404)
    check("Bob cannot change status (403)", bob.put(f"/api/orders/{oid}/status", json={"status": "Delivered"}).status_code == 403)
    check("Alice cannot change status (403)", alice.put(f"/api/orders/{oid}/status", json={"status": "Delivered"}).status_code == 403)
    check("Admin sees all orders with customer info",
          any(o["id"] == oid and o["customer_email"] == a_mail for o in admin.get("/api/orders").json["orders"]))
    check("Admin can filter orders by status", all(o["status"] == "Pending" for o in admin.get("/api/orders?status=Pending").json["orders"]))
    check("My Orders page loads when logged in", alice.get("/orders").status_code == 200 and alice.get("/checkout").status_code == 200)

    # ---- status management ----
    st = lambda s, o=oid: admin.put(f"/api/orders/{o}/status", json={"status": s})
    check("Invalid status name -> 400", st("Teleported").status_code == 400)
    check("Skipping steps (Pending -> Delivered) is refused", st("Delivered").status_code == 409)
    check("Admin: Pending -> Confirmed", st("Confirmed").json["order"]["status"] == "Confirmed")
    check("User sees the new status", alice.get(f"/api/orders/{oid}").json["order"]["status"] == "Confirmed")
    check("User cannot cancel a Confirmed order (409)", alice.put(f"/api/orders/{oid}/cancel").status_code == 409)
    check("Admin: Confirmed -> Shipped -> Delivered", st("Shipped").status_code == 200 and st("Delivered").json["order"]["status"] == "Delivered")
    check("Delivered orders are final", st("Cancelled").status_code == 409)

    other = [o["id"] for o in alice.get("/api/orders").json["orders"] if o["id"] != oid][0]
    r = alice.put(f"/api/orders/{other}/cancel")
    check("User cancels own Pending order", r.status_code == 200 and r.json["order"]["status"] == "Cancelled")
    check("Cancelling restores stock (1 -> 2)", stock() == 2)

    # ---- deleting a product keeps order history ----
    check("Admin deletes product", admin.delete(f"/api/products/{pid}").status_code == 200)
    check("Deleted product -> 404", anon.get(f"/api/products/{pid}").status_code == 404)
    kept = alice.get(f"/api/orders/{oid}").json["order"]["items"][0]
    check("Past order still shows deleted product's name", kept["product_name"].startswith("Test Lamp XL"))

    # ---- logout ----
    check("Logout works", alice.post("/api/logout").status_code == 200)
    check("After logout: /api/orders -> 401 and /orders redirects",
          alice.get("/api/orders").status_code == 401 and alice.get("/orders").status_code == 302)
    check("Unknown API route returns JSON 404", anon.get("/api/nope").is_json)

    # ---- cleanup ----
    with app.app_context():
        for mail in (a_mail, b_mail, adm_mail):
            u = users.get_by_email(mail)
            if u:
                execute("DELETE FROM orders WHERE user_id = %s", (u["id"],))
                execute("DELETE FROM users WHERE id = %s", (u["id"],))

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
