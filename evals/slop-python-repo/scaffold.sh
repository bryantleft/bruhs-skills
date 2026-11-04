#!/usr/bin/env bash
# FastAPI catalog service (bruhs:state framework=fastapi, language=python).
# Planted: app/routes/products.py builds the search SQL with an f-string
# (injection); app/routes/inventory.py constructs an httpx.AsyncClient per
# request and awaits stock lookups one SKU at a time in a for loop.
# Decoys that are fine: get_product() uses a `?` placeholder, and
# sync_supplier_catalog() awaits inside a while loop because each page's
# cursor comes from the previous page (dependent, not independent), using a
# module-level client.
# ruff, mypy, pytest and uv are not installed here and nothing can be
# installed, so validate_pr_ready.sh finds no Python checker to run; the
# stdlib unittest suite does run (python3 -m unittest).
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "fastapi", "language": "python", "database": ["sqlite"], "testing": ["pytest"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write pyproject.toml <<'EOF'
[project]
name = "catalog-api"
version = "0.4.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "httpx>=0.27",
    "uvicorn>=0.30",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
EOF

eval_write .gitignore <<'EOF'
__pycache__/
.venv/
catalog.db
EOF

eval_write app/__init__.py <<'EOF'
EOF

eval_write app/main.py <<'EOF'
from fastapi import FastAPI

from app.routes import inventory, products

app = FastAPI(title="catalog-api")
app.include_router(products.router)
app.include_router(inventory.router)
EOF

eval_write app/db.py <<'EOF'
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

DB_PATH = "catalog.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
EOF

eval_write app/scoring.py <<'EOF'
def relevance(name: str, query: str) -> int:
    """Rank exact matches first, then prefix matches, then substring matches."""
    name, query = name.casefold(), query.casefold()
    if name == query:
        return 3
    if name.startswith(query):
        return 2
    return 1 if query in name else 0
EOF

eval_write app/routes/__init__.py <<'EOF'
EOF

eval_write app/routes/products.py <<'EOF'
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import connect
from app.scoring import relevance

router = APIRouter(prefix="/products")


class Product(BaseModel):
    id: int
    name: str
    price_cents: int


@router.get("/search")
def search_products(q: str) -> list[Product]:
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, name, price_cents FROM products WHERE name LIKE '%{q}%' ORDER BY name"
        ).fetchall()
    products = [Product(**dict(row)) for row in rows]
    return sorted(products, key=lambda p: relevance(p.name, q), reverse=True)


@router.get("/{product_id}")
def get_product(product_id: int) -> Product:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, price_cents FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"product {product_id} not found")
    return Product(**dict(row))
EOF

eval_write app/routes/inventory.py <<'EOF'
import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/inventory")

WAREHOUSE_URL = os.environ.get("WAREHOUSE_URL", "https://warehouse.internal")
SUPPLIER_URL = os.environ.get("SUPPLIER_URL", "https://supplier.example.com")

supplier = httpx.AsyncClient(base_url=SUPPLIER_URL)


class Availability(BaseModel):
    sku: str
    in_stock: int


@router.post("/availability")
async def availability(skus: list[str]) -> list[Availability]:
    async with httpx.AsyncClient(base_url=WAREHOUSE_URL) as client:
        results = []
        for sku in skus:
            resp = await client.get(f"/stock/{sku}")
            resp.raise_for_status()
            results.append(Availability(sku=sku, in_stock=resp.json()["in_stock"]))
    return results


@router.post("/supplier-sync")
async def sync_supplier_catalog() -> dict[str, int]:
    synced = 0
    cursor: str | None = ""
    while cursor is not None:
        resp = await supplier.get("/catalog", params={"cursor": cursor})
        resp.raise_for_status()
        page = resp.json()
        synced += len(page["items"])
        cursor = page["next_cursor"]
    return {"synced": synced}
EOF

eval_write tests/__init__.py <<'EOF'
EOF

eval_write tests/test_scoring.py <<'EOF'
import unittest

from app.scoring import relevance


class RelevanceTest(unittest.TestCase):
    def test_exact_match_ranks_highest(self) -> None:
        self.assertEqual(relevance("Desk Lamp", "desk lamp"), 3)

    def test_prefix_beats_substring(self) -> None:
        self.assertGreater(relevance("Lamp shade", "lamp"), relevance("Desk lamp", "lamp"))

    def test_no_match_scores_zero(self) -> None:
        self.assertEqual(relevance("Chair", "lamp"), 0)


if __name__ == "__main__":
    unittest.main()
EOF

eval_commit "feat: product search and inventory availability endpoints"
eval_origin
eval_gh
