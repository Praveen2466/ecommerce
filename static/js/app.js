"use strict";

/* ---------- Helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => APP.currency + Number(n).toFixed(2);

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {}, credentials: "same-origin" };
  if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  let res;
  try { res = await fetch(path, init); }
  catch { throw new Error("Cannot reach the server. Check your connection and try again."); }
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON response */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status}).`);
    err.status = res.status;
    err.errors = data && data.errors;
    throw err;
  }
  return data;
}

function toast(message, type = "ok") {
  const el = document.createElement("div");
  el.className = "toast " + (type === "error" ? "error" : "");
  el.textContent = message;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function showError(el, err) {
  el.textContent = err.errors && err.errors.length ? err.errors.join(" ") : err.message;
  el.hidden = false;
}

function hue(text) {
  let h = 0;
  for (const c of String(text)) h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}

/* Product picture: tinted placeholder with an initial; the real image covers it when it loads. */
function thumb(p) {
  const initial = esc((p.name || "?").trim().charAt(0).toUpperCase());
  const img = p.image_url
    ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy" onerror="this.remove()">` : "";
  return `<span class="thumb" style="--h:${hue(p.name)}"><span aria-hidden="true">${initial}</span>${img}</span>`;
}

function stockLabel(p) {
  if (p.stock < 1) return '<span class="stock-out">Out of stock</span>';
  if (p.stock <= 5) return `<span class="stock-low">Only ${p.stock} left</span>`;
  return '<span class="stock-ok">In stock</span>';
}

const statusBadge = (s) => `<span class="status s-${esc(s)}">${esc(s)}</span>`;

/* ---------- Cart (kept in the browser; prices and stock are always re-checked on the server) ---------- */
const Cart = {
  get() {
    try {
      const c = JSON.parse(localStorage.getItem("cart") || "[]");
      return Array.isArray(c) ? c.filter((i) => Number.isInteger(i.id) && Number.isInteger(i.qty) && i.qty > 0) : [];
    } catch { return []; }
  },
  save(items) { localStorage.setItem("cart", JSON.stringify(items)); Cart.badge(); },
  qtyOf(id) { const i = Cart.get().find((x) => x.id === id); return i ? i.qty : 0; },
  add(id, qty, stock) {
    const items = Cart.get();
    const item = items.find((x) => x.id === id);
    const next = Math.min((item ? item.qty : 0) + qty, stock);
    if (item && next === item.qty) return false;           // already at the stock limit
    if (item) item.qty = next; else items.push({ id, qty: next });
    Cart.save(items);
    return true;
  },
  set(id, qty) {
    Cart.save(Cart.get().map((i) => (i.id === id ? { id, qty } : i)));
  },
  remove(id) { Cart.save(Cart.get().filter((i) => i.id !== id)); },
  clear() { Cart.save([]); },
  badge() {
    const n = Cart.get().reduce((sum, i) => sum + i.qty, 0);
    const el = $("#cart-badge");
    if (el) { el.textContent = n; el.hidden = n === 0; }
  },
};

/* Load the cart's products, drop deleted ones and cap quantities at stock. */
async function loadCartLines() {
  const cart = Cart.get();
  if (!cart.length) return [];
  const { products } = await api("/api/products?ids=" + cart.map((i) => i.id).join(","));
  const byId = Object.fromEntries(products.map((p) => [p.id, p]));
  const lines = [];
  let changed = false;
  for (const item of cart) {
    const p = byId[item.id];
    const qty = p ? Math.min(item.qty, p.stock) : 0;
    if (qty !== item.qty) changed = true;
    if (qty > 0) lines.push({ p, qty });
  }
  if (changed) {
    Cart.save(lines.map((l) => ({ id: l.p.id, qty: l.qty })));
    toast("Your cart was updated to match current stock.", "error");
  }
  return lines;
}

const cartTotal = (lines) => lines.reduce((sum, l) => sum + l.p.price * l.qty, 0);

