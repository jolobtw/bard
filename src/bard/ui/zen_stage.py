"""Zen Now-Playing Stage widget with Sixel/TGP HD art and horizontal mock-style dock."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from bard.arcane_theme import DEFAULT_THEME, hex_to_rgb, interpolate_rgb, load_theme, render_rich_gradient
from bard.art import render_album_art

_DOCK_BG_ANSI = "\x1b[48;2;24;26;36m"  # #181A24
_PALETTE = DEFAULT_THEME["palette"]
_GRAD_START_RGB = hex_to_rgb(_PALETTE.get("gradient_start", "#FF4500"))
_GRAD_END_RGB = hex_to_rgb(_PALETTE.get("gradient_end", "#FFD166"))
_TRACK_MUTED_HEX = _PALETTE.get("border_muted", "#2E3244")
_THUMB_GOLD_HEX = _PALETTE.get("accent_gold", "#FFD166")


def render_arcane_bar(filled: int, unfilled: int) -> str:
    """Render an Arcane flame-to-gold gradient bar anchored to the full bar width."""
    total = max(1, filled + unfilled)
    parts = []
    if filled > 0:
        for i in range(filled):
            factor = i / total
            color = interpolate_rgb(_GRAD_START_RGB, _GRAD_END_RGB, factor)
            parts.append(f"[{color}]━[/]")
    thumb_color = interpolate_rgb(_GRAD_START_RGB, _GRAD_END_RGB, filled / total)
    parts.append(f"[bold {thumb_color}]●[/]")
    if unfilled > 0:
        parts.append(f"[{_TRACK_MUTED_HEX}]{'─' * unfilled}[/]")
    return "".join(parts)


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
    bar = render_arcane_bar(max(0, filled_len - 1), max(0, unfilled_len))

    return f"[#A6ADC8]{curr_str}[/]  {bar}  [#6C7086]{total_str}[/]"


def _render_play_pill_row(
    is_playing: bool,
    is_active: bool,
    hovered: bool,
) -> str:
    """Render a smooth Nerd Font Powerline-capped Play/Pause pill."""
    if is_playing or hovered:
        pill_rgb = (255, 146, 43) if hovered else (255, 122, 0)  # #FF922B / #FF7A00
        icon_rgb = (19, 20, 28)  # #13141C
    elif is_active:
        pill_rgb = (38, 41, 56)  # #262938
        icon_rgb = (255, 209, 102)  # #FFD166
    else:
        pill_rgb = (38, 41, 56)
        icon_rgb = (166, 173, 200)  # #A6ADC8

    bg_rgb = (24, 26, 36)  # #181A24
    cap = f"\x1b[38;2;{pill_rgb[0]};{pill_rgb[1]};{pill_rgb[2]}m\x1b[48;2;{bg_rgb[0]};{bg_rgb[1]};{bg_rgb[2]}m"
    inner = f"\x1b[38;2;{icon_rgb[0]};{icon_rgb[1]};{icon_rgb[2]}m\x1b[48;2;{pill_rgb[0]};{pill_rgb[1]};{pill_rgb[2]}m"
    rst = "\x1b[0m"

    glyph = "󰏤" if is_playing else "󰐊"
    return f"{cap}\ue0b6{inner}  {glyph}  {cap}\ue0b4{rst}"


class TransportBar(Widget):
    """Custom mouse-hit-tested transport bar: Prev, Play/Pause Pill, Next; Shuffle & Repeat below."""

    DEFAULT_CSS = """
    TransportBar {
        width: 17;
        height: 4;
        background: #181A24;
    }
    """

    # Row 1 (top): [0..3] Prev, [5..11] Play Pill, [13..16] Next
    # Row 2: blank spacer
    # Row 3 (bottom): [5..7] Shuffle, [9..11] Repeat
    TOP_ZONES = (
        ("prev", 0, 4),
        ("play", 5, 12),
        ("next", 13, 17),
    )
    BOTTOM_ZONES = (
        ("shuffle", 5, 8),
        ("repeat", 9, 12),
    )

    def __init__(
        self,
        on_prev: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_shuffle: Optional[Callable[[], None]] = None,
        on_repeat: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.on_repeat = on_repeat
        self.is_playing: bool = False
        self.has_track: bool = False
        self.shuffle_enabled: bool = False
        self.repeat_mode: str = "off"
        self._hover_zone: Optional[str] = None

    def set_state(
        self,
        is_playing: bool,
        has_track: bool,
        shuffle_enabled: bool,
        repeat_mode: str = "off",
    ) -> None:
        if (
            self.is_playing == is_playing
            and self.has_track == has_track
            and self.shuffle_enabled == shuffle_enabled
            and self.repeat_mode == repeat_mode
        ):
            return
        self.is_playing = is_playing
        self.has_track = has_track
        self.shuffle_enabled = shuffle_enabled
        self.repeat_mode = repeat_mode
        self.refresh()

    def _zone_at(self, x: int, y: int) -> Optional[str]:
        if y == 1:
            zones = self.TOP_ZONES
        elif y == 3:
            zones = self.BOTTOM_ZONES
        else:
            return None
        for name, start, end in zones:
            if start <= x < end:
                return name
        return None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        zone = self._zone_at(event.x, event.y)
        if zone != self._hover_zone:
            self._hover_zone = zone
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hover_zone is not None:
            self._hover_zone = None
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        zone = self._zone_at(event.x, event.y)
        if not zone:
            return
        event.stop()
        if zone == "prev" and self.on_prev:
            self.on_prev()
        elif zone == "play" and self.on_play_pause:
            self.on_play_pause()
        elif zone == "next" and self.on_next:
            self.on_next()
        elif zone == "shuffle" and self.on_shuffle:
            self.on_shuffle()
        elif zone == "repeat" and self.on_repeat:
            self.on_repeat()

    def render(self) -> Text:
        pill = _render_play_pill_row(
            is_playing=self.is_playing,
            is_active=self.has_track,
            hovered=(self._hover_zone == "play"),
        )

        prev_rgb = (255, 255, 255) if self._hover_zone == "prev" else (166, 173, 200)
        next_rgb = (255, 255, 255) if self._hover_zone == "next" else (166, 173, 200)
        if self._hover_zone == "shuffle":
            shuf_rgb = (255, 209, 102)
        elif self.shuffle_enabled:
            shuf_rgb = (255, 122, 0)
        else:
            shuf_rgb = (108, 112, 134)

        if self._hover_zone == "repeat":
            rep_rgb = (255, 255, 255) if self.repeat_mode == "one" else (255, 209, 102)
        elif self.repeat_mode == "one":
            rep_rgb = (255, 209, 102)
        elif self.repeat_mode == "all":
            rep_rgb = (255, 122, 0)
        else:
            rep_rgb = (108, 112, 134)

        rep_glyph = "󰑘" if self.repeat_mode == "one" else "󰑖"

        def _fg(rgb: Tuple[int, int, int]) -> str:
            return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{_DOCK_BG_ANSI}"

        rst = "\x1b[0m"
        gap = f"{_DOCK_BG_ANSI} {rst}"

        blank = f"{_DOCK_BG_ANSI}{' ' * 17}{rst}"
        line1 = (
            f"{_fg(prev_rgb)} 󰒮  {rst}"
            f"{gap}{pill}{gap}"
            f"{_fg(next_rgb)}  󰒭 {rst}"
        )
        line3 = (
            f"{_DOCK_BG_ANSI}     {rst}"
            f"{_fg(shuf_rgb)} 󰒟 {rst}"
            f"{gap}"
            f"{_fg(rep_rgb)} {rep_glyph} {rst}"
            f"{_DOCK_BG_ANSI}     {rst}"
        )
        return Text.from_ansi(f"{blank}\n{line1}\n{blank}\n{line3}")


class VolumeBar(Widget):
    """Right-side clickable volume slider with clickable speaker mute/unmute icon."""

    DEFAULT_CSS = """
    VolumeBar {
        width: 22;
        height: 3;
        background: #181A24;
    }
    """

    def __init__(
        self,
        on_volume: Optional[Callable[[int], None]] = None,
        on_mute: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.on_volume = on_volume
        self.on_mute = on_mute
        self.volume: int = 100
        self.device_name: str = "YouTube Music"
        self._hover_icon: bool = False

    def set_state(self, volume: int, device_name: str = "") -> None:
        new_vol = max(0, min(100, int(volume)))
        if new_vol == self.volume and (not device_name or device_name == self.device_name):
            return
        self.volume = new_vol
        if device_name:
            self.device_name = device_name
        self.refresh()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        over_icon = event.x < 3
        if over_icon != self._hover_icon:
            self._hover_icon = over_icon
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hover_icon:
            self._hover_icon = False
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        if event.x < 3:
            if self.on_mute:
                self.on_mute()
            return
        if event.x >= 3:
            bar_x = event.x - 3
            bar_w = 18
            pct = max(0, min(100, round((bar_x / (bar_w - 1)) * 100)))
            if self.on_volume:
                self.on_volume(pct)

    def render(self) -> Text:
        is_muted = self.volume == 0
        if is_muted:
            speaker = "[bold #FF7A00]󰖁[/]"
        elif self._hover_icon:
            speaker = "[bold #FFD166]󰕾[/]"
        else:
            speaker = "[#A6ADC8]󰕾[/]"

        bar_w = 18
        filled = round((self.volume / 100.0) * (bar_w - 1))
        unfilled = (bar_w - 1) - filled
        slider = render_arcane_bar(filled, unfilled)
        line1 = f" {speaker} {slider}"
        return Text.from_markup(f"\n{line1}\n")


class SeekBar(Widget):
    """Full-width clickable seek bar with compact mm:ss/mm:ss timestamp on the right."""

    DEFAULT_CSS = """
    SeekBar {
        width: 100%;
        height: 1;
        background: #181A24;
        margin-top: 1;
    }
    """

    def __init__(self, on_seek: Optional[Callable[[float], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_seek = on_seek
        self.progress_ms: int = 0
        self.duration_ms: int = 0

    def set_progress(self, progress_ms: int, duration_ms: int) -> None:
        self.progress_ms = max(0, progress_ms)
        self.duration_ms = max(0, duration_ms)
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        if event.y == 0 and self.duration_ms > 0 and self.on_seek:
            w = max(20, self.size.width or 80)
            bar_w = max(10, w - 13)
            pct = min(1.0, max(0.0, event.x / max(1, bar_w - 1)))
            target_sec = (self.duration_ms / 1000.0) * pct
            event.stop()
            self.on_seek(target_sec)

    def render(self) -> Text:
        w = max(24, self.size.width or 80)
        curr_str = format_ms(self.progress_ms)
        total_str = format_ms(self.duration_ms)
        ts_plain = f"{curr_str} / {total_str}"
        bar_w = max(10, w - len(ts_plain) - 2)

        pct = min(1.0, max(0.0, self.progress_ms / self.duration_ms)) if self.duration_ms > 0 else 0.0
        filled = int((bar_w - 1) * pct)
        unfilled = max(0, (bar_w - 1) - filled)
        bar_line = render_arcane_bar(filled, unfilled)
        return Text.from_markup(f"{bar_line}  [bold #FF7A00]{curr_str}[/][#6C7086] / {total_str}[/]")


class ZenStage(Widget):
    """The central Hero stage showcasing Sixel HD album art and a horizontal mock-style dock."""

    DEFAULT_CSS = """
    ZenStage {
        width: 100%;
        height: 1fr;
        align: center middle;
        background: #13141C;
    }

    #stage-container {
        width: 100;
        max-width: 98%;
        height: auto;
        background: #13141C;
        padding: 0 1;
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
        border: inner #FF7A00;
        background: #13141C;
    }

    #player-dock {
        width: 100%;
        height: 8;
        background: #181A24;
        border: round #2E3244;
        padding: 0 2;
    }

    #dock-top-row {
        width: 100%;
        height: 4;
        align: center middle;
    }

    #dock-meta {
        width: 1fr;
        height: 100%;
        padding-right: 2;
        align: left middle;
    }

    #dock-right {
        width: 1fr;
        height: 100%;
        align: right middle;
    }

    #track-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: #FFFFFF;
    }

    #track-meta {
        width: 100%;
        height: 1;
        color: #A6ADC8;
    }

    #track-source {
        width: 100%;
        height: 1;
        color: #6C7086;
    }

    #controls-hint {
        text-align: center;
        color: #6C7086;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        on_prev: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_shuffle: Optional[Callable[[], None]] = None,
        on_repeat: Optional[Callable[[], None]] = None,
        on_seek: Optional[Callable[[float], None]] = None,
        on_volume: Optional[Callable[[int], None]] = None,
        on_mute: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.on_repeat = on_repeat
        self.on_seek = on_seek
        self.on_volume = on_volume
        self.on_mute = on_mute
        self.shuffle_enabled: bool = False
        self.repeat_mode: str = "off"
        self.playback_data: Optional[Dict[str, Any]] = None
        self._current_progress_ms: int = 0
        self._last_art_url: str = ""
        self._cached_art_ansi: str = ""
        self._last_rendered_dims: Optional[Tuple[int, int]] = None
        self.device_name: Optional[str] = None
        self._last_title: str = ""
        self._last_meta: str = ""
        self._last_source: str = ""
        self._last_art_drawn: str = ""
        self._hint_initialized: bool = False
        self._full_title: str = ""
        self._marquee_offset: int = 0
        self._marquee_pause: int = 8
        self._marquee_end_pause: int = 0
        self._marquee_timer: Any = None

    def set_shuffle(self, enabled: bool) -> None:
        """Update shuffle toggle state and refresh transport controls."""
        self.shuffle_enabled = enabled
        self._sync_transport()

    def set_repeat(self, mode: str) -> None:
        """Update repeat mode ('off', 'all', 'one') and refresh transport controls."""
        self.repeat_mode = mode if mode in ("off", "all", "one") else "off"
        self._sync_transport()

    def _sync_transport(self) -> None:
        if self.is_mounted:
            try:
                transport = self.query_one("#transport-controls", TransportBar)
                is_playing = bool(self.playback_data and self.playback_data.get("is_playing", False))
                transport.set_state(
                    is_playing=is_playing,
                    has_track=bool(self.playback_data),
                    shuffle_enabled=self.shuffle_enabled,
                    repeat_mode=self.repeat_mode,
                )
                return
            except Exception:
                pass
        self.refresh_stage()

    def update_volume(self, volume: int) -> None:
        """Update only the volume slider without touching artwork or layout."""
        if self.is_mounted:
            try:
                self.query_one("#volume-control", VolumeBar).set_state(volume=volume)
            except Exception:
                pass

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
                        self._last_art_drawn = self._cached_art_ansi
                    except Exception:
                        pass

    def set_device_name(self, name: Optional[str]) -> None:
        """Update active output device name."""
        self.device_name = name
        if self.is_mounted:
            self.refresh_stage()

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
                data["device_name"] = self.device_name or "YouTube Music"
            self.update_playback(data)
        else:
            self.update_playback(None)

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="stage-container"):
                with Center(id="art-center"):
                    yield Static(id="art-box")
                with Vertical(id="player-dock"):
                    with Horizontal(id="dock-top-row"):
                        with Vertical(id="dock-meta"):
                            yield Static(id="track-title")
                            yield Static(id="track-meta")
                            yield Static(id="track-source")
                        yield TransportBar(
                            on_prev=self._handle_prev,
                            on_play_pause=self._handle_play_pause,
                            on_next=self._handle_next,
                            on_shuffle=self._handle_shuffle,
                            on_repeat=self._handle_repeat,
                            id="transport-controls",
                        )
                        with Horizontal(id="dock-right"):
                            yield VolumeBar(
                                on_volume=self._handle_volume,
                                on_mute=self._handle_mute,
                                id="volume-control",
                            )
                    yield SeekBar(on_seek=self._handle_seek, id="progress-bar")
                yield Static(id="controls-hint")

    def _handle_prev(self) -> None:
        if self.on_prev:
            self.on_prev()
        elif self.app and hasattr(self.app, "action_prev_track"):
            self.app.action_prev_track()

    def _handle_play_pause(self) -> None:
        if self.on_play_pause:
            self.on_play_pause()
        elif self.app and hasattr(self.app, "action_toggle_playback"):
            self.app.action_toggle_playback()

    def _handle_next(self) -> None:
        if self.on_next:
            self.on_next()
        elif self.app and hasattr(self.app, "action_next_track"):
            self.app.action_next_track()

    def _handle_shuffle(self) -> None:
        if self.on_shuffle:
            self.on_shuffle()
        elif self.app and hasattr(self.app, "action_toggle_shuffle"):
            self.app.action_toggle_shuffle()

    def _handle_repeat(self) -> None:
        if self.on_repeat:
            self.on_repeat()
        elif self.app and hasattr(self.app, "action_cycle_repeat"):
            self.app.action_cycle_repeat()

    def _handle_seek(self, position_seconds: float) -> None:
        if self.on_seek:
            self.on_seek(position_seconds)
        elif self.app and hasattr(self.app, "action_seek_to"):
            self.app.action_seek_to(position_seconds)

    def _handle_volume(self, volume: int) -> None:
        if self.on_volume:
            self.on_volume(volume)
        elif self.app and hasattr(self.app, "action_set_volume"):
            self.app.action_set_volume(volume)

    def _handle_mute(self) -> None:
        if self.on_mute:
            self.on_mute()
        elif self.app and hasattr(self.app, "action_toggle_mute"):
            self.app.action_toggle_mute()

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
        else:
            self._last_art_url = ""
            self._cached_art_ansi = ""
        self.refresh_stage()

    def update_progress(self, progress_ms: int, duration_ms: int) -> None:
        """Update only the seek bar without re-rendering album art or dock layout."""
        self._current_progress_ms = max(0, progress_ms)
        if self.is_mounted:
            try:
                self.query_one("#progress-bar", SeekBar).set_progress(self._current_progress_ms, duration_ms)
            except Exception:
                pass

    def tick_progress(self, delta_ms: int = 1000) -> None:
        """Advance progress bar by delta if currently playing."""
        if self.playback_data and self.playback_data.get("is_playing"):
            duration = self.playback_data.get("duration_ms", 0)
            if duration > 0 and self._current_progress_ms < duration:
                self.update_progress(min(duration, self._current_progress_ms + delta_ms), duration)

    def refresh_stage(self) -> None:
        """Re-render stage widgets."""
        if not self.is_mounted:
            return

        art_center = self.query_one("#art-center")
        art_widget = self.query_one("#art-box", Static)
        title_widget = self.query_one("#track-title", Static)
        meta_widget = self.query_one("#track-meta", Static)
        source_widget = self.query_one("#track-source", Static)
        transport = self.query_one("#transport-controls", TransportBar)
        volume_bar = self.query_one("#volume-control", VolumeBar)
        seek_bar = self.query_one("#progress-bar", SeekBar)
        hint_widget = self.query_one("#controls-hint", Static)

        if not self._hint_initialized:
            hint_widget.update(
                Text.assemble(
                    ("[Tab]", "bold #FF7A00"),
                    (" Explore", "#6C7086"),
                    (" • ", "#2E3244"),
                    ("[Space]", "bold #FF7A00"),
                    (" Play/Pause", "#6C7086"),
                    (" • ", "#2E3244"),
                    ("[S]", "bold #FF7A00"),
                    (" Shuffle", "#6C7086"),
                    (" • ", "#2E3244"),
                    ("[R]", "bold #FF7A00"),
                    (" Repeat", "#6C7086"),
                    (" • ", "#2E3244"),
                    ("[+/-]", "bold #FF7A00"),
                    (" Volume", "#6C7086"),
                    (" • ", "#2E3244"),
                    ("[Q]", "bold #FF7A00"),
                    (" Quit", "#6C7086"),
                ),
                layout=False,
            )
            self._hint_initialized = True

        if not self.playback_data:
            if art_center.display:
                art_center.display = False
            if self._last_art_drawn:
                art_widget.update("")
                self._last_art_drawn = ""
            self._full_title = ""
            self._marquee_offset = 0
            self._marquee_pause = 8
            self._marquee_end_pause = 0
            if self._last_title != "__EMPTY__":
                theme = load_theme()
                palette = theme.get("palette", {})
                start_color = palette.get("gradient_start", "#FF4500")
                end_color = palette.get("gradient_end", "#FFD166")
                title_widget.update(render_rich_gradient("Select Music", start_color, end_color), layout=False)
                self._last_title = "__EMPTY__"
            if self._last_meta != "__EMPTY__":
                meta_widget.update(
                    Text.assemble(
                        ("Press ", "dim #A6ADC8"),
                        ("[Tab]", "bold #FFD166"),
                        (" to explore", "dim #A6ADC8"),
                    ),
                    layout=False,
                )
                self._last_meta = "__EMPTY__"
            if self._last_source != "":
                source_widget.update("", layout=False)
                self._last_source = ""
            if source_widget.display:
                source_widget.display = False
            transport.set_state(
                is_playing=False,
                has_track=False,
                shuffle_enabled=self.shuffle_enabled,
                repeat_mode=self.repeat_mode,
            )
            volume_bar.set_state(volume=100, device_name=self.device_name or "YouTube Music")
            seek_bar.set_progress(0, 0)
            return

        if not art_center.display:
            art_center.display = True
        if self._last_art_drawn != self._cached_art_ansi:
            art_widget.update(Text.from_ansi(self._cached_art_ansi))
            self._last_art_drawn = self._cached_art_ansi

        title = self.playback_data.get("title", "Unknown")
        artist = self.playback_data.get("artist", "Unknown Artist")
        album = self.playback_data.get("album", "")
        duration = self.playback_data.get("duration_ms", 0)
        volume = self.playback_data.get("volume", 50)
        is_playing = self.playback_data.get("is_playing", False)
        device_name = self.playback_data.get("device_name", self.device_name or "YouTube Music")

        if title != self._full_title:
            self._full_title = title
            self._marquee_offset = 0
            self._marquee_pause = 8
            self._marquee_end_pause = 0

        title_width = self._get_title_width(title_widget)
        title_visible = self._slice_title_marquee(title, title_width)
        if self._last_title != title_visible:
            title_widget.update(f"[bold #FFFFFF]{title_visible}[/]", layout=False)
            self._last_title = title_visible

        meta_raw = f"{artist} • {album}" if album else artist
        meta_limit = max(26, title_width)
        meta_trunc = meta_raw if len(meta_raw) <= meta_limit else meta_raw[: meta_limit - 1] + "…"
        if self._last_meta != meta_trunc:
            meta_widget.update(f"[dim #A6ADC8]{meta_trunc}[/]", layout=False)
            self._last_meta = meta_trunc

        source_raw = (self.playback_data.get("playlist_source") or self.playback_data.get("source") or "").strip()
        if source_raw:
            src_limit = max(24, title_width - 2)
            source_trunc = source_raw if len(source_raw) <= src_limit else source_raw[: src_limit - 1] + "…"
            source_text = f"[dim #6C7086]♫ {source_trunc}[/]"
        else:
            source_text = ""
        if self._last_source != source_text:
            source_widget.update(source_text, layout=False)
            self._last_source = source_text
        want_source_display = bool(source_text)
        if source_widget.display != want_source_display:
            source_widget.display = want_source_display

        transport.set_state(
            is_playing=is_playing,
            has_track=True,
            shuffle_enabled=self.shuffle_enabled,
            repeat_mode=self.repeat_mode,
        )
        volume_bar.set_state(volume=volume, device_name=device_name)
        seek_bar.set_progress(self._current_progress_ms, duration)

    def _get_title_width(self, title_widget: Static) -> int:
        w = getattr(title_widget.size, "width", 0) or 0
        return max(24, w) if w > 0 else 34

    def _slice_title_marquee(self, title: str, width: int) -> str:
        if len(title) <= width:
            return title
        max_offset = len(title) - width
        offset = max(0, min(self._marquee_offset, max_offset))
        return title[offset : offset + width]

    def _advance_title_marquee(self) -> None:
        if not self.is_mounted or not self.playback_data or not self._full_title:
            return
        try:
            title_widget = self.query_one("#track-title", Static)
        except Exception:
            return
        width = self._get_title_width(title_widget)
        if len(self._full_title) <= width:
            return

        max_offset = len(self._full_title) - width
        if self._marquee_pause > 0:
            self._marquee_pause -= 1
            return
        if self._marquee_offset < max_offset:
            self._marquee_offset += 1
            if self._marquee_offset == max_offset:
                self._marquee_end_pause = 8
        elif self._marquee_end_pause > 0:
            self._marquee_end_pause -= 1
            return
        else:
            self._marquee_offset = 0
            self._marquee_pause = 8

        title_visible = self._slice_title_marquee(self._full_title, width)
        if self._last_title != title_visible:
            title_widget.update(f"[bold #FFFFFF]{title_visible}[/]", layout=False)
            self._last_title = title_visible

    def on_mount(self) -> None:
        self.refresh_stage()
        if self._marquee_timer is None:
            self._marquee_timer = self.set_interval(0.25, self._advance_title_marquee)
