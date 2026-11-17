"""Read-only command allowlist used to gate terminal-command approvals."""

from __future__ import annotations

import re
from collections.abc import Iterable

_SEPARATORS = re.compile(r"[;|&]+")
_UNSAFE = re.compile(r"[<>`]|\$\(")


def is_read_only_command(command: str, allowed: Iterable[str]) -> bool:
    """True when every pipeline/statement starts with an allowlisted command and nothing
    redirects output, runs a backtick, or uses command substitution."""
    if _UNSAFE.search(command):
        return False
    allowed_lower = {name.lower() for name in allowed}
    segments = [seg.split() for seg in _SEPARATORS.split(command)]
    segments = [seg for seg in segments if seg]
    if not segments:
        return False
    return all(seg[0].lower() in allowed_lower for seg in segments)