function safeNext() {
  const next = new URLSearchParams(location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

/* ---------- Pages ---------- */
const Pages = {};

Pages.home = async () => {
  const grid = $("#grid"), search = $("#search"), category = $("#category");
  let list = [];

  try {
    const { categories } = await api("/api/categories");
    category.insertAdjacentHTML("beforeend", categories.map((c) => `<option>${esc(c)}</option>`).join(""));
  } catch { /* filter simply stays on "All" */ }

  async function load() {
    const params = new URLSearchParams();
    if (search.value.trim()) params.set("q", search.value.trim());
    if (category.value) params.set("category", category.value);
    try {
      list = (await api("/api/products?" + params)).products;
    } catch (e) {
      grid.innerHTML = `<p class="notice error">${esc(e.message)}</p>`;
      return;
    }
    if (!list.length) {
      grid.innerHTML = '<p class="muted">No products match your search. Try a different word or clear the category.</p>';
      return;
    }
    grid.innerHTML = list.map((p) => `
      <article class="card">
        <a href="/product/${p.id}" aria-label="${esc(p.name)}">${thumb(p)}</a>
        <div class="card-body">
          <a class="card-title" href="/product/${p.id}">${esc(p.name)}</a>
          <span class="muted">${esc(p.category)}</span>
          <div class="row between"><span class="price">${money(p.price)}</span>${stockLabel(p)}</div>
          <button class="btn" data-add="${p.id}" ${p.stock < 1 ? "disabled" : ""}>Add to cart</button>
        </div>
      </article>`).join("");
  }

  grid.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add]");
    if (!btn) return;
    const p = list.find((x) => x.id === Number(btn.dataset.add));
    if (Cart.add(p.id, 1, p.stock)) toast(`Added "${p.name}" to your cart.`);
    else toast(`All ${p.stock} in stock are already in your cart.`, "error");
  });
  let timer;
  search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
  category.addEventListener("change", load);
  $("#search-form").addEventListener("submit", (e) => { e.preventDefault(); load(); });
  load();
};

Pages.product = async () => {
  const root = $("#product");
  let p;
  try {
    p = (await api("/api/products/" + document.body.dataset.productId)).product;
  } catch (e) {
    root.innerHTML = `<p class="notice error">${esc(e.status === 404 ? "This product doesn't exist or was removed." : e.message)}</p>`;
    return;
  }
  document.title = p.name + " | Marlow";
  root.innerHTML = `
    <div class="detail">
      ${thumb(p)}
      <div>
        <h1>${esc(p.name)}</h1>
        <p class="muted">${esc(p.category)}</p>
        <p class="price">${money(p.price)}</p>
        <p>${esc(p.description).replace(/\n/g, "<br>") || '<span class="muted">No description yet.</span>'}</p>
        <p>${stockLabel(p)}</p>
        ${p.stock > 0 ? `
        <div class="row">
          <div class="qty">
            <button type="button" id="dec" aria-label="Decrease quantity">&minus;</button>
            <input id="qty" type="number" min="1" max="${p.stock}" value="1" aria-label="Quantity">
            <button type="button" id="inc" aria-label="Increase quantity">+</button>
          </div>
          <button class="btn" id="add">Add to cart</button>
        </div>` : ""}
      </div>
    </div>`;
  if (p.stock < 1) return;
  const qty = $("#qty");
  const clamp = () => { qty.value = Math.max(1, Math.min(p.stock, parseInt(qty.value, 10) || 1)); return Number(qty.value); };
  $("#dec").onclick = () => { qty.value = clamp() - 1; clamp(); };
  $("#inc").onclick = () => { qty.value = clamp() + 1; clamp(); };
  qty.onchange = clamp;
  $("#add").onclick = () => {
    if (Cart.add(p.id, clamp(), p.stock)) toast(`Added to your cart. You have ${Cart.qtyOf(p.id)} of this item.`);
    else toast(`All ${p.stock} in stock are already in your cart.`, "error");
  };
};

Pages.login = () => {
  const err = $("#form-error");
  if (new URLSearchParams(location.search).get("registered")) {
    const info = $("#info");
    info.textContent = "Account created. Log in to continue.";
    info.hidden = false;
  }
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    try {
      const { user } = await api("/api/login", { method: "POST", body: { email: $("#email").value, password: $("#password").value } });
      location.href = safeNext() || (user.role === "admin" ? "/admin" : "/");
    } catch (ex) { showError(err, ex); }
  });
};

Pages.register = () => {
  const err = $("#form-error");
  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    if ($("#password").value !== $("#confirm").value) {
      return showError(err, new Error("The two passwords don't match."));
    }
    try {
      await api("/api/register", { method: "POST", body: { name: $("#name").value, email: $("#email").value, password: $("#password").value } });
      location.href = "/login?registered=1";
    } catch (ex) { showError(err, ex); }
  });
};

