"""Zen Now-Playing Stage widget."""

from __future__ import annotations

from typing import Any, Dict, Optional
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from bard.art import render_album_art


def format_ms(ms: int) -> str:
    """Format milliseconds to mm:ss."""
    total_seconds = max(0, ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def render_flame_progress(progress_ms: int, duration_ms: int, width: int = 50) -> str:
    """Render a gradient flame progress bar with timestamps."""
    if duration_ms <= 0:
        pct = 0.0
    else:
        pct = min(1.0, max(0.0, progress_ms / duration_ms))

    curr_str = format_ms(progress_ms)
    total_str = format_ms(duration_ms)

    bar_width = max(10, width - len(curr_str) - len(total_str) - 4)
    filled_len = int(bar_width * pct)
    unfilled_len = bar_width - filled_len

    # Flame gradient: start #FF4500 -> end #FFD166
    if filled_len > 0:
        filled_bar = f"[#FF7A00]{'━' * max(0, filled_len - 1)}[#FFD166]●[/]"
    else:
        filled_bar = "[#FFD166]●[/]"
    unfilled_bar = f"[#2E3244]{'─' * max(0, unfilled_len)}[/]"

    return f"[#A6ADC8]{curr_str}[/]  {filled_bar}{unfilled_bar}  [#6C7086]{total_str}[/]"


class ZenStage(Widget):
    """The central Hero stage showcasing album art, track details, glowing progress, and transport controls."""

    DEFAULT_CSS = """
    ZenStage {
        width: 100%;
        height: 1fr;
        align: center middle;
        background: #13141C;
    }

    #stage-container {
        width: 84;
        height: auto;
        border: round #FF7A00;
        background: #181A24;
        padding: 1 2;
        align: center middle;
    }

    #art-box {
        width: auto;
        height: auto;
        margin-bottom: 1;
        content-align: center middle;
    }

    #track-title {
        text-align: center;
        text-style: bold;
        color: #FFFFFF;
        margin-bottom: 0;
    }

    #track-meta {
        text-align: center;
        color: #A6ADC8;
        margin-bottom: 1;
    }

    #progress-bar {
        text-align: center;
        margin-bottom: 1;
    }

    #transport-controls {
        text-align: center;
        margin-bottom: 1;
    }

    #controls-hint {
        text-align: center;
        color: #6C7086;
        margin-top: 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.playback_data: Optional[Dict[str, Any]] = None
        self._current_progress_ms: int = 0
        self._last_art_url: str = ""
        self._cached_art_ansi: str = ""

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="stage-container"):
                yield Static(id="art-box")
                yield Static(id="track-title")
                yield Static(id="track-meta")
                yield Static(id="progress-bar")
                yield Static(id="transport-controls")
                yield Static(id="controls-hint")

    def update_playback(self, data: Optional[Dict[str, Any]]) -> None:
        """Update stage with fresh playback data from Spotify."""
        self.playback_data = data
        if data:
            self._current_progress_ms = data.get("progress_ms", 0)
            art_url = data.get("album_art_url", "")
            if art_url != self._last_art_url or not self._cached_art_ansi:
                self._last_art_url = art_url
                self._cached_art_ansi = render_album_art(art_url, width=32, height=14)
        self.refresh_stage()

    def tick_progress(self, delta_ms: int = 1000) -> None:
        """Advance progress bar by delta if currently playing."""
        if self.playback_data and self.playback_data.get("is_playing"):
            duration = self.playback_data.get("duration_ms", 0)
            if duration > 0 and self._current_progress_ms < duration:
                self._current_progress_ms = min(duration, self._current_progress_ms + delta_ms)
                bar_widget = self.query_one("#progress-bar", Static)
                bar_widget.update(Text.from_markup(render_flame_progress(self._current_progress_ms, duration, width=52)))

    def refresh_stage(self) -> None:
        """Re-render stage widgets."""
        if not self.is_mounted:
            return

        art_widget = self.query_one("#art-box", Static)
        title_widget = self.query_one("#track-title", Static)
        meta_widget = self.query_one("#track-meta", Static)
        bar_widget = self.query_one("#progress-bar", Static)
        transport_widget = self.query_one("#transport-controls", Static)
        hint_widget = self.query_one("#controls-hint", Static)

        if not self.playback_data:
            art_widget.update(Text.from_ansi(render_album_art("", width=32, height=12)))
            title_widget.update("[bold #FF7A00]No Music Playing[/]")
            meta_widget.update(Text.assemble(("Press ", "#A6ADC8"), ("[Tab]", "bold #FFD166"), (" to browse your playlists", "#A6ADC8")))
            bar_widget.update("")
            transport_widget.update("[on #262938 #6C7086]  ⏮ Prev  [/]   [on #FF7A00 bold #FFFFFF]  ▶ Play  [/]   [on #262938 #6C7086]  ⏭ Next  [/]")
            hint_widget.update(Text.assemble(("[Tab] Playlists", "on #262938 bold #A6ADC8"), ("   ", ""), ("[Q] Quit", "on #262938 bold #A6ADC8")))
            return

        art_widget.update(Text.from_ansi(self._cached_art_ansi))
        title = self.playback_data.get("title", "Unknown")
        artist = self.playback_data.get("artist", "Unknown Artist")
        album = self.playback_data.get("album", "")
        duration = self.playback_data.get("duration_ms", 0)
        volume = self.playback_data.get("volume", 50)
        is_playing = self.playback_data.get("is_playing", False)
        device_name = self.playback_data.get("device_name", "PC Speakers")

        title_widget.update(f"[bold #FFFFFF]{title}[/]")
        meta_widget.update(f"[#A6ADC8]{artist}[/] [#6C7086]• {album}[/]")
        bar_widget.update(Text.from_markup(render_flame_progress(self._current_progress_ms, duration, width=52)))

        play_btn = "[on #FF7A00 bold #FFFFFF]  ⏸ Pause  [/]" if is_playing else "[on #FF7A00 bold #FFFFFF]  ▶ Play  [/]"
        transport_markup = (
            f"[on #262938 #FFD166]  ⏮ Prev [P]  [/]   "
            f"{play_btn}   "
            f"[on #262938 #FFD166]  ⏭ Next [N]  [/]   "
            f"[on #262938 #A6ADC8]  󰕾 {volume}% [- / +]  [/]"
        )
        transport_widget.update(transport_markup)

        hint_widget.update(
            Text.assemble(
                (f"Audio Output: {device_name}", "bold #FFD166"),
                ("   •   ", "#6C7086"),
                (" [Tab] Playlists ", "on #262938 bold #A6ADC8"),
                ("   ", ""),
                (" [Q] Quit ", "on #262938 bold #A6ADC8"),
            )
        )

    def on_mount(self) -> None:
        self.refresh_stage()
