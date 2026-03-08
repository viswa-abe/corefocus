"""Utility functions for corefocus."""

import re
from datetime import datetime, timezone


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def time_ago(iso_str: str) -> str:
    """Human-readable time delta from ISO timestamp to now."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - dt
    hours = int(diff.total_seconds() / 3600)
    if hours < 1:
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours:
        return f"{days}d {remaining_hours}h ago"
    return f"{days}d ago"


def format_timestamp() -> str:
    """Format current UTC time for note entries."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