Pages.cart = async () => {
  const root = $("#cart");
  let lines;
  try { lines = await loadCartLines(); }
  catch (e) { root.innerHTML = `<p class="notice error">${esc(e.message)}</p>`; return; }

  function render() {
    if (!lines.length) {
      root.innerHTML = '<p class="lead">Your cart is empty.</p><p><a class="btn" href="/">Browse products</a></p>';
      return;
    }
    const count = lines.reduce((s, l) => s + l.qty, 0);
    root.innerHTML = `
      <div class="split">
        <div class="panel">${lines.map(({ p, qty }) => `
          <div class="line">
            <a href="/product/${p.id}">${thumb(p)}</a>
            <div>
              <a class="card-title" href="/product/${p.id}">${esc(p.name)}</a>
              <div class="muted">${money(p.price)} each${p.stock <= 5 ? ` · only ${p.stock} left` : ""}</div>
              <div class="row">
                <div class="qty">
                  <button type="button" data-dec="${p.id}" aria-label="Decrease quantity of ${esc(p.name)}">&minus;</button>
                  <input type="number" min="1" max="${p.stock}" value="${qty}" data-qty="${p.id}" aria-label="Quantity of ${esc(p.name)}">
                  <button type="button" data-inc="${p.id}" aria-label="Increase quantity of ${esc(p.name)}">+</button>
                </div>
                <button type="button" class="link-btn" data-remove="${p.id}">Remove</button>
              </div>
            </div>
            <div class="line-total">${money(p.price * qty)}</div>
          </div>`).join("")}
        </div>
        <aside class="panel">
          <h2>Summary</h2>
          <div class="sum"><span>Items (${count})</span><span>${money(cartTotal(lines))}</span></div>
          <div class="sum total"><span>Total</span><span>${money(cartTotal(lines))}</span></div>
          <p><a class="btn" href="/checkout">Go to checkout</a></p>
        </aside>
      </div>`;
  }

  function setQty(id, qty) {
    const line = lines.find((l) => l.p.id === id);
    qty = Math.max(1, Math.min(line.p.stock, qty || 1));
    line.qty = qty;
    Cart.set(id, qty);
    render();
  }
  root.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    const find = (a) => lines.find((l) => l.p.id === Number(t.dataset[a]));
    if (t.dataset.inc) { const l = find("inc"); if (l.qty >= l.p.stock) toast(`Only ${l.p.stock} in stock.`, "error"); setQty(l.p.id, l.qty + 1); }
    if (t.dataset.dec) { const l = find("dec"); setQty(l.p.id, l.qty - 1); }
    if (t.dataset.remove) { const id = Number(t.dataset.remove); Cart.remove(id); lines = lines.filter((l) => l.p.id !== id); render(); }
  });
  root.addEventListener("change", (e) => {
    if (e.target.dataset.qty) setQty(Number(e.target.dataset.qty), parseInt(e.target.value, 10));
  });
  render();
};

Pages.checkout = async () => {
  const root = $("#checkout");
  let lines;
  try { lines = await loadCartLines(); }
  catch (e) { root.innerHTML = `<p class="notice error">${esc(e.message)}</p>`; return; }
  if (!lines.length) {
    root.innerHTML = '<div><p class="lead">Your cart is empty.</p><p><a class="btn" href="/">Browse products</a></p></div>';
    return;
  }
  root.innerHTML = `
    <form id="checkout-form" class="panel form" novalidate style="max-width:none">
      <h2>Shipping</h2>
      <label>Delivery address
        <textarea id="address" rows="4" maxlength="500" required placeholder="Name, street, city, postal code"></textarea></label>
      <p class="muted">This is a demo store: no payment is collected. You'll pay on delivery.</p>
      <div id="form-error" class="notice error" role="alert" hidden></div>
      <button class="btn" id="place" type="submit">Place order</button>
    </form>
    <aside class="panel">
      <h2>Order summary</h2>
      ${lines.map(({ p, qty }) => `<div class="sum"><span>${esc(p.name)} × ${qty}</span><span>${money(p.price * qty)}</span></div>`).join("")}
      <div class="sum total"><span>Total</span><span>${money(cartTotal(lines))}</span></div>
      <p><a href="/cart">Edit cart</a></p>
    </aside>`;
  const err = $("#form-error"), place = $("#place");
  $("#checkout-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    place.disabled = true;
    try {
      const { order } = await api("/api/orders", { method: "POST", body: {
        shipping_address: $("#address").value,
        items: lines.map((l) => ({ product_id: l.p.id, quantity: l.qty })),
      } });
      Cart.clear();
      location.href = "/orders?placed=" + order.id;
    } catch (ex) {
      if (ex.status === 401) { location.href = "/login?next=/checkout"; return; }
      showError(err, ex);
      place.disabled = false;
    }
  });
};

