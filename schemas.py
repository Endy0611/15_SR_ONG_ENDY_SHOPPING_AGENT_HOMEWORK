"""Explicit input schemas for every tool (Requirement B).

Each schema is the contract the model must fill in to call a tool: field
names, types, and constraints. The harness validates every tool call
against these BEFORE the real function ever runs.
"""

from pydantic import BaseModel, Field, field_validator


class SearchProductsInput(BaseModel):
    category: str = Field(..., description="Product category to search, e.g. 'laptop'")

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("category must not be empty")
        return v.strip().lower()


class CheckStockInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Positive product ID")


class BuyProductInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Positive product ID")
    quantity: int = Field(..., ge=1, le=5, description="Units to buy (1-5 per order)")


class DeleteProductInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Positive product ID")


# Registry the harness uses to validate a tool call by name.
TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "search_products": SearchProductsInput,
    "check_stock": CheckStockInput,
    "buy_product": BuyProductInput,
    "delete_product": DeleteProductInput,
}