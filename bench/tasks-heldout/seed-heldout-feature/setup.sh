#!/usr/bin/env bash
# Trusted, runs before the agent (and before the bench-base commit): create .venv with the
# locked deps. uv-managed Python only, so the venv's interpreter is one the sandbox can read.
set -euo pipefail
export UV_PYTHON_PREFERENCE=only-managed
uv sync --frozen --quiet
