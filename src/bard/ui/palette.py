"""Obsidian & Ember UI palette tokens and deterministic rune helpers for Bard."""

from __future__ import annotations

import hashlib

BG_OBSIDIAN = "#0D0E11"
BG_PANEL = "#14161A"
BG_ELEVATED = "#1B1E24"
BG_CURSOR = "#232832"
BG_ACTIVE_AMBER = "#2B1A0D"

BORDER_SLATE = "#2C323D"
BORDER_AMBER = "#FF7B00"

TEXT_MUTED = "#6E7787"
TEXT_MAIN = "#D4D9E3"

AMBER_DEEP = "#8F3900"
AMBER_CORE = "#FF7B00"
AMBER_GLOW = "#FF9E2C"
AMBER_PEAK = "#FFD28A"

RUNES = ("ᛟ", "ᛉ", "☉", "ᛗ", "ᛜ")


def track_rune(track_id: str) -> str:
    """Return a deterministic arcane rune for a track identifier."""
    cleaned = (track_id or "").strip()
    if not cleaned:
        return RUNES[0]
    digest = hashlib.blake2b(cleaned.encode("utf-8"), digest_size=2).digest()
    idx = int.from_bytes(digest, "big") % len(RUNES)
    return RUNES[idx]
