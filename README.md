# Simple Safe Shopping Agent

Topic 07 — Autonomous Agents & Tool Integration

## 1. Project Overview

A small shopping assistant. The user makes a request in plain language
("find the cheapest laptop in stock", "buy 1 of product 2"). The agent
(a local Ollama model) decides whether a tool is needed, calls it with
structured arguments, observes the result, and keeps going until it can
give a final answer — or the run is stopped by a safety limit.

The important design point: **the model proposes an action, the
application (`AgentHarness`) decides whether it is allowed to run.**
Permission, validation, and limits live in Python code, not in the prompt.

## 2. Available Tools

| Tool | What it does | Risk tier |
|---|---|---|
| `search_products(category)` | Search the catalog by category, cheapest first | GREEN |
| `check_stock(product_id)` | Return current stock for one product | GREEN |
| `buy_product(product_id, quantity)` | Buy 1-5 units if enough stock exists | YELLOW (needs approval) |
| `delete_product(product_id)` | Permanently remove a product (admin only) | RED (needs approval) |

Each tool has an implementation in `tools.py` and an input schema in
`schemas.py` (Pydantic). The schema is what the model is allowed to send;
the implementation is what the application actually does.

## 3. Agent Loop

```
User Request
   -> Agent / LLM (Ollama, tool-calling)
   -> proposes a tool call, e.g. search_products("laptop")
   -> AgentHarness.execute(): allowlist -> permission -> validate -> risk/HITL -> run
   -> Tool result observed by the agent
   -> Agent decides: call another tool, or answer
   -> (repeat, bounded by MAX_ITERATIONS / MAX_TOOL_CALLS)
   -> Final answer
```

`agent.py` drives this loop with `ollama`'s chat + tools API. `harness.py`
is the only thing allowed to actually call a Python function.

## 4. Permission Rule

Checked in `harness.py` (`PERMISSIONS` dict), enforced before any tool runs:

| Action | Customer | Admin |
|---|---|---|
| search_products | Yes | Yes |
| check_stock | Yes | Yes |
| buy_product | Yes | Yes |
| delete_product | No | Yes |

Role is chosen at login in `main.py` (`customer` or `admin`). A customer
asking the agent to delete a product gets a `PERMISSION_DENIED` result —
the harness rejects it even if the model requested it.

## 5. Safety

- **Input validation** — every tool call is parsed through its Pydantic
  schema before execution (`product_id` must be a positive int, `quantity`
  must be 1-5, `category` can't be empty). Bad input never reaches the
  real function; it comes back as `INVALID_ARGUMENTS`.
- **Error handling** — tools never raise to the caller. Failures are
  structured dicts (`OUT_OF_STOCK`, `PRODUCT_NOT_FOUND`,
  `TOOL_EXECUTION_FAILED`, ...) so the agent can observe and recover
  instead of crashing.
- **Loop / call limits** — `MAX_ITERATIONS = 8` agent turns and
  `MAX_TOOL_CALLS = 8` total tool calls per run, both enforced in
  `harness.py`, so a confused model can't loop forever.

### Bonus extensions implemented

- **Allowlist** — `AgentHarness` only ever calls functions in
  `AVAILABLE_FUNCTIONS`; any other tool name is rejected as
  `TOOL_NOT_ALLOWED`, even before checking permissions.
- **Risk classification (Green/Yellow/Red)** — read-only tools are GREEN
  and run immediately; `buy_product` (YELLOW) and `delete_product` (RED)
  require approval.
- **Human-in-the-Loop (HITL)** — for YELLOW/RED tools, `agent.py` prints
  the proposed call and asks the operator to approve it (`y`/`N`) before
  the harness executes it. A rejection comes back as `REJECTED_BY_HUMAN`,
  which the agent observes like any other tool result.
- **Stronger failure boundaries** — every rejection/error uses a
  structured `error_code` (`OUT_OF_STOCK`, `PERMISSION_DENIED`,
  `INVALID_ARGUMENTS`, `TOOL_CALL_LIMIT`, ...) instead of a raw exception
  or stack trace, so the agent (and a real UI) can branch on it.

*Not implemented, but worth noting for the MCP bonus:* the same
`AVAILABLE_FUNCTIONS`/`TOOL_SCHEMAS` in `harness.py`/`schemas.py` could be
wrapped one-to-one as MCP tools. The path would be **Host** (this CLI) ->
**Client** (an MCP client embedded in `agent.py`) -> **Server** (a small
FastMCP process exposing `search_products`/`check_stock`/`buy_product`/
`delete_product`) -> **Tool** (the same functions in `tools.py`, unchanged).
The harness's permission/risk/validation logic would move into the MCP
server so it still runs in application code, not the prompt.

## 6. Example Run

Verified directly against `AgentHarness.execute()` (no model needed to see
the control logic — this is what the harness returns for each call):

```
customer role, auto-approved YELLOW/RED for this trace:

1) search_products(category="laptop")
   -> {"status": "success", "results": [
        {"id": 1, "name": "Acer Aspire 3", "price": 420.0, "in_stock": true},
        {"id": 3, "name": "Lenovo IdeaPad Slim 5", "price": 480.0, "in_stock": true},
        {"id": 2, "name": "Dell Inspiron 15", "price": 560.0, "in_stock": false}
      ]}

2) check_stock(product_id=1)
   -> {"status": "success", "product_id": 1, "name": "Acer Aspire 3", "stock": 5}

3) buy_product(product_id=1, quantity=1)   [YELLOW, approved]
   -> {"status": "success", "message": "Purchased 1 x 'Acer Aspire 3'.",
       "product_id": 1, "quantity": 1, "total_price": 420.0, "remaining_stock": 4}

4) delete_product(product_id=1)   [customer role]
   -> {"status": "error", "error_code": "PERMISSION_DENIED",
       "message": "Role 'customer' may not call 'delete_product'."}

5) check_stock(product_id=-1)
   -> {"status": "error", "error_code": "INVALID_ARGUMENTS",
       "message": "Input should be greater than 0"}

--- switching to admin role ---

6) delete_product(product_id=2)   [RED, approved]
   -> {"status": "success", "message": "Deleted product 'Dell Inspiron 15'.",
       "deleted_id": 2}
```

Run `main.py` end-to-end with a live Ollama model to see the same flow
driven by natural language, e.g.:

```
You: Find the cheapest laptop that is currently in stock and buy one.
```

## Run Instructions

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Make sure [Ollama](https://ollama.com) is running locally with a
   tool-calling model pulled, e.g.:
   ```
   ollama pull qwen3:4b
   ```
3. Copy `.env.example` to `.env` and adjust if your Ollama host/model
   differ from the defaults.
4. Run:
   ```
   python main.py
   ```
5. Log in as `customer` or `admin` when prompted, then type a request.

## Project Structure

```
shopping-agent/
├── README.md
├── main.py       # entry point, role login, chat loop
├── agent.py      # model, agent loop, tool schema exposed to the LLM
├── tools.py      # tool implementations (in-memory catalog)
├── schemas.py    # Pydantic input schemas per tool
├── harness.py    # permission, risk tiers, HITL, validation, limits
├── requirements.txt
└── .env.example
```