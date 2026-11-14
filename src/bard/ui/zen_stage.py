"""Zen Now-Playing Stage widget with Sixel/TGP HD art and horizontal mock-style dock."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static
from textual_image.widget import Image as TIImage

from bard.arcane_theme import load_theme, render_rich_gradient
from bard.art import fetch_pil_image, render_album_art

_DOCK_BG_ANSI = "\x1b[48;2;24;26;36m"  # #181A24


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

    if filled_len > 0:
        filled_bar = f"[#FF7A00]{'━' * max(0, filled_len - 1)}[#FFD166]●[/]"
    else:
        filled_bar = "[#FFD166]●[/]"
    unfilled_bar = f"[#2E3244]{'─' * max(0, unfilled_len)}[/]"

    return f"[#A6ADC8]{curr_str}[/]  {filled_bar}{unfilled_bar}  [#6C7086]{total_str}[/]"


def _render_play_circle_rows(
    is_playing: bool,
    is_active: bool,
    hovered: bool,
) -> Tuple[str, str, str]:
    """
    Render a 7x3 chamfered circle for the Play/Pause control using 24-bit TrueColor half-blocks.
    """
    if is_playing or hovered:
        fg = (255, 146, 43) if hovered else (255, 122, 0)  # #FF922B / #FF7A00
        icon_fg = (19, 20, 28)  # #13141C
    elif is_active:
        fg = (38, 41, 56)  # #262938
        icon_fg = (255, 209, 102)  # #FFD166
    else:
        fg = (38, 41, 56)
        icon_fg = (166, 173, 200)  # #A6ADC8

    bg = (24, 26, 36)  # #181A24
    fg_c = f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m"
    fg_on_bg = f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m"
    bg_on_fg = f"\x1b[38;2;{icon_fg[0]};{icon_fg[1]};{icon_fg[2]}m\x1b[48;2;{fg[0]};{fg[1]};{fg[2]}m"
    solid_fg = f"{fg_c}\x1b[48;2;{fg[0]};{fg[1]};{fg[2]}m"
    rst = "\x1b[0m"

    glyph = "❚❚" if is_playing else "▶ "

    # Row 0: chamfered top (5 full middle, 2 bottom-half corners)
    row0 = f"{fg_on_bg}▄{solid_fg}█████{fg_on_bg}▄{rst}"
    # Row 1: full 7-wide center with centered 2-cell glyph
    row1 = f"{solid_fg}  {bg_on_fg}{glyph}{solid_fg}   {rst}"
    # Row 2: chamfered bottom
    row2 = f"{fg_on_bg}▀{solid_fg}█████{fg_on_bg}▀{rst}"
    return (row0, row1, row2)


class TransportBar(Widget):
    """Custom mouse-hit-tested transport bar: Prev, Circle Play/Pause, Next, Shuffle."""

    DEFAULT_CSS = """
    TransportBar {
        width: 24;
        height: 3;
        background: #181A24;
    }
    """

    # Hit zones along X (width 24):
    # [0..3]: Prev   [5..11]: Play Circle   [13..16]: Next   [18..21]: Shuffle
    ZONES = (
        ("prev", 0, 4),
        ("play", 5, 12),
        ("next", 13, 17),
        ("shuffle", 18, 23),
    )

    def __init__(
        self,
        on_prev: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_shuffle: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.is_playing: bool = False
        self.has_track: bool = False
        self.shuffle_enabled: bool = False
        self._hover_zone: Optional[str] = None

    def set_state(self, is_playing: bool, has_track: bool, shuffle_enabled: bool) -> None:
        self.is_playing = is_playing
        self.has_track = has_track
        self.shuffle_enabled = shuffle_enabled
        self.refresh()

    def _zone_at(self, x: int) -> Optional[str]:
        for name, start, end in self.ZONES:
            if start <= x < end:
                return name
        return None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        zone = self._zone_at(event.x)
        if zone != self._hover_zone:
            self._hover_zone = zone
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hover_zone is not None:
            self._hover_zone = None
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        zone = self._zone_at(event.x)
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

    def render(self) -> Text:
        r0, r1, r2 = _render_play_circle_rows(
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

        def _fg(rgb: Tuple[int, int, int]) -> str:
            return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{_DOCK_BG_ANSI}"

        rst = "\x1b[0m"
        blank = f"{_DOCK_BG_ANSI}    {rst}"
        gap = f"{_DOCK_BG_ANSI} {rst}"

        line0 = f"{blank}{gap}{r0}{gap}{blank}{gap}{_DOCK_BG_ANSI}    {rst}"
        line1 = (
            f"{_fg(prev_rgb)} 󰒮  {rst}"
            f"{gap}{r1}{gap}"
            f"{_fg(next_rgb)} 󰒭  {rst}"
            f"{gap}{_fg(shuf_rgb)} 󰒟  {rst}"
        )
        line2 = f"{blank}{gap}{r2}{gap}{blank}{gap}{_DOCK_BG_ANSI}    {rst}"
        return Text.from_ansi(f"{line0}\n{line1}\n{line2}")


class VolumeBar(Widget):
    """Right-side clickable volume slider with [MUTE] toggle and device caption."""

    DEFAULT_CSS = """
    VolumeBar {
        width: 24;
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

    def set_state(self, volume: int, device_name: str) -> None:
        self.volume = max(0, min(100, int(volume)))
        self.device_name = device_name or "YouTube Music"
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        if event.y == 0 and event.x >= 10:
            if self.on_mute:
                self.on_mute()
            return
        if event.y == 1 and event.x >= 3:
            bar_x = event.x - 3
            bar_w = max(1, 20)
            pct = max(0, min(100, round((bar_x / (bar_w - 1)) * 100)))
            if self.on_volume:
                self.on_volume(pct)

    def render(self) -> Text:
        is_muted = self.volume == 0
        mute_tag = "[bold #FF7A00][MUTED][/]" if is_muted else "[#6C7086][MUTE][/]"
        pct_str = f"[bold #FFD166]{self.volume:3d}%[/]"
        line0 = f"         {mute_tag} {pct_str}"

        speaker = "[#FF7A00]󰖁[/]" if is_muted else "[#A6ADC8]󰕾[/]"
        bar_w = 19
        filled = round((self.volume / 100.0) * (bar_w - 1))
        unfilled = (bar_w - 1) - filled
        slider = f"[#FF7A00]{'━' * filled}[#FFD166]●[/][#2E3244]{'─' * unfilled}[/]"
        line1 = f" {speaker} {slider}"

        dev = self.device_name[:23]
        line2 = f"[#6C7086]{dev:>23}[/]"
        return Text.from_markup(f"{line0}\n{line1}\n{line2}")


class SeekBar(Widget):
    """Full-width clickable seek bar with centered mm:ss / mm:ss timestamp."""

    DEFAULT_CSS = """
    SeekBar {
        width: 100%;
        height: 2;
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
            w = max(2, self.size.width)
            pct = min(1.0, max(0.0, event.x / (w - 1)))
            target_sec = (self.duration_ms / 1000.0) * pct
            event.stop()
            self.on_seek(target_sec)

    def render(self) -> Text:
        w = max(20, self.size.width or 80)
        pct = min(1.0, max(0.0, self.progress_ms / self.duration_ms)) if self.duration_ms > 0 else 0.0
        filled = int((w - 1) * pct)
        unfilled = max(0, (w - 1) - filled)
        bar_line = f"[#FF7A00]{'━' * filled}[#FFD166]●[/][#2E3244]{'─' * unfilled}[/]"

        curr_str = format_ms(self.progress_ms)
        total_str = format_ms(self.duration_ms)
        ts = f"{curr_str} / {total_str}"
        pad = max(0, (w - len(ts)) // 2)
        ts_line = f"{' ' * pad}[#A6ADC8]{curr_str}[/] [#6C7086]/ {total_str}[/]"
        return Text.from_markup(f"{bar_line}\n{ts_line}")


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
        width: 92;
        max-width: 96%;
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
        height: 18;
    }

    #player-dock {
        width: 100%;
        height: auto;
        background: #181A24;
        border: round #2E3244;
        padding: 1 2;
    }

    #dock-top-row {
        width: 100%;
        height: 3;
        align: center middle;
    }

    #dock-left {
        width: 1fr;
        height: 3;
    }

    #dock-viz {
        width: 7;
        height: 3;
        margin-right: 1;
        color: #FF7A00;
    }

    #dock-meta {
        width: 1fr;
        height: 3;
    }

    #track-kicker {
        height: 1;
        color: #6C7086;
    }

    #track-title {
        height: 1;
        text-style: bold;
        color: #FFFFFF;
    }

    #track-meta {
        height: 1;
        color: #A6ADC8;
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
        on_seek: Optional[Callable[[float], None]] = None,
        on_volume: Optional[Callable[[int], None]] = None,
        on_mute: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.on_seek = on_seek
        self.on_volume = on_volume
        self.on_mute = on_mute
        self.shuffle_enabled: bool = False
        self.playback_data: Optional[Dict[str, Any]] = None
        self._current_progress_ms: int = 0
        self._last_art_url: str = ""
        self._cached_art_ansi: str = ""
        self._cached_pil_image: Any = None
        self._last_rendered_dims: Optional[Tuple[int, int]] = None
        self.device_name: Optional[str] = None

    def set_shuffle(self, enabled: bool) -> None:
        """Update shuffle toggle state and refresh transport controls."""
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

    def _apply_art_height(self) -> None:
        if not self.is_mounted:
            return
        try:
            art_widget = self.query_one("#art-box", TIImage)
            _, art_h = self.get_art_dimensions()
            art_widget.styles.height = min(22, max(10, art_h - 2))
        except Exception:
            pass

    def on_resize(self, event: Any = None) -> None:
        """Handle resize to adapt album art dimensions dynamically."""
        self._apply_art_height()
        if self.playback_data:
            art_w, art_h = self.get_art_dimensions()
            if self._last_rendered_dims != (art_w, art_h):
                art_url = self.playback_data.get("album_art_url", "")
                self._last_rendered_dims = (art_w, art_h)
                self._cached_art_ansi = render_album_art(art_url, width=art_w, height=art_h)

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
                    yield TIImage(id="art-box")
                with Vertical(id="player-dock"):
                    with Horizontal(id="dock-top-row"):
                        with Horizontal(id="dock-left"):
                            yield Static(id="dock-viz")
                            with Vertical(id="dock-meta"):
                                yield Static("NOW PLAYING", id="track-kicker")
                                yield Static(id="track-title")
                                yield Static(id="track-meta")
                        yield TransportBar(
                            on_prev=self._handle_prev,
                            on_play_pause=self._handle_play_pause,
                            on_next=self._handle_next,
                            on_shuffle=self._handle_shuffle,
                            id="transport-controls",
                        )
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
                self._cached_pil_image = fetch_pil_image(art_url) if art_url else None
        else:
            self._last_art_url = ""
            self._cached_pil_image = None
        self.refresh_stage()

    def tick_progress(self, delta_ms: int = 1000) -> None:
        """Advance progress bar by delta if currently playing."""
        if self.playback_data and self.playback_data.get("is_playing"):
            duration = self.playback_data.get("duration_ms", 0)
            if duration > 0 and self._current_progress_ms < duration:
                self._current_progress_ms = min(duration, self._current_progress_ms + delta_ms)
                if self.is_mounted:
                    try:
                        self.query_one("#progress-bar", SeekBar).set_progress(self._current_progress_ms, duration)
                    except Exception:
                        pass

    def refresh_stage(self) -> None:
        """Re-render stage widgets."""
        if not self.is_mounted:
            return

        art_center = self.query_one("#art-center")
        art_widget = self.query_one("#art-box", TIImage)
        viz_widget = self.query_one("#dock-viz", Static)
        kicker_widget = self.query_one("#track-kicker", Static)
        title_widget = self.query_one("#track-title", Static)
        meta_widget = self.query_one("#track-meta", Static)
        transport = self.query_one("#transport-controls", TransportBar)
        volume_bar = self.query_one("#volume-control", VolumeBar)
        seek_bar = self.query_one("#progress-bar", SeekBar)
        hint_widget = self.query_one("#controls-hint", Static)

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
            ("+/-", "bold #FFD166"),
            (" Volume", "#6C7086"),
            ("   •   ", "#2E3244"),
            ("Q", "bold #FFD166"),
            (" Quit", "#6C7086"),
        )

        if not self.playback_data:
            art_center.display = False
            art_widget.image = None
            viz_widget.update("[#2E3244]▂ ▄ ▆\n▄ ▆ █\n█ ▆ ▄[/]")
            kicker_widget.update("[#FF7A00]✦ READY TO STREAM[/]")
            theme = load_theme()
            palette = theme.get("palette", {})
            start_color = palette.get("gradient_start", "#FF4500")
            end_color = palette.get("gradient_end", "#FFD166")
            title_widget.update(render_rich_gradient("Select Music", start_color, end_color))
            meta_widget.update(
                Text.assemble(
                    ("Press ", "#A6ADC8"),
                    ("[Tab]", "bold #FFD166"),
                    (" to browse or ", "#A6ADC8"),
                    ("[Space]", "bold #FFD166"),
                    (" to resume", "#A6ADC8"),
                )
            )
            transport.set_state(is_playing=False, has_track=False, shuffle_enabled=self.shuffle_enabled)
            volume_bar.set_state(volume=100, device_name=self.device_name or "YouTube Music")
            seek_bar.set_progress(0, 0)
            hint_widget.update(hint_text)
            return

        self._apply_art_height()
        if self._cached_pil_image is not None:
            art_center.display = True
            art_widget.image = self._cached_pil_image
        else:
            art_center.display = True
            art_widget.image = None

        title = self.playback_data.get("title", "Unknown")
        artist = self.playback_data.get("artist", "Unknown Artist")
        album = self.playback_data.get("album", "")
        duration = self.playback_data.get("duration_ms", 0)
        volume = self.playback_data.get("volume", 50)
        is_playing = self.playback_data.get("is_playing", False)
        device_name = self.playback_data.get("device_name", self.device_name or "YouTube Music")

        if is_playing:
            viz_widget.update("[#FF7A00]▁ ▄ ▇\n▃ █ ▅\n█ ▆ ▂[/]")
            kicker_widget.update("[#FF7A00]NOW PLAYING[/]")
        else:
            viz_widget.update("[#363B54]▂ ▄ ▆\n▂ ▄ ▆\n▂ ▄ ▆[/]")
            kicker_widget.update("[#6C7086]PAUSED[/]")

        title_trunc = title if len(title) <= 28 else title[:27] + "…"
        meta_raw = f"{artist} • {album}" if album else artist
        meta_trunc = meta_raw if len(meta_raw) <= 30 else meta_raw[:29] + "…"
        title_widget.update(f"[bold #FFFFFF]{title_trunc}[/]")
        meta_widget.update(f"[#A6ADC8]{meta_trunc}[/]")

        transport.set_state(is_playing=is_playing, has_track=True, shuffle_enabled=self.shuffle_enabled)
        volume_bar.set_state(volume=volume, device_name=device_name)
        seek_bar.set_progress(self._current_progress_ms, duration)
        hint_widget.update(hint_text)

    def on_mount(self) -> None:
        self.refresh_stage()
