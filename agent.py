"""The agent loop (Requirement A):

User Request -> Agent/LLM -> Tool Call -> Tool Execution -> Result ->
Agent Decides Again (repeat) -> Final Answer

Uses a local Ollama model with tool calling. The model only ever
*proposes* a tool call; AgentHarness (harness.py) decides if it runs.
"""

import json
import os

from dotenv import load_dotenv
from ollama import Client

from harness import AgentHarness, MAX_ITERATIONS

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = (
    "You are a shopping assistant. Use the available tools to answer the "
    "user's request. Never claim a purchase or deletion happened unless you "
    "received a tool result confirming it. If a tool returns an error, "
    "treat it as an observation and decide what to do next instead of "
    "repeating the exact same failed call."
)

# Tool schema exposed to the model (Ollama/OpenAI-style function-calling
# format). This describes *how the model may ask*; harness.py + schemas.py
# decide what actually happens.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search products by category, cheapest first.",
            "parameters": {
                "type": "object",
                "properties": {"category": {"type": "string"}},
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Return current stock for a product by its ID.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buy_product",
            "description": "Buy a quantity (1-5) of a product if enough stock exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "quantity": {"type": "integer"},
                },
                "required": ["product_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_product",
            "description": "Permanently delete a product from the catalog. Admin only, destructive.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
]


class ShoppingAgent:
    def __init__(self, user_role: str = "customer"):
        self.client = Client(host=OLLAMA_BASE_URL)
        self.harness = AgentHarness(user_role=user_role)

    def run(self, user_request: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ]

        for step in range(MAX_ITERATIONS):
            print(f"\n===== AGENT STEP {step + 1} =====")

            try:
                response = self.client.chat(model=MODEL, messages=messages, tools=TOOLS)
            except Exception as exc:
                # Do not leak connection/internal details to the caller.
                return f"Model request failed safely: {type(exc).__name__}"

            message = response.message
            messages.append(message)

            if not message.tool_calls:
                return message.content or "No final response was produced."

            for call in message.tool_calls:
                tool_name = call.function.name
                arguments = call.function.arguments

                print(f"Requested: {tool_name}({json.dumps(arguments)})")
                result = self.harness.execute(tool_name, arguments)
                print(f"Result: {json.dumps(result)}")

                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": json.dumps(result),
                })

        return "Agent stopped safely: maximum iterations reached."