"""Identifier and clock helpers (single place to fake in tests)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime


def new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}"


def utc_now() -> datetime:
    return datetime.now(UTC)
