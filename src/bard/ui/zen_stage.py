"""Zen Now-Playing Stage widget."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Static

from bard.arcane_theme import load_theme, render_rich_gradient
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
        width: 86;
        max-width: 96%;
        height: auto;
        border: round #FF7A00;
        background: #181A24;
        padding: 1 2;
        align-horizontal: center;
    }

    #art-center {
        width: 100%;
        height: auto;
        content-align: center middle;
        margin-bottom: 1;
    }

    #art-box {
        width: auto;
        height: auto;
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
        width: 100%;
        height: auto;
        align: center middle;
        margin-bottom: 1;
    }

    .transport-btn {
        width: auto;
        min-width: 10;
        height: 3;
        background: #1B1E2B;
        color: #CDD6F4;
        border: round #363B54;
        padding: 0 2;
        margin: 0 1;
        text-style: none;
        content-align: center middle;
    }

    .transport-btn:hover {
        background: #25293A;
        color: #FFFFFF;
        border: round #FFD166;
    }

    .transport-btn:focus {
        border: round #FF7A00;
        text-style: bold;
    }

    #btn-play {
        min-width: 13;
        color: #FFD166;
        border: round #4B5273;
    }

    #btn-play.-playing {
        background: #2A1D16;
        color: #FFD166;
        border: round #FF7A00;
        text-style: bold;
    }

    #btn-shuffle.-active {
        background: #2A1D16;
        color: #FFD166;
        border: round #FF7A00;
        text-style: bold;
    }

    #status-bar {
        text-align: center;
        margin-bottom: 1;
    }

    #controls-hint {
        text-align: center;
        color: #6C7086;
        margin-top: 0;
    }
    """

    def __init__(
        self,
        on_prev: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_shuffle: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.shuffle_enabled: bool = False
        self.playback_data: Optional[Dict[str, Any]] = None
        self._current_progress_ms: int = 0
        self._last_art_url: str = ""
        self._cached_art_ansi: str = ""
        self._last_rendered_dims: Optional[Tuple[int, int]] = None
        self.device_name: Optional[str] = None

    def set_shuffle(self, enabled: bool) -> None:
        """Update shuffle toggle state and refresh transport button styling."""
        self.shuffle_enabled = enabled
        self.refresh_stage()

    def get_art_dimensions(self) -> Tuple[int, int]:
        """Compute responsive album art dimensions based on current widget/screen dimensions."""
        width = self.size.width
        height = self.size.height
        if not width or not height:
            if self.app:
                width = width or self.app.size.width
                height = height or self.app.size.height
        if height < 32 or width < 86:
            return (32, 14)
        if height >= 44 and width >= 110:
            return (58, 25)
        return (46, 20)

    def on_resize(self, event: Any = None) -> None:
        """Handle resize to adapt album art dimensions dynamically."""
        if self.playback_data:
            art_w, art_h = self.get_art_dimensions()
            if self._last_rendered_dims != (art_w, art_h):
                art_url = self.playback_data.get("album_art_url", "")
                self._last_rendered_dims = (art_w, art_h)
                self._cached_art_ansi = render_album_art(art_url, width=art_w, height=art_h)
                if self.is_mounted:
                    try:
                        art_widget = self.query_one("#art-box", Static)
                        art_widget.update(Text.from_ansi(self._cached_art_ansi))
                    except Exception:
                        pass

    def set_device_name(self, name: Optional[str]) -> None:
        """Update active output device name."""
        self.device_name = name
        if self.is_mounted and not self.playback_data:
            try:
                status_widget = self.query_one("#status-bar", Static)
                if name:
                    status_widget.update(f"[#6C7086]Ready to stream • {name}[/]")
                else:
                    status_widget.update("[#6C7086]Ready to stream • YouTube Music / Standalone[/]")
            except Exception:
                pass

    def update_track(self, track: Optional[Dict[str, Any]]) -> None:
        """Update stage with a newly selected track dictionary."""
        if track:
            data = dict(self.playback_data) if self.playback_data else {}
            data.update(track)
            if "duration_ms" not in data and "duration_seconds" in data:
                data["duration_ms"] = (data.get("duration_seconds") or 0) * 1000
            data["is_playing"] = data.get("is_playing", True)
            data["progress_ms"] = data.get("progress_ms", 0)
            if "device_name" not in data:
                data["device_name"] = self.device_name or "YouTube Music / Standalone"
            self.update_playback(data)
        else:
            self.update_playback(None)

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="stage-container"):
                with Center(id="art-center"):
                    yield Static(id="art-box")
                yield Static(id="track-title")
                yield Static(id="track-meta")
                yield Static(id="progress-bar")
                with Horizontal(id="transport-controls"):
                    yield Button("⇄ Shuffle", id="btn-shuffle", classes="transport-btn")
                    yield Button("⏮ Prev", id="btn-prev", classes="transport-btn")
                    yield Button("▶ Resume", id="btn-play", classes="transport-btn")
                    yield Button("Next ⏭", id="btn-next", classes="transport-btn")
                yield Static(id="status-bar")
                yield Static(id="controls-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle clicks on modern transport control buttons."""
        btn_id = event.button.id
        event.stop()
        if btn_id == "btn-shuffle":
            if self.on_shuffle:
                self.on_shuffle()
            elif self.app and hasattr(self.app, "action_toggle_shuffle"):
                self.app.action_toggle_shuffle()
        elif btn_id == "btn-prev":
            if self.on_prev:
                self.on_prev()
            elif self.app and hasattr(self.app, "action_prev_track"):
                self.app.action_prev_track()
        elif btn_id == "btn-play":
            if self.on_play_pause:
                self.on_play_pause()
            elif self.app and hasattr(self.app, "action_toggle_playback"):
                self.app.action_toggle_playback()
        elif btn_id == "btn-next":
            if self.on_next:
                self.on_next()
            elif self.app and hasattr(self.app, "action_next_track"):
                self.app.action_next_track()

    def update_playback(self, data: Optional[Dict[str, Any]]) -> None:
        """Update stage with fresh playback data from YouTube Music or Spotify."""
        self.playback_data = data
        if data:
            self._current_progress_ms = data.get("progress_ms", 0)
            art_url = data.get("album_art_url", "")
            art_w, art_h = self.get_art_dimensions()
            needs_render = (
                art_url != self._last_art_url
                or not self._cached_art_ansi
                or ("ARCANE RESONANCE" in self._cached_art_ansi and art_url)
                or self._last_rendered_dims != (art_w, art_h)
            )
            if needs_render:
                self._last_art_url = art_url
                self._last_rendered_dims = (art_w, art_h)
                self._cached_art_ansi = render_album_art(art_url, width=art_w, height=art_h)
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

        art_center = self.query_one("#art-center")
        art_widget = self.query_one("#art-box", Static)
        title_widget = self.query_one("#track-title", Static)
        meta_widget = self.query_one("#track-meta", Static)
        bar_widget = self.query_one("#progress-bar", Static)
        shuffle_btn = self.query_one("#btn-shuffle", Button)
        play_btn = self.query_one("#btn-play", Button)
        status_widget = self.query_one("#status-bar", Static)
        hint_widget = self.query_one("#controls-hint", Static)

        if self.shuffle_enabled:
            shuffle_btn.add_class("-active")
            shuffle_btn.label = "⇄ Shuffle •"
        else:
            shuffle_btn.remove_class("-active")
            shuffle_btn.label = "⇄ Shuffle"

        hint_text = Text.assemble(
            ("Tab", "bold #FFD166"),
            (" Explore", "#6C7086"),
            ("   •   ", "#2E3244"),
            ("Space", "bold #FFD166"),
            (" Play/Pause", "#6C7086"),
            ("   •   ", "#2E3244"),
            ("S", "bold #FFD166"),
            (" Shuffle", "#6C7086"),
            ("   •   ", "#2E3244"),
            ("Q", "bold #FFD166"),
            (" Quit", "#6C7086"),
        )

        if not self.playback_data:
            art_center.display = False
            art_widget.update("")
            theme = load_theme()
            palette = theme.get("palette", {})
            start_color = palette.get("gradient_start", "#FF4500")
            end_color = palette.get("gradient_end", "#FFD166")
            title_widget.update(render_rich_gradient("Select Music", start_color, end_color))
            meta_widget.update(
                Text.assemble(
                    ("Summon your library with ", "#A6ADC8"),
                    ("[Tab]", "bold #FFD166"),
                    (" or press ", "#A6ADC8"),
                    ("[Space]", "bold #FFD166"),
                    (" to resume", "#A6ADC8"),
                )
            )
            bar_widget.update("")
            play_btn.label = "▶ Resume"
            play_btn.remove_class("-playing")
            if self.device_name:
                status_widget.update(f"[#6C7086]Ready to stream • {self.device_name}[/]")
            else:
                status_widget.update("[#6C7086]Ready to stream • YouTube Music / Standalone[/]")
            hint_widget.update(hint_text)
            return

        art_center.display = True
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

        if is_playing:
            play_btn.label = "⏸ Pause"
            play_btn.add_class("-playing")
        else:
            play_btn.label = "▶ Play"
            play_btn.remove_class("-playing")

        # Dedicated status strip: volume & audio engine
        status_markup = (
            f"[#6C7086]Volume:[/] [bold #FFD166]{volume}%[/] [#6C7086][- / +][/]     "
            f"[#2E3244]•[/]     "
            f"[#6C7086]Audio Engine:[/] [bold #FFD166]{device_name}[/]"
        )
        status_widget.update(status_markup)

        # Bottom navigation keycaps
        hint_widget.update(hint_text)

    def on_mount(self) -> None:
        self.refresh_stage()
