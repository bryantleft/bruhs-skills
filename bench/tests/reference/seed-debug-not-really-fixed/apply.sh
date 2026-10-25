#!/usr/bin/env bash
# Reference fix: two causes. (1) The stacking breakpoint was below every current phone
# width, so phones got two columns. (2) Even stacked, the long nowrap product name sets the
# grid track's and the flex item's minimum width (min-width: auto), so the single column
# is wider than the screen and the ellipsis never applies. Runs in the workspace.
set -euo pipefail
sed -i.bak 's/export const STACK_BELOW = 380;/export const STACK_BELOW = 640;/' src/layout.ts
sed -i.bak 's/repeat(${columns}, 1fr)/repeat(${columns}, minmax(0, 1fr))/' src/App.tsx
python3 - <<'PY'
from pathlib import Path
p = Path("src/styles.css")
s = p.read_text()
old = ".line-info {\n  flex: 1;\n}"
assert old in s
p.write_text(s.replace(old, ".line-info {\n  flex: 1;\n  min-width: 0;\n}"))
PY
rm -f src/layout.ts.bak src/App.tsx.bak
grep -q "STACK_BELOW = 640" src/layout.ts
grep -q "minmax(0, 1fr)" src/App.tsx
