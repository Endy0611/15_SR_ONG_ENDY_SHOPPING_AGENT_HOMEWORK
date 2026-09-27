"""Tool implementations for the Shopping Agent (Requirement B).

Each function is plain Python business logic that takes already-validated
arguments and returns a small JSON-serializable dict. No tool ever raises
to its caller — failures come back as
{"status": "error", "error_code": ..., "message": ...} so the agent can
*observe* the failure and decide what to do next (bonus: stronger failure
boundaries instead of raw exceptions).

Swap the in-memory catalog below for real Postgres/SQLite without touching
agent.py, harness.py, or schemas.py.
"""

_PRODUCTS: dict[int, dict] = {
    1: {"id": 1, "name": "Acer Aspire 3", "category": "laptop", "price": 420.0, "stock": 5},
    2: {"id": 2, "name": "Dell Inspiron 15", "category": "laptop", "price": 560.0, "stock": 0},
    3: {"id": 3, "name": "Lenovo IdeaPad Slim 5", "category": "laptop", "price": 480.0, "stock": 3},
    4: {"id": 4, "name": "Logitech MX Master 3S", "category": "mouse", "price": 99.0, "stock": 12},
    5: {"id": 5, "name": "Kingston 1TB NVMe SSD", "category": "storage", "price": 75.0, "stock": 20},
}

_PURCHASES: list[dict] = []


def _normalize_category(category: str) -> str:
    """Lowercase and strip a trailing 's' so 'laptop' and 'laptops' match."""
    normalized = category.strip().lower()
    if len(normalized) > 1 and normalized.endswith("s"):
        normalized = normalized[:-1]
    return normalized


def search_products(category: str) -> dict:
    """Search products by category, cheapest first. Matches singular/plural."""
    target = _normalize_category(category)
    matches = sorted(
        (p for p in _PRODUCTS.values() if _normalize_category(p["category"]) == target),
        key=lambda p: p["price"],
    )
    return {
        "status": "success",
        "results": [
            {"id": p["id"], "name": p["name"], "price": p["price"], "in_stock": p["stock"] > 0}
            for p in matches
        ],
    }


def check_stock(product_id: int) -> dict:
    """Return current stock for a product."""
    product = _PRODUCTS.get(product_id)
    if product is None:
        return {"status": "error", "error_code": "PRODUCT_NOT_FOUND", "message": f"No product with id {product_id}."}
    return {"status": "success", "product_id": product_id, "name": product["name"], "stock": product["stock"]}


def buy_product(product_id: int, quantity: int) -> dict:
    """Buy `quantity` units of a product if enough stock exists."""
    product = _PRODUCTS.get(product_id)
    if product is None:
        return {"status": "error", "error_code": "PRODUCT_NOT_FOUND", "message": f"No product with id {product_id}."}

    if product["stock"] < quantity:
        return {
            "status": "error",
            "error_code": "OUT_OF_STOCK",
            "message": f"Only {product['stock']} unit(s) of '{product['name']}' left.",
            "available_stock": product["stock"],
        }

    product["stock"] -= quantity
    total = round(product["price"] * quantity, 2)
    _PURCHASES.append({"product_id": product_id, "quantity": quantity, "total": total})
    return {
        "status": "success",
        "message": f"Purchased {quantity} x '{product['name']}'.",
        "product_id": product_id,
        "quantity": quantity,
        "total_price": total,
        "remaining_stock": product["stock"],
    }


def delete_product(product_id: int) -> dict:
    """Permanently remove a product from the catalog. Admin-only, destructive."""
    product = _PRODUCTS.pop(product_id, None)
    if product is None:
        return {"status": "error", "error_code": "PRODUCT_NOT_FOUND", "message": f"No product with id {product_id}."}
    return {"status": "success", "message": f"Deleted product '{product['name']}'.", "deleted_id": product_id}