"""Standalone test for the retry/timeout controls in harness.py.

Simulates a tool that fails once (a transient glitch) then succeeds, and
confirms the harness automatically retries it once before giving up.

Run with:
    python3 test_retry.py
"""

import json

import harness as h

calls = {"n": 0}


def flaky(product_id):
    """Fails on the first call, succeeds on the second — simulates a
    one-off transient error (e.g. a dropped connection)."""
    calls["n"] += 1
    if calls["n"] == 1:
        raise RuntimeError("simulated transient glitch")
    return {"status": "success", "product_id": product_id, "name": "ok after retry", "stock": 1}


# Swap the real check_stock for our flaky test double, just for this run.
h.AVAILABLE_FUNCTIONS["check_stock"] = flaky

agent_harness = h.AgentHarness(user_role="customer")
result = agent_harness.execute("check_stock", {"product_id": 1})

print("Result:", json.dumps(result))
print("Underlying function was called:", calls["n"], "time(s)")

if calls["n"] == 2 and result.get("status") == "success":
    print("\nPASS: failed once, retried automatically, then succeeded.")
else:
    print("\nUNEXPECTED: check MAX_RETRIES in harness.py.")