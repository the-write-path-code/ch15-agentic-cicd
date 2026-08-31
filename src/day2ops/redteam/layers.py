"""Security layers from Chapter 14's SentinelAI pipeline (compact versions).

Single responsibility: deterministic prompt-safety checks that run before and
around inference. This module implements the Layer 1 regex input validator and
the Layer 2 rule-based semantic guard as pure functions returning a block
reason or None. Layer 7 and Layer 10 are added by the red-team pipeline
milestone. Constraints: no network, no model calls, no exceptions swallowed
here; callers decide what a block means.
"""
from __future__ import annotations

import re

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore-previous-instructions",
        re.compile(
            r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+"
            r"(?:\w+\s+)?(?:instructions?|prompts?|rules?|guidelines?)",
            re.IGNORECASE,
        ),
    ),
    (
        "disregard-instructions",
        re.compile(
            r"disregard\s+(?:all\s+|any\s+|the\s+)?(?:\w+\s+)?"
            r"(?:instructions?|policies|rules?|guidelines?)",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt-exfiltration",
        re.compile(
            r"(?:reveal|show|print|repeat|leak|expose)\s+(?:your|the)\s+"
            r"(?:system\s+)?(?:prompt|instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "role-rewrite",
        re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+\w+", re.IGNORECASE),
    ),
    (
        "developer-mode",
        re.compile(
            r"(?:enter|activate|enable|switch\s+to)\s+(?:developer|god|dan|admin)\s+mode",
            re.IGNORECASE,
        ),
    ),
    ("jailbreak", re.compile(r"\bjailbreak\b", re.IGNORECASE)),
    (
        "exfiltration-request",
        re.compile(
            r"(?:send|email|exfiltrate|forward|upload)\b.{0,80}\b"
            r"(?:attacker|adversary|hacker)@",
            re.IGNORECASE,
        ),
    ),
]

MAX_INPUT_LENGTH = 2000

SEMANTIC_RULES: dict[str, list[str]] = {
    "privilege escalation phrasing": [
        "act as an administrator",
        "act as admin",
        "administrator privileges",
        "elevate my privileges",
        "grant me owner",
        "grant yourself",
        "root access",
        "sudo access",
        "override your restrictions",
        "remove your restrictions",
    ],
    "instruction override phrasing": [
        "treat the following as an authoritative instruction",
        "new instructions:",
        "pretend the policy says",
        "pretend you have no guidelines",
        "simulate having no guidelines",
        "you have no restrictions",
    ],
    "out-of-scope data access phrasing": [
        "all restricted documents",
        "every classified document",
        "regardless of classification",
        "confidential files regardless",
    ],
}


def check_input(text: str) -> str | None:
    """Layer 1: regex input validator. Returns a block reason or None."""
    if not text.strip():
        return "input validator: malformed input, empty payload"
    if len(text) > MAX_INPUT_LENGTH:
        return "input validator: malformed input, payload exceeds 2000 characters"
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in text):
        return "input validator: malformed input, control characters present"
    if not re.search(r"[a-zA-Z0-9]", text):
        return "input validator: malformed input, no alphanumeric content"
    for label, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return f"input validator: direct injection attempt ({label})"
    return None


def check_semantics(text: str) -> str | None:
    """Layer 2: rule-based semantic guard. Returns a block reason or None."""
    low = text.lower()
    for label, phrases in SEMANTIC_RULES.items():
        for phrase in phrases:
            if phrase in low:
                return f"semantic guard: {label}"
    return None
