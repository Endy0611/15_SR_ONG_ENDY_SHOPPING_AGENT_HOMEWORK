"""Application-level control layer (Requirements C & D).

This is the part of the system the model does NOT get to decide. The model
may *propose* a tool call; this harness decides whether it is allowed to
run, validates it, and only then executes the real function.
"""

from dataclasses import dataclass
from typing import Callable

from pydantic import ValidationError

from schemas import TOOL_SCHEMAS
from tools import search_products, check_stock, buy_product, delete_product

# The only tools the harness will ever execute, no matter what name the
# model asks for.
AVAILABLE_FUNCTIONS: dict[str, Callable] = {
    "search_products": search_products,
    "check_stock": check_stock,
    "buy_product": buy_product,
    "delete_product": delete_product,
}

# Permission rule (Requirement C) — checked in application code, not just
# described to the model. See README for the role/action table.
PERMISSIONS: dict[str, set[str]] = {
    "search_products": {"customer", "admin"},
    "check_stock": {"customer", "admin"},
    "buy_product": {"customer", "admin"},
    "delete_product": {"admin"},
}

MAX_ITERATIONS = 8  # agent-loop turns (Requirement D: max iteration limit)
MAX_TOOL_CALLS = 8  # total tool calls per run (Requirement D)


@dataclass
class AgentHarness:
    """Permission, validation, and bounded execution (Requirements C & D)."""

    user_role: str = "customer"
    max_tool_calls: int = MAX_TOOL_CALLS
    tool_calls_made: int = 0

    def execute(self, tool_name: str, arguments: dict) -> dict:
        # 1. Tool must be a known, registered function.
        if tool_name not in AVAILABLE_FUNCTIONS:
            return self._error("TOOL_NOT_ALLOWED", f"Tool '{tool_name}' is not available.")

        # 2. Tool-call budget — prevents an endless agent loop.
        self.tool_calls_made += 1
        if self.tool_calls_made > self.max_tool_calls:
            return self._error("TOOL_CALL_LIMIT", "Maximum tool calls reached for this run.")

        # 3. Permission control (Requirement C).
        if self.user_role not in PERMISSIONS.get(tool_name, set()):
            return self._error(
                "PERMISSION_DENIED", f"Role '{self.user_role}' may not call '{tool_name}'."
            )

        # 4. Input validation (Requirement D) via the tool's Pydantic schema.
        try:
            validated = TOOL_SCHEMAS[tool_name](**arguments)
        except ValidationError as exc:
            return self._error("INVALID_ARGUMENTS", exc.errors()[0]["msg"])

        # 5. Controlled execution (Requirement D) — never let a raw
        # exception reach the model; always return a structured result.
        function = AVAILABLE_FUNCTIONS[tool_name]
        try:
            return function(**validated.model_dump())
        except Exception:
            return self._error("TOOL_EXECUTION_FAILED", "Tool execution failed safely.")

    @staticmethod
    def _error(code: str, message: str) -> dict:
        return {"status": "error", "error_code": code, "message": message}