#!/usr/bin/env bash
# An empty directory (git repo with only an empty root commit) where the user
# wants a new Roblox game, obby-game. No Linear server is configured in any
# agent config and the case has no Linear mocks. The Luau toolchain (rojo,
# aftman, selene, stylua) is not on the run's system PATH, and installs under
# the real home can't be read from the sandbox, so `rojo init` will most
# likely fail here.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