const TRACK = ["Pending", "Confirmed", "Shipped", "Delivered"];

Pages.orders = async () => {
  const root = $("#orders");
  const placed = new URLSearchParams(location.search).get("placed");
  if (placed) {
    const n = $("#placed");
    n.textContent = `Thank you! Order #${placed} was placed.`;
    n.hidden = false;
  }

  async function load() {
    let orders;
    try { orders = (await api("/api/orders")).orders; }
    catch (e) { root.innerHTML = `<p class="notice error">${esc(e.message)}</p>`; return; }
    if (!orders.length) {
      root.innerHTML = '<p class="lead">You haven\'t placed any orders yet.</p><p><a class="btn" href="/">Start shopping</a></p>';
      return;
    }
    root.innerHTML = orders.map((o) => {
      const at = TRACK.indexOf(o.status);
      const tracker = o.status === "Cancelled"
        ? '<p class="muted">This order was cancelled.</p>'
        : `<ol class="tracker" aria-label="Order progress">${TRACK.map((s, i) =>
            `<li class="${i <= at ? "done" : ""} ${i === at ? "current" : ""}">${s}</li>`).join("")}</ol>`;
      return `
      <article class="order">
        <div class="order-head">
          <div><h3>Order #${o.id}</h3><span class="muted">Placed ${esc(o.created_at)}</span></div>
          <div>${statusBadge(o.status)}</div>
        </div>
        ${tracker}
        <ul>${o.items.map((i) => `<li class="item"><span>${esc(i.product_name)} × ${i.quantity}</span><span>${money(i.unit_price * i.quantity)}</span></li>`).join("")}</ul>
        <div class="sum total"><span>Total</span><span>${money(o.total_amount)}</span></div>
        <p class="muted">Ships to: ${esc(o.shipping_address)}</p>
        ${o.status === "Pending" ? `<button class="btn btn-ghost btn-small" data-cancel="${o.id}">Cancel order</button>` : ""}
      </article>`;
    }).join("");
  }
  root.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-cancel]");
    if (!btn || !confirm("Cancel this order?")) return;
    try { await api(`/api/orders/${btn.dataset.cancel}/cancel`, { method: "PUT" }); toast("Order cancelled."); load(); }
    catch (ex) { toast(ex.message, "error"); load(); }
  });
  load();
};

/* ---------- Admin ---------- */
function ordersTable(orders, withActions) {
  return `<table>
    <thead><tr><th>Order</th><th>Customer</th><th>Items</th><th>Total</th><th>Status</th>${withActions ? "<th>Update</th>" : ""}</tr></thead>
    <tbody>${orders.map((o) => `<tr>
      <td>#${o.id}<br><span class="muted">${esc(o.created_at)}</span></td>
      <td>${esc(o.customer_name)}<br><span class="muted">${esc(o.customer_email)}</span>
        ${withActions ? `<br><span class="muted">${esc(o.shipping_address)}</span>` : ""}</td>
      <td>${o.items.map((i) => `${esc(i.product_name)} × ${i.quantity}`).join("<br>")}</td>
      <td>${money(o.total_amount)}</td>
      <td>${statusBadge(o.status)}</td>
      ${withActions ? `<td>${o.next_statuses.length ? `
        <div class="row"><select data-status-for="${o.id}" aria-label="New status for order ${o.id}">
          ${o.next_statuses.map((s) => `<option>${s}</option>`).join("")}</select>
          <button class="btn btn-small" data-update="${o.id}">Update</button></div>`
        : '<span class="muted">Final</span>'}</td>` : ""}
    </tr>`).join("")}</tbody></table>`;
}

Pages["admin-dashboard"] = async () => {
  const root = $("#stats");
  try {
    const s = await api("/api/admin/stats");
    const tile = (label, value) => `<div class="stat"><b>${value}</b>${label}</div>`;
    root.innerHTML = `
      <div class="stats">
        ${tile("Revenue (excl. cancelled)", money(s.revenue))}
        ${tile("Orders", s.orders)}
        ${tile("Pending orders", s.by_status.Pending)}
        ${tile("Products", s.products)}
        ${tile("Low or no stock", s.low_stock)}
        ${tile("Customers", s.customers)}
      </div>
      <div class="row between"><h2>Recent orders</h2><a href="/admin/orders">Manage all orders</a></div>
      <div class="table-wrap">${s.recent_orders.length ? ordersTable(s.recent_orders, false) : '<p class="panel muted">No orders yet.</p>'}</div>
      <p><a class="btn" href="/admin/products">Manage products</a></p>`;
  } catch (e) { root.innerHTML = `<p class="notice error">${esc(e.message)}</p>`; }
};

