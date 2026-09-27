# Simple Safe Shopping Agent

Topic 07 — Autonomous Agents & Tool Integration

---

## 1. Project Overview

This is a small shopping assistant. You type what you want in plain
English, like "find the cheapest laptop in stock" or "buy 1 of product
2", and the agent figures out which tool to use, calls it, looks at
the result, and answers you.

The important part: the AI model only *suggests* what it wants to do.
It never runs anything by itself. Every suggested action goes through
`AgentHarness` in `harness.py` first, and that's the part that decides
if the action is actually allowed. So permission checks, input
checking, and safety limits are all real Python code, not just
instructions I typed into the prompt.

## 2. Available Tools

| Tool | What it does |
|---|---|
| `search_products(category)` | Searches the catalog by category, cheapest item first |
| `check_stock(product_id)` | Checks how many units of a product are left |
| `buy_product(product_id, quantity)` | Buys 1 to 5 units, if there's enough stock |
| `delete_product(product_id)` | Removes a product for good (admin only) |

Each tool has two pieces, in two separate files:
- `tools.py` — the actual logic (right now it's an in-memory product
  list, not a real database, since this is just a demo).
- `schemas.py` — a Pydantic model that says exactly what arguments the
  tool expects. If the model sends something that doesn't match the
  schema, it gets rejected before the real function even runs.

## 3. Agent Loop

The agent keeps repeating this cycle until it has a final answer:

```
User Request
   -> Agent / LLM (Ollama, tool calling)      <- decides which tool to use
   -> proposes e.g. search_products("laptop") <- asks to run it
   -> AgentHarness.execute():
        is it a real tool? -> under the call limit? -> allowed for this role? -> valid input? -> run it
   -> Tool result                             <- the agent sees what happened
   -> agent decides: call another tool, or answer the user
   -> (repeats, but stops after 8 turns max)
   -> Final answer
```

`agent.py` runs this loop with Ollama's chat + tools API. `harness.py`
is the only place that's allowed to actually call a tool function —
the model never touches `tools.py` on its own.

## 4. Permission Rule

Who can do what is checked inside `harness.py` (the `PERMISSIONS`
dict), not just written somewhere in the prompt and hoped for:

| Action | Customer | Admin |
|---|---|---|
| search_products | Yes | Yes |
| check_stock | Yes | Yes |
| buy_product | Yes | Yes |
| delete_product | No | Yes |

You pick a role when you log in (`main.py` asks for it). So if a
customer asks the agent to delete something, the model can still try
to call `delete_product` — but the harness stops it and sends back
`PERMISSION_DENIED` before it ever reaches `tools.py`.

## 5. Safety

- **Input validation** — every tool call goes through its Pydantic
  schema first. Product IDs have to be positive numbers, quantity has
  to be between 1 and 5, category can't be blank. Bad input never
  reaches the real function — it just comes back as
  `INVALID_ARGUMENTS`.
- **Error handling** — no tool ever crashes with a raw Python
  exception. Every failure comes back as something like
  `{"status": "error", "error_code": "OUT_OF_STOCK", ...}`, so the
  agent can read what went wrong and decide what to do next instead of
  just breaking.
- **Loop limit** — the agent stops after `MAX_ITERATIONS = 8` turns,
  and after `MAX_TOOL_CALLS = 8` tool calls total. Both are checked in
  `harness.py`. If the model somehow gets stuck looping, it gets
  stopped instead of running forever.

## 6. Example Run

Two full sessions below — one as `customer`, one as `admin` — from
one continuous test. The point of these particular requests is to
show the agent choosing a *different* number of tool calls depending
on what it already knows: sometimes it needs to search first to find
a product ID, sometimes it already has the ID and skips straight to
the action, and sometimes it checks something first and decides the
final tool call isn't even needed.

### Customer session (`python main.py`)

`Buy 1 unit of the cheapest laptop in stock` has no product ID in it,
so the agent has to search first, then feed the ID it found into
`buy_product` — two tool calls chained together for one request:

