"""Live-test helper: claude runs need a token (R20), which the user supplies."""

import pytest

from bruhsbench.homes import ClaudeAuthMissing, claude_auth


def need_claude_token(cli: str) -> None:
    """Skip a live claude test, with the setup instructions, when no token is configured."""
    if cli == "claude":
        try:
            claude_auth()
        except ClaudeAuthMissing as exc:
            pytest.skip(str(exc))