Pages["admin-products"] = async () => {
  const root = $("#products"), dialog = $("#product-dialog"), form = $("#product-form"), err = $("#form-error");
  let list = [], editingId = null;
  const f = { name: $("#p-name"), description: $("#p-description"), price: $("#p-price"),
              stock: $("#p-stock"), category: $("#p-category"), image_url: $("#p-image") };

  async function load() {
    try { list = (await api("/api/products")).products; }
    catch (e) { root.innerHTML = `<p class="notice error">${esc(e.message)}</p>`; return; }
    $("#category-list").innerHTML = [...new Set(list.map((p) => p.category).filter(Boolean))].map((c) => `<option value="${esc(c)}">`).join("");
    root.innerHTML = list.length ? `<table>
      <thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Actions</th></tr></thead>
      <tbody>${list.map((p) => `<tr>
        <td>${p.id}</td><td><a href="/product/${p.id}">${esc(p.name)}</a></td><td>${esc(p.category)}</td>
        <td>${money(p.price)}</td><td>${p.stock}</td>
        <td class="actions"><div class="row">
          <button class="btn btn-ghost btn-small" data-edit="${p.id}">Edit</button>
          <button class="btn btn-danger btn-small" data-delete="${p.id}">Delete</button></div></td>
      </tr>`).join("")}</tbody></table>` : '<p class="panel muted">No products yet. Use "Add product" to create one.</p>';
  }

  function open(p) {
    editingId = p ? p.id : null;
    $("#dialog-title").textContent = p ? "Edit product" : "Add product";
    f.name.value = p ? p.name : ""; f.description.value = p ? p.description || "" : "";
    f.price.value = p ? p.price : ""; f.stock.value = p ? p.stock : "0";
    f.category.value = p ? p.category : ""; f.image_url.value = p ? p.image_url : "";
    err.hidden = true;
    dialog.showModal();
  }

  $("#add-product").onclick = () => open(null);
  $("#cancel-dialog").onclick = () => dialog.close();
  root.addEventListener("click", async (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.edit) open(list.find((p) => p.id === Number(t.dataset.edit)));
    if (t.dataset.delete) {
      const p = list.find((x) => x.id === Number(t.dataset.delete));
      if (!confirm(`Delete "${p.name}"? Past orders keep their record of it.`)) return;
      try { await api("/api/products/" + p.id, { method: "DELETE" }); toast("Product deleted."); load(); }
      catch (ex) { toast(ex.message, "error"); }
    }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    const body = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.value]));
    try {
      await api(editingId ? "/api/products/" + editingId : "/api/products", { method: editingId ? "PUT" : "POST", body });
      dialog.close();
      toast(editingId ? "Product updated." : "Product added.");
      load();
    } catch (ex) { showError(err, ex); }
  });
  load();
};

Pages["admin-orders"] = async () => {
  const root = $("#orders"), filter = $("#status-filter");
  async function load() {
    try {
      const { orders } = await api("/api/orders" + (filter.value ? "?status=" + filter.value : ""));
      root.innerHTML = orders.length ? ordersTable(orders, true) : '<p class="panel muted">No orders found.</p>';
    } catch (e) { root.innerHTML = `<p class="notice error">${esc(e.message)}</p>`; }
  }
  filter.addEventListener("change", load);
  root.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-update]");
    if (!btn) return;
    const status = $(`[data-status-for="${btn.dataset.update}"]`).value;
    try {
      await api(`/api/orders/${btn.dataset.update}/status`, { method: "PUT", body: { status } });
      toast(`Order #${btn.dataset.update} is now ${status}.`);
    } catch (ex) { toast(ex.message, "error"); }
    load();
  });
  load();
};

/* ---------- Start ---------- */
document.addEventListener("DOMContentLoaded", () => {
  Cart.badge();
  const logout = $("#logout-btn");
  if (logout) logout.addEventListener("click", async () => {
    try { await api("/api/logout", { method: "POST" }); } catch { /* ignore */ }
    Cart.clear();
    location.href = "/";
  });
  const init = Pages[document.body.dataset.page];
  if (init) init();
});