```
Login as role [customer/admin] (default customer): customer

Logged in as: customer
Try: 'Find the cheapest laptop in stock', 'Buy 1 of product 2', 'Delete product 4'
Type 'exit' to quit.

You: Buy 1 unit of the cheapest laptop in stock

===== AGENT STEP 1 =====
Requested: search_products({"category": "laptops"})
Result: {"status": "success", "results": [{"id": 1, "name": "Acer Aspire 3", "price": 420.0, "in_stock": true}, {"id": 3, "name": "Lenovo IdeaPad Slim 5", "price": 480.0, "in_stock": true}, {"id": 2, "name": "Dell Inspiron 15", "price": 560.0, "in_stock": false}]}

===== AGENT STEP 2 =====
Requested: buy_product({"quantity": 1, "product_id": 1})
Result: {"status": "success", "message": "Purchased 1 x 'Acer Aspire 3'.", "product_id": 1, "quantity": 1, "total_price": 420.0, "remaining_stock": 4}

===== AGENT STEP 3 =====

FINAL ANSWER: The purchase was successful! You've bought 1 unit of **Acer Aspire 3** for a total of $420.00. Remaining stock: 4 units. 🎉

You: Buy 1 of product 1

===== AGENT STEP 1 =====
Requested: buy_product({"product_id": 1, "quantity": 1})
Result: {"status": "success", "message": "Purchased 1 x 'Acer Aspire 3'.", "product_id": 1, "quantity": 1, "total_price": 420.0, "remaining_stock": 3}

===== AGENT STEP 2 =====

FINAL ANSWER: The purchase was successful! You've bought 1 x **Acer Aspire 3** for a total of **$420.00**. The remaining stock for this product is now **3 units**. Let me know if you need further assistance! 😊

You: Buy 5 of product 2

===== AGENT STEP 1 =====
Requested: check_stock({"product_id": 2})
Result: {"status": "success", "product_id": 2, "name": "Dell Inspiron 15", "stock": 0}

===== AGENT STEP 2 =====

FINAL ANSWER: The product "Dell Inspiron 15" (ID 2) is currently out of stock. I cannot complete the purchase of 5 units as there are 0 items available. Would you like to check other products or adjust your request?

You: Search for mouse products and tell me if any are in stock

===== AGENT STEP 1 =====
Requested: search_products({"category": "mouse"})
Result: {"status": "success", "results": [{"id": 4, "name": "Logitech MX Master 3S", "price": 99.0, "in_stock": true}]}

===== AGENT STEP 2 =====

FINAL ANSWER: The search for mouse products shows that **Logitech MX Master 3S (ID 4)** is in stock with a price of $99.00. ✅

You: Search for keyboard products

===== AGENT STEP 1 =====
Requested: search_products({"category": "keyboard"})
Result: {"status": "success", "results": []}

===== AGENT STEP 2 =====

FINAL ANSWER: The search for keyboard products returned no results. It's possible that there are no keyboard products in the catalog, or the category name might need adjustment (e.g., "keyboards" instead of "keyboard"). Would you like to try a different category or check if we have other product types available?
```

Notice `Buy 1 of product 1` (ID already given) only takes one tool
call, while the very first request needed two — same tool
(`buy_product`), reached two different ways depending on the request.
`Buy 5 of product 2` also shows the agent stopping after `check_stock`
and never calling `buy_product` at all, since it already knows the
purchase would fail.

### Admin session (`python main.py`, same run continued)

Same pattern applies to delete, plus a three-tool chain at the end
(search → check stock → buy in a single request):

