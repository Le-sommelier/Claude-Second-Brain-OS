"""Verbatim guard for fetch bricks: flags text that looks summarised rather than copied.

Every formatter that persists external text (Slack, Confluence, owed replies) runs its payload
through `check()` and reports the warnings in its JSON result. The brick re-fetches on warning.
"""
from __future__ import annotations

import re

PATTERNS = [
    (r"\[(two|three|several|multiple|various|some|a few)\s+\w+\s+(links?|urls?|images?|files?|docs?|attachments?|messages?)\]",
     "bracketed summary of links/files"),
    (r"\[link\d* (?:to|and)", "bracketed link description"),
    (r"\[(summary|summarised|summarized|paraphrased|truncated|abbreviated)", "explicit summary marker"),
    (r"\[see (?:the )?(?:original|full)", "pointer instead of content"),
    (r"^\s*\[[^\]]{0,120}\]\s*$", "whole text is a bracketed placeholder"),
    (r"\[(?:body|content|outcome|text|message)[^\]]{0,60}\]", "bracketed placeholder for missing content"),
]


def check(items: list[tuple[str, str]]) -> list[str]:
    """items: (identifier, text) pairs. Returns human-readable warnings, empty when clean."""
    warnings = []
    for ident, text in items:
        text = text or ""
        for pattern, label in PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                warnings.append(f"{ident}: {label}")
                break
        else:
            if text.rstrip().endswith(("...", "…")) and len(text) < 500:
                warnings.append(f"{ident}: short text ending in an ellipsis — possible truncation")
    return warnings


def slack_texts(messages: list[dict]) -> list[tuple[str, str]]:
    """Flatten root messages and thread replies into (permalink, text) pairs."""
    out = []
    for m in messages or []:
        out.append((m.get("permalink", "<no-permalink>"), m.get("text", "")))
        for r in m.get("thread", []) or []:
            out.append((r.get("permalink", m.get("permalink", "<no-permalink>")), r.get("text", "")))
    return out
