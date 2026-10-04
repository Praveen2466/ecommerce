# Marlow: E-Commerce Web Application

A small online store built with **Flask**, **MySQL** and plain **HTML/CSS/JavaScript**.
Customers can browse, search, fill a cart, check out and track orders. Admins manage products and orders.

## Features

**Customers:** register, log in/out, browse and search products (by text and category), product detail page, cart (add, change quantity, remove, total), checkout with shipping address, order history, live order status tracker, cancel own *Pending* orders.

**Admins** (same login): dashboard with totals, add/edit/delete products, view all orders with customer details, filter orders by status, update order status.

**Rules enforced by the server:** passwords hashed; role checks on every admin API and page; users only see their own orders; stock checked and decreased inside one database transaction; prices come from the database (never from the browser); input validation with clear error messages.

## Order status flow

`Pending → Confirmed → Shipped → Delivered`. An order can be `Cancelled` while Pending or Confirmed (stock is returned to the shop). Delivered and Cancelled orders are final.

## Requirements

- Python 3.10+
- MySQL 5.7+ or 8.x (or MariaDB 10.4+) running locally

## Setup

```bash
# 1. Go to the project folder and create a virtual environment
cd ecommerce
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install packages
pip install -r requirements.txt

# 3. Configure
cp .env.example .env              # Windows: copy .env.example .env
#    Edit .env: set DB_PASSWORD (your MySQL password) and a random SECRET_KEY.

# 4. Create the database, tables and sample products
python init_db.py --seed

# 5. Create your admin account (you will be asked for a password)
python create_admin.py --name "Store Admin" --email admin@example.com

# 6. Run
python app.py
```

Open <http://127.0.0.1:5000>.

**Alternative to step 4:** `mysql -u root -p < schema.sql` creates a database named `ecommerce` and the tables (keep `DB_NAME=ecommerce` in `.env`). Sample products come only from `python init_db.py --seed`.

### Admin account

There is deliberately no built-in default password. Run `create_admin.py` with the email you want; it asks for a password and stores only a hash. If the email already belongs to a registered customer, that account is promoted to admin. Log in at `/login`; admins are sent to `/admin`.

### Running the automated checks

```bash
python tests/test_flows.py
```

Runs about 75 checks (user flow, admin flow, authorization) against the database in your `.env`. It creates its own test users/products and deletes them afterwards.

## Project structure

```
app.py            Flask app, error handlers, login lookup
config.py         Settings read from .env
db.py             MySQL connection helper (PyMySQL)
utils.py          Auth decorators and input helpers
schema.sql        Tables: users, products, orders, order_items
init_db.py        Creates database/tables, optional sample data
create_admin.py   Creates or promotes an admin
models/           SQL for users, products, orders
routes/           auth, products, orders, admin APIs + HTML page routes
templates/        Pages (admin/ holds the three admin pages)
static/           style.css and app.js (cart, API calls, page logic)
tests/            test_flows.py
```

## API summary

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/register`, `/api/login`, `/api/logout` | public |
| GET | `/api/me` | public (returns `user: null` if logged out) |
| GET | `/api/products` (`?q=`, `?category=`, `?ids=1,2`), `/api/products/<id>`, `/api/categories` | public |
| POST / PUT / DELETE | `/api/products`, `/api/products/<id>` | admin |
| POST | `/api/orders` | logged in |
| GET | `/api/orders`, `/api/orders/<id>` | logged in (own orders; admin sees all) |
| PUT | `/api/orders/<id>/cancel` | owner, Pending only |
| PUT | `/api/orders/<id>/status` | admin |
| GET | `/api/admin/stats` | admin |

## Design notes

- **Sessions:** Flask signed-cookie sessions (HttpOnly, SameSite=Lax). The user's role is re-read from the database on every request. State-changing endpoints only accept JSON, which browsers won't send cross-site from a plain form. For a public deployment also serve over HTTPS and set `SESSION_COOKIE_SECURE = True`.
- **Cart:** kept in the browser's `localStorage`; it is cleared on logout. Checkout re-validates every product, price and quantity on the server.
- **Deleting a product** keeps old orders intact: order lines store the product name and unit price at purchase time.

## Troubleshooting

- `Access denied for user`: fix `DB_USER` / `DB_PASSWORD` in `.env`.
- `Can't connect to MySQL server`: start MySQL and check `DB_HOST` / `DB_PORT`.
- `Unknown database 'ecommerce'`: run `python init_db.py`.
- Pages show "The database is unavailable": MySQL stopped or `.env` is wrong; check the terminal log.
