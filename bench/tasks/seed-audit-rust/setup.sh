#!/usr/bin/env bash
# Trusted, runs before the agent (and before the bench-base commit). No crates.io deps;
# a warm target/ (gitignored) so the agent's first build is quick.
set -euo pipefail
cargo build --offline --locked --all-targets --quiet
