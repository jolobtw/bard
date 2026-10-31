"""Zen Now-Playing Stage widget."""

from __future__ import annotations

from typing import Any, Dict, Optional
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.widget import Widget
from textual.widgets import Static

from bard.art import render_album_art


def format_ms(ms: int) -> str:
    """Format milliseconds to mm:ss."""
    total_seconds = max(0, ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def render_flame_progress(progress_ms: int, duration_ms: int, width: int = 40) -> str:
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
    filled_bar = f"[#FF7A00]{'━' * max(0, filled_len - 1)}[#FFD166]●[/]" if filled_len > 0 else "[#FFD166]●[/]"
    unfilled_bar = f"[#2E3244]{'─' * max(0, unfilled_len)}[/]"

    return f"[#6C7086]{curr_str}[/]  {filled_bar}{unfilled_bar}  [#6C7086]{total_str}[/]"


class ZenStage(Widget):
    """The central Hero stage showcasing album art, track details, and glowing progress."""

    DEFAULT_CSS = """
    ZenStage {
        width: 100%;
        height: 1fr;
        align: center middle;
        background: #13141C;
    }

    #stage-container {
        width: 80;
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

    #controls-hint {
        text-align: center;
        color: #6C7086;
        margin-top: 1;
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
                yield Static(id="controls-hint")

    def update_playback(self, data: Optional[Dict[str, Any]]) -> None:
        """Update stage with fresh playback data from Spotify."""
        self.playback_data = data
        if data:
            self._current_progress_ms = data.get("progress_ms", 0)
            art_url = data.get("album_art_url", "")
            if art_url != self._last_art_url or not self._cached_art_ansi:
                self._last_art_url = art_url
                self._cached_art_ansi = render_album_art(art_url, width=30, height=14)
        self.refresh_stage()

    def tick_progress(self, delta_ms: int = 1000) -> None:
        """Advance progress bar by delta if currently playing."""
        if self.playback_data and self.playback_data.get("is_playing"):
            duration = self.playback_data.get("duration_ms", 0)
            if duration > 0 and self._current_progress_ms < duration:
                self._current_progress_ms = min(duration, self._current_progress_ms + delta_ms)
                bar_widget = self.query_one("#progress-bar", Static)
                bar_widget.update(Text.from_markup(render_flame_progress(self._current_progress_ms, duration, width=48)))

    def refresh_stage(self) -> None:
        """Re-render stage widgets."""
        if not self.is_mounted:
            return

        art_widget = self.query_one("#art-box", Static)
        title_widget = self.query_one("#track-title", Static)
        meta_widget = self.query_one("#track-meta", Static)
        bar_widget = self.query_one("#progress-bar", Static)
        hint_widget = self.query_one("#controls-hint", Static)

        if not self.playback_data:
            art_widget.update(Text.from_ansi(render_album_art("", width=30, height=12)))
            title_widget.update("[bold #FF7A00]No Music Playing[/]")
            meta_widget.update("[#A6ADC8]Press [bold #FFD166]\\[Tab][/] to browse playlists[/]\n[#6C7086]Open Spotify on any device (PC, web, or phone) to output sound[/]")
            bar_widget.update("")
            hint_widget.update("[on #262938 #A6ADC8] \\[Tab] Playlists [/]   [on #262938 #A6ADC8] \\[Q] Quit [/]")
            return

        art_widget.update(Text.from_ansi(self._cached_art_ansi))
        title = self.playback_data.get("title", "Unknown")
        artist = self.playback_data.get("artist", "Unknown Artist")
        album = self.playback_data.get("album", "")
        duration = self.playback_data.get("duration_ms", 0)
        volume = self.playback_data.get("volume", 50)
        is_playing = self.playback_data.get("is_playing", False)

        play_icon = "󰐊" if is_playing else "󰏤"
        title_widget.update(f"[bold #FFFFFF]{title}[/]")
        meta_widget.update(f"[#A6ADC8]{artist}[/] [#6C7086]• {album}[/]")
        bar_widget.update(Text.from_markup(render_flame_progress(self._current_progress_ms, duration, width=48)))
        hint_widget.update(
            f"[#FFD166]󰕾 {volume}%[/]   "
            f"[on #262938 #A6ADC8] [Space] {play_icon} [/]  "
            f"[on #262938 #A6ADC8] [N] Next [/]  "
            f"[on #262938 #A6ADC8] [P] Prev [/]  "
            f"[on #262938 #A6ADC8] [Tab] Playlists [/]  "
            f"[on #262938 #A6ADC8] [Q] Quit [/]"
        )

    def on_mount(self) -> None:
        self.refresh_stage()
