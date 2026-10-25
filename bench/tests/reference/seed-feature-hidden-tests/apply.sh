#!/usr/bin/env bash
# Reference solution: settle-up payments (lib + API route + group page section + tests).
# Runs in the workspace; $REFERENCE_DIR is this dir.
set -euo pipefail
cp -R "$REFERENCE_DIR/files/." .
python3 - <<'PY'
from pathlib import Path

page = Path("src/app/groups/[groupId]/page.tsx")
src = page.read_text()
src = src.replace('import { formatCents } from "@/lib/money";\n',
                  'import { formatCents } from "@/lib/money";\nimport { settleUp } from "@/lib/settle";\n')
src = src.replace("  const balances = computeBalances(group);\n",
                  "  const balances = computeBalances(group);\n  const payments = settleUp(balances);\n")
section = '''      <h2>Settle up</h2>
      {payments.length === 0 ? (
        <p className="muted">Everyone&apos;s square.</p>
      ) : (
        <ul className="list">
          {payments.map((p) => (
            <li key={`${p.from}-${p.to}`}>
              <span>
                {names.get(p.from)} pays {names.get(p.to)}
              </span>
              <span className="amount">{formatCents(p.amountCents)}</span>
            </li>
          ))}
        </ul>
      )}

      <h2>Expenses</h2>
'''
src = src.replace("      <h2>Expenses</h2>\n", section, 1)
page.write_text(src)
PY
