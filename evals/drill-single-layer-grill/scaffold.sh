#!/usr/bin/env bash
# Python FastAPI billing service with three packages (app/billing,
# app/search, app/accounts). .github/workflows/ci.yml has one `checks` job
# with timeout-minutes: 10 (the CI critical-path cap, docs/adr/0002) running
# ruff, mypy, pytest --cov and diff-cover --fail-under=78 on changed lines (a
# hard gate). No mutation runner anywhere. CONTEXT.md records the suite size
# and speed (~1,800 unit tests in ~22 s) and incident INC-41: a refund test
# passed while asserting nothing and the function returned the wrong value.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "fastapi", "language": "python", "database": ["postgres"], "testing": ["pytest", "pytest-cov", "diff-cover"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write pyproject.toml <<'EOF'
[project]
name = "billing-api"
version = "2.3.0"
requires-python = ">=3.13"
dependencies = ["fastapi>=0.115", "sqlalchemy>=2.0", "psycopg>=3.2"]

[dependency-groups]
dev = ["pytest>=8", "pytest-cov>=5", "diff-cover>=9", "ruff>=0.6", "mypy>=1.11"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["app"]
branch = true
EOF

eval_write .gitignore <<'EOF'
__pycache__/
.venv/
coverage.xml
.coverage
EOF

eval_write CONTEXT.md <<'EOF'
# billing-api

## Domain

- **Invoice**: what a customer owes for one billing period.
- **Refund**: money returned against a paid invoice, full or partial.
- **Search**: invoice lookup for the support console.
- **Account**: a customer and their payment settings.

## Engineering constraints

- The CI critical path (`checks` job) has a hard 10-minute cap: the deploy train
  leaves every 30 minutes and a PR must be mergeable within one train
  (docs/adr/0002-ci-ten-minute-cap.md). Today the job takes about 4 minutes.
- The suite is about 1,800 unit tests and runs in about 22 seconds locally.
- Coverage is gated at 78% of changed lines (diff-cover). It has not moved
  since it was introduced.

## Incidents

- **INC-41 (2026-09)**: partial refunds paid out the full invoice amount for two
  days. `test_partial_refund` existed and was green the whole time: it called
  `refund_amount()` and asserted nothing about the result. Coverage counted the
  line as covered.
EOF

eval_write docs/adr/0002-ci-ten-minute-cap.md <<'EOF'
# 2. The CI critical path stays under 10 minutes

Status: accepted

The deploy train leaves every 30 minutes. A PR that is approved must be able to
pass CI and catch the next train, so the `checks` job has `timeout-minutes: 10`
and anything slower runs on a schedule instead.
EOF

eval_write .github/workflows/ci.yml <<'EOF'
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  checks:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - name: Lint
        run: uv run ruff check .
      - name: Typecheck
        run: uv run mypy app
      - name: Test
        run: uv run pytest --cov=app --cov-report=xml
      - name: Coverage on changed lines
        run: uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=78
EOF

for pkg in app app/billing app/search app/accounts tests tests/billing tests/search tests/accounts; do
  eval_write "$pkg/__init__.py" </dev/null
done

eval_write app/billing/refunds.py <<'EOF'
from decimal import Decimal


def refund_amount(invoice_total: Decimal, already_refunded: Decimal, requested: Decimal | None) -> Decimal:
    """Amount to refund now. None means refund whatever is left."""
    remaining = invoice_total - already_refunded
    if remaining <= 0:
        raise ValueError("invoice is already fully refunded")
    if requested is None:
        return remaining
    if requested <= 0:
        raise ValueError(f"refund must be positive, got {requested}")
    if requested > remaining:
        raise ValueError(f"refund {requested} exceeds the remaining {remaining}")
    return requested
EOF

eval_write app/billing/invoices.py <<'EOF'
from decimal import ROUND_HALF_EVEN, Decimal


def line_total(unit_price: Decimal, quantity: int, tax_rate: Decimal) -> Decimal:
    subtotal = unit_price * quantity
    return (subtotal * (1 + tax_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def invoice_total(lines: list[tuple[Decimal, int, Decimal]]) -> Decimal:
    return sum((line_total(p, q, t) for p, q, t in lines), Decimal("0"))
EOF

eval_write app/search/ranking.py <<'EOF'
def rank(invoice_ids: list[str], query: str) -> list[str]:
    exact = [i for i in invoice_ids if i == query]
    prefix = [i for i in invoice_ids if i != query and i.startswith(query)]
    return exact + prefix
EOF

eval_write app/accounts/settings.py <<'EOF'
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentSettings:
    autopay: bool
    retry_failed_charges: bool

    def can_retry(self) -> bool:
        return self.autopay and self.retry_failed_charges
EOF

eval_write app/main.py <<'EOF'
from decimal import Decimal

from fastapi import FastAPI

from app.billing.refunds import refund_amount

app = FastAPI(title="billing-api")


@app.post("/invoices/{invoice_id}/refunds")
def create_refund(invoice_id: str, total: Decimal, refunded: Decimal, amount: Decimal | None = None) -> dict[str, str]:
    return {"invoice_id": invoice_id, "refund": str(refund_amount(total, refunded, amount))}
EOF

eval_write tests/billing/test_refunds.py <<'EOF'
import unittest
from decimal import Decimal

from app.billing.refunds import refund_amount


class RefundAmountTest(unittest.TestCase):
    def test_partial_refund(self) -> None:
        self.assertEqual(refund_amount(Decimal("100"), Decimal("0"), Decimal("30")), Decimal("30"))

    def test_full_refund_of_remainder(self) -> None:
        self.assertEqual(refund_amount(Decimal("100"), Decimal("40"), None), Decimal("60"))

    def test_rejects_over_refund(self) -> None:
        with self.assertRaises(ValueError):
            refund_amount(Decimal("100"), Decimal("90"), Decimal("20"))
EOF

eval_write tests/billing/test_invoices.py <<'EOF'
import unittest
from decimal import Decimal

from app.billing.invoices import invoice_total


class InvoiceTotalTest(unittest.TestCase):
    def test_totals_lines_with_tax(self) -> None:
        total = invoice_total([(Decimal("10.00"), 2, Decimal("0.08"))])
        self.assertTrue(total > 0)
EOF

eval_write tests/search/test_ranking.py <<'EOF'
import unittest

from app.search.ranking import rank


class RankTest(unittest.TestCase):
    def test_exact_before_prefix(self) -> None:
        self.assertEqual(rank(["INV-10", "INV-1", "INV-100"], "INV-1"), ["INV-1", "INV-10", "INV-100"])
EOF

eval_write tests/accounts/test_settings.py <<'EOF'
import unittest

from app.accounts.settings import PaymentSettings


class PaymentSettingsTest(unittest.TestCase):
    def test_retry_needs_autopay(self) -> None:
        PaymentSettings(autopay=False, retry_failed_charges=True).can_retry()
EOF

eval_commit "feat: billing api with changed-line coverage gate"
eval_origin
eval_gh