```
Login as role [customer/admin] (default customer): admin

Logged in as: admin
Try: 'Find the cheapest laptop in stock', 'Buy 1 of product 2', 'Delete product 4'
Type 'exit' to quit.

You: Delete the cheapest laptop from the catalog

===== AGENT STEP 1 =====
Requested: search_products({"category": "laptops"})
Result: {"status": "success", "results": [{"id": 1, "name": "Acer Aspire 3", "price": 420.0, "in_stock": true}, {"id": 3, "name": "Lenovo IdeaPad Slim 5", "price": 480.0, "in_stock": true}, {"id": 2, "name": "Dell Inspiron 15", "price": 560.0, "in_stock": false}]}

===== AGENT STEP 2 =====
Requested: delete_product({"product_id": 1})
Result: {"status": "success", "message": "Deleted product 'Acer Aspire 3'.", "deleted_id": 1}

===== AGENT STEP 3 =====

FINAL ANSWER: The cheapest laptop, **Acer Aspire 3** (ID 1), has been successfully deleted from the catalog.

You: Delete product 4

===== AGENT STEP 1 =====
Requested: delete_product({"product_id": 4})
Result: {"status": "success", "message": "Deleted product 'Logitech MX Master 3S'.", "deleted_id": 4}

===== AGENT STEP 2 =====

FINAL ANSWER: The product with ID 4 (Logitech MX Master 3S) has been successfully deleted from the catalog.

You: Delete product 999

===== AGENT STEP 1 =====
Requested: delete_product({"product_id": 999})
Result: {"status": "error", "error_code": "PRODUCT_NOT_FOUND", "message": "No product with id 999."}

===== AGENT STEP 2 =====

FINAL ANSWER: The product with ID 999 does not exist in the catalog. Would you like to check if you meant a different product ID or search for available products to find the correct one?

You: Buy 10 of product 3

===== AGENT STEP 1 =====

FINAL ANSWER: The user requested to buy 10 of product 3. However, the `buy_product` function only allows quantities between 1 and 5. Since 10 exceeds this limit, the purchase cannot be processed. No tool calls are needed here as the request is invalid by the system's constraints.

You: Search for storage products, check stock, then buy 1 of the cheapest one

===== AGENT STEP 1 =====
Requested: search_products({"category": "storage"})
Result: {"status": "success", "results": [{"id": 5, "name": "Kingston 1TB NVMe SSD", "price": 75.0, "in_stock": true}]}

===== AGENT STEP 2 =====
Requested: check_stock({"product_id": 5})
Result: {"status": "success", "product_id": 5, "name": "Kingston 1TB NVMe SSD", "stock": 20}

===== AGENT STEP 3 =====
Requested: buy_product({"product_id": 5, "quantity": 1})
Result: {"status": "success", "message": "Purchased 1 x 'Kingston 1TB NVMe SSD'.", "product_id": 5, "quantity": 1, "total_price": 75.0, "remaining_stock": 19}

===== AGENT STEP 4 =====

FINAL ANSWER: The purchase was successful! You've bought **1 x Kingston 1TB NVMe SSD** for **$75.00**. The remaining stock for this product is **19 units**. 🎯
```

`Delete product 999` is a good one to point out: the error comes back
as `PRODUCT_NOT_FOUND`, not `PERMISSION_DENIED` — admin *is* allowed
to call `delete_product`, the tool itself just couldn't find that ID.
Permission and business logic are two separate checks, and this shows
both working independently. `Buy 10 of product 3` shows the 1–5
quantity limit applies to admin too, not just customer — validation
isn't tied to role.

### Permission and validation, checked directly against the harness

The two sessions above didn't happen to trigger a live
`PERMISSION_DENIED` or `INVALID_ARGUMENTS` through the model, so here
they are called directly against `AgentHarness.execute()` — this
skips the LLM entirely and proves the checks live in application code,
not just in the prompt (Requirement C: *"Permission must be checked in
application code, not only described in the prompt"*). This is real
output from running the code just now, not written by hand:

```python
>>> from harness import AgentHarness
>>> h = AgentHarness(user_role='customer')

>>> h.execute('delete_product', {'product_id': 1})
{'status': 'error', 'error_code': 'PERMISSION_DENIED', 'message': "Role 'customer' may not call 'delete_product'."}

>>> h.execute('check_stock', {'product_id': -1})
{'status': 'error', 'error_code': 'INVALID_ARGUMENTS', 'message': 'Input should be greater than 0'}

>>> h.execute('buy_product', {'product_id': 1, 'quantity': 10})
{'status': 'error', 'error_code': 'INVALID_ARGUMENTS', 'message': 'Input should be less than or equal to 5'}

>>> h2 = AgentHarness(user_role='admin')
>>> h2.execute('delete_product', {'product_id': 1})
{'status': 'success', 'message': "Deleted product 'Acer Aspire 3'.", 'deleted_id': 1}
```

Same tool call (`delete_product(product_id=1)`), two different roles,
two different results — that's the permission rule enforced in code.
Same tool call shape (`quantity` or `product_id` out of range) rejected
before the real function ever runs — that's the input validation.

---

## Run Instructions

1. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Make sure [Ollama](https://ollama.com) is running on your machine
   and you've pulled a model that supports tool calling, for example:
   ```
   ollama pull qwen3:4b
   ```
3. Copy `.env.example` to `.env`. You only need to change it if your
   Ollama host or model name is different from the defaults.
4. Run it:
   ```
   python main.py
   ```
5. Pick `customer` or `admin` when it asks, then just type what you
   want.

## Project Structure

```
shopping-agent/
├── README.md
├── main.py         # entry point — asks for a role, runs the chat loop
├── agent.py        # the agent loop itself, talks to Ollama
├── tools.py        # the actual tool functions (in-memory product list)
├── schemas.py      # Pydantic schema for each tool's input
├── harness.py      # permission checks, validation, call/iteration limits
├── requirements.txt
└── .env.example
```