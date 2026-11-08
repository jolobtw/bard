"""Arcane Header and status badges widget for Textual."""

from __future__ import annotations

from typing import List, Optional
from textual.widgets import Static
from rich.text import Text

from bard import __version__
from bard.arcane_theme import format_rich_header, load_theme


class ArcaneHeader(Static):
    """Renders the signature 2-row Arcane header with live badges."""

    DEFAULT_CSS = """
    ArcaneHeader {
        dock: top;
        height: 2;
        width: 100%;
        background: #13141C;
        color: #A6ADC8;
        padding: 0 1;
        margin-bottom: 1;
    }
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
        self.theme = load_theme()

    def update_status(self, is_playing: bool, device_name: Optional[str] = None) -> None:
        """Update playback state badges."""
        self.is_playing = is_playing
        if device_name:
            self.device_name = device_name
        self.refresh()

    def render(self) -> Text:
        """Render header with current badges."""
        width = self.size.width or 100
        play_badge = "󰐊 Playing" if self.is_playing else "󰏤 Paused"
        badges = [
            f"󰓇 {self.device_name}",
            "󰋋 320 kbps",
            play_badge,
        ]
        markup = format_rich_header(
            app_title="BARD",
            tagline="Arcane Spotify Player",
            badges=badges,
            width=width,
            theme=self.theme,
            version=self.version,
        )
        return Text.from_markup(markup)
