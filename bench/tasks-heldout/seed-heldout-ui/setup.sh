#!/usr/bin/env bash
# Trusted, runs before the agent (and before the bench-base commit): install pinned deps
# and the Playwright Chromium they expect (a no-op when it's already in the shared cache).
set -euo pipefail
npm ci --no-audit --no-fund --loglevel=error
./node_modules/.bin/playwright install chromium >/dev/null
