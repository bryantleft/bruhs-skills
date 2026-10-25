#!/usr/bin/env bash
# Trusted, runs before the agent (and before the bench-base commit): install pinned deps.
set -euo pipefail
npm ci --no-audit --no-fund --loglevel=error
