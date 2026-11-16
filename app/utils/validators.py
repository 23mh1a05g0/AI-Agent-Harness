"""Validation utilities for guardrails and API safety."""

import re
from typing import Tuple, Optional


def check_bulk_intent(prompt: str) -> Tuple[bool, Optional[str]]:
    """Detect if a user prompt attempts a bulk destructive mutation.

    Returns:
        (is_bulk, reason)
    """
    cleaned = prompt.lower()

    bulk_patterns = [
        r"\b(purge|delete|remove|erase|drop|clear)\s+(all|everything|entire|every)\b",
        r"\b(all|everything|entire)\b.*\b(purge|delete|remove|clear)\b",
        r"\bpurge\s+immediately\s+without\s+asking\b",
        r"\bdelete\s+immediately\s+without\s+asking\b",
        r"\bwithout\s+confirmation\b",
        r"\bmass\s+(deletion|purge|update)\b",
    ]

    for pattern in bulk_patterns:
        if re.search(pattern, cleaned):
            return True, f"Bulk destructive command detected matching pattern: {pattern}"

    return False, None
