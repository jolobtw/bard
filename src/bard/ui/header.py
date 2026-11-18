"""Arcane Header and status badges widget for Textual."""

from __future__ import annotations

from typing import Any, Dict, Optional
from textual.widgets import Static
from rich.markup import escape as markup_escape
from rich.text import Text

from bard import __version__
from bard.arcane_theme import format_rich_header
from bard.ui.palette import (
    AMBER_CORE,
    AMBER_PEAK,
    BG_ELEVATED,
    BG_OBSIDIAN,
    BORDER_SLATE,
    TEXT_MAIN,
    TEXT_MUTED,
)

_HEADER_THEME: Dict[str, Any] = {
    "palette": {
        "text_muted": TEXT_MUTED,
    },
    "header": {
        "star_glyph": "✦",
        "star_color": AMBER_CORE,
        "title_glyph": "❖",
        "title_gradient": ["#FF4500", AMBER_PEAK],
        "separator_glyph": "❖",
        "separator_color": TEXT_MUTED,
        "tagline_color": TEXT_MUTED,
        "divider_glyph": "─",
        "divider_color": BORDER_SLATE,
    },
    "badges": {
        "background": BG_ELEVATED,
        "text_color": TEXT_MAIN,
    },
}


class ArcaneHeader(Static):
    """Renders the compact 2-row Bard header with live playback badges."""

    DEFAULT_CSS = f"""
    ArcaneHeader {{
        dock: top;
        height: 2;
        width: 100%;
        background: {BG_OBSIDIAN};
        color: {TEXT_MAIN};
        padding: 0 1;
        margin-bottom: 0;
    }}
    """

    def __init__(
        self,
        is_playing: bool = False,
        device_name: str = "Bard",
        version: Optional[str] = None,
    ):
        super().__init__()
        self.is_playing = is_playing
        self.device_name = device_name
        self.version = version or __version__

    def update_status(self, is_playing: bool, device_name: Optional[str] = None) -> None:
        """Update playback state badges."""
        self.is_playing = is_playing
        if device_name:
            self.device_name = device_name
        self.refresh()

    def render(self) -> Text:
        """Render header with truthful playback and source badges."""
        width = self.size.width or 100
        play_badge = "▶ Playing" if self.is_playing else "❚❚ Paused"
        badges = [
            f"◈ {markup_escape(self.device_name)}",
            play_badge,
        ]
        markup = format_rich_header(
            app_title="BARD",
            tagline="Arcane Music Player",
            badges=badges,
            width=width,
            theme=_HEADER_THEME,
            version=self.version,
        )
        return Text.from_markup(markup)
