"""Bottom three-column command deck widgets for Bard."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from rich.markup import escape as markup_escape
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Static

from bard.art import frame_art_ansi, render_album_art
from bard.models import Track
from bard.ui.palette import (
    AMBER_CORE,
    AMBER_GLOW,
    AMBER_PEAK,
    BG_ACTIVE_AMBER,
    BG_CURSOR,
    BG_ELEVATED,
    BG_OBSIDIAN,
    BG_PANEL,
    BORDER_AMBER,
    BORDER_SLATE,
    TEXT_MAIN,
    TEXT_MUTED,
    track_rune,
)
from bard.ui.spectrum import format_ms, render_arcane_bar


class ArtifactPanel(Widget):
    """Left column: framed album art (or sigil placeholder) and track metadata."""

    DEFAULT_CSS = f"""
    ArtifactPanel {{
        width: 1fr;
        height: 100%;
        background: {BG_PANEL};
        border: round {BORDER_SLATE};
        padding: 0 1;
    }}

    #art-header {{
        width: 100%;
        height: 1;
        color: {AMBER_GLOW};
    }}

    #art-center {{
        width: 100%;
        height: 1fr;
        content-align: center middle;
    }}

    #art-box {{
        width: auto;
        height: auto;
        background: {BG_PANEL};
    }}

    #art-divider {{
        width: 100%;
        height: 1;
        color: {BORDER_SLATE};
    }}

    #track-title {{
        width: 100%;
        height: 1;
        text-style: bold;
        color: {AMBER_PEAK};
    }}

    #track-meta {{
        width: 100%;
        height: 1;
        color: {TEXT_MAIN};
    }}

    #track-source {{
        width: 100%;
        height: 1;
        color: {TEXT_MUTED};
    }}

    #track-codec {{
        width: 100%;
        height: 1;
        color: {AMBER_CORE};
    }}
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.playback_data: Optional[Dict[str, Any]] = None
        self.queue_pos: Tuple[int, int] = (0, 0)
        self.audio_info: Dict[str, Any] = {}
        self._last_art_url: str = "__UNSET__"
        self._last_dims: Optional[Tuple[int, int]] = None
        self._cached_art_ansi: str = ""
        self._last_art_drawn: str = "__UNSET__"
        self._full_title: str = ""
        self._marquee_offset: int = 0
        self._marquee_pause: int = 8
        self._marquee_end_pause: int = 0
        self._marquee_timer: Any = None

    def compose(self) -> ComposeResult:
        yield Static(id="art-header")
        with Vertical(id="art-center"):
            yield Static(id="art-box")
        yield Static(id="art-divider")
        yield Static(id="track-title")
        yield Static(id="track-meta")
        yield Static(id="track-source")
        yield Static(id="track-codec")

    def on_mount(self) -> None:
        self.refresh_panel()
        if self._marquee_timer is None:
            self._marquee_timer = self.set_interval(0.25, self._advance_title_marquee)

    def on_unmount(self) -> None:
        if self._marquee_timer is not None:
            try:
                self._marquee_timer.stop()
            except Exception:
                pass
            self._marquee_timer = None

    def on_resize(self, event: Any = None) -> None:
        if self.is_mounted:
            self.refresh_panel()

    def get_art_dimensions(
        self,
        avail_width: Optional[int] = None,
        avail_height: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Compute proportional album art size fitting inside the left column."""
        w = avail_width if avail_width is not None else (self.size.width or 36)
        h = avail_height if avail_height is not None else (self.size.height or 24)
        art_w = max(12, min(32, w - 4))
        art_h = max(3, min(14, h - 8))
        return (art_w, art_h)

    def set_track(
        self,
        playback_data: Optional[Dict[str, Any]],
        queue_pos: Tuple[int, int] = (0, 0),
        audio_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update artwork, track metadata, queue counter, and codec info."""
        self.playback_data = playback_data
        self.queue_pos = queue_pos
        if audio_info is not None:
            self.audio_info = dict(audio_info)
        self.refresh_panel()

    def set_audio_info(self, audio_info: Dict[str, Any]) -> None:
        """Update real stream codec/samplerate metadata."""
        self.audio_info = dict(audio_info or {})
        if self.is_mounted:
            self._render_codec_badge()

    def _title_width(self) -> int:
        w = self.size.width or 36
        return max(12, w - 2)

    def _slice_marquee(self, title: str, width: int) -> str:
        if len(title) <= width:
            return title
        max_offset = len(title) - width
        offset = max(0, min(self._marquee_offset, max_offset))
        return title[offset : offset + width]

    def _advance_title_marquee(self) -> None:
        if not self.is_mounted or not self.playback_data or not self._full_title:
            return
        width = self._title_width()
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

        rune = track_rune(str(self.playback_data.get("id", "")))
        visible = markup_escape(self._slice_marquee(self._full_title, width))
        try:
            self.query_one("#track-title", Static).update(
                Text.from_markup(f"[bold {AMBER_CORE}]{rune}[/] [bold {AMBER_PEAK}]{visible}[/]"),
                layout=False,
            )
        except Exception:
            pass

    def _render_codec_badge(self) -> None:
        try:
            codec_w = self.query_one("#track-codec", Static)
        except Exception:
            return
        src = ""
        if self.playback_data:
            ps = str(self.playback_data.get("playlist_source") or self.playback_data.get("source") or "").strip()
            if ps:
                src = f"[{TEXT_MUTED}]♫ {markup_escape(ps[:24])}[/]"
        if src:
            codec_w.update(Text.from_markup(src), layout=False)
        else:
            codec_w.update("", layout=False)

    def refresh_panel(self) -> None:
        """Render header, artwork, divider, and metadata."""
        if not self.is_mounted:
            return
        try:
            hdr_w = self.query_one("#art-header", Static)
            art_w_widget = self.query_one("#art-box", Static)
            div_w = self.query_one("#art-divider", Static)
            title_w = self.query_one("#track-title", Static)
            meta_w = self.query_one("#track-meta", Static)
            src_w = self.query_one("#track-source", Static)
        except Exception:
            return

        w = max(14, self.size.width or 32)
        idx, total = self.queue_pos
        count_str = f"{idx:02d}/{total:02d}" if total > 0 and idx > 0 else "--/--"
        hdr_label = "ARTIFACT COVER" if w >= 22 else "ARTIFACT"
        gap = max(1, w - len(hdr_label) - len(count_str))
        hdr_w.update(
            Text.from_markup(f"[bold {AMBER_GLOW}]{hdr_label}[/]{' ' * gap}[{TEXT_MUTED}]{count_str}[/]"),
            layout=False,
        )
        div_w.update(Text.from_markup(f"[{BORDER_SLATE}]{'─' * w}[/]"), layout=False)

        art_w, art_h = self.get_art_dimensions()
        art_url = str(self.playback_data.get("album_art_url", "")) if self.playback_data else ""
        if art_url:
            if art_url != self._last_art_url or self._last_dims != (art_w, art_h) or not self._cached_art_ansi:
                self._last_art_url = art_url
                self._last_dims = (art_w, art_h)
                self._cached_art_ansi = render_album_art(art_url, width=art_w, height=art_h)
            framed = frame_art_ansi(self._cached_art_ansi, border_hex=BORDER_AMBER, bg_hex=BG_PANEL)
            if framed != self._last_art_drawn:
                self._last_art_drawn = framed
                art_w_widget.update(Text.from_ansi(framed), layout=True)
        else:
            self._last_art_url = ""
            self._last_dims = (art_w, art_h)
            self._cached_art_ansi = ""
            if self._last_art_drawn != "":
                self._last_art_drawn = ""
                art_w_widget.update("", layout=True)

        if not self.playback_data:
            self._full_title = ""
            title_w.update(Text.from_markup(f"[bold {AMBER_PEAK}]ᛟ Select Music[/]"), layout=False)
            meta_w.update(Text.from_markup(f"[{TEXT_MAIN}]Press [bold {AMBER_PEAK}]\\[Tab][/bold {AMBER_PEAK}] to explore[/]"), layout=False)
            src_w.update("", layout=False)
            self._render_codec_badge()
            return

        title = str(self.playback_data.get("title") or "Unknown")
        artist = str(self.playback_data.get("artist") or "Unknown Artist")
        album = str(self.playback_data.get("album") or "").strip()
        rune = track_rune(str(self.playback_data.get("id") or ""))

        if title != self._full_title:
            self._full_title = title
            self._marquee_offset = 0
            self._marquee_pause = 8
            self._marquee_end_pause = 0

        tw = self._title_width()
        visible = markup_escape(self._slice_marquee(title, tw))
        title_w.update(Text.from_markup(f"[bold {AMBER_CORE}]{rune}[/] [bold {AMBER_PEAK}]{visible}[/]"), layout=False)

        artist_trunc = artist if len(artist) <= w else artist[: max(1, w - 1)] + "…"
        meta_w.update(Text.from_markup(f"[{TEXT_MAIN}]{markup_escape(artist_trunc)}[/]"), layout=False)

        album_trunc = album if len(album) <= w else album[: max(1, w - 1)] + "…"
        src_w.update(Text.from_markup(f"[{TEXT_MUTED}]{markup_escape(album_trunc)}[/]") if album_trunc else "", layout=False)
        self._render_codec_badge()


class _QueueListView(Widget):
    """Scrollable, mouse-clickable queue rows widget."""

    can_focus = False

    DEFAULT_CSS = f"""
    _QueueListView {{
        width: 100%;
        height: 1fr;
        background: {BG_PANEL};
    }}
    """

    def __init__(self, on_click_row: Optional[Callable[[int], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_click_row = on_click_row
        self.entries: List[Tuple[int, Track]] = []
        self.active_original_index: int = -1
        self.cursor_idx: int = 0
        self._row_offset: int = 0

    def set_entries(
        self,
        entries: List[Tuple[int, Track]],
        active_original_index: int,
        cursor_idx: int,
    ) -> None:
        self.entries = entries
        self.active_original_index = active_original_index
        self.cursor_idx = cursor_idx
        self._ensure_cursor_visible()
        self.refresh()

    def _visible_rows(self) -> int:
        return max(1, self.size.height or 8)

    def _ensure_cursor_visible(self) -> None:
        if not self.entries:
            self._row_offset = 0
            return
        vis = self._visible_rows()
        if self.cursor_idx < self._row_offset:
            self._row_offset = self.cursor_idx
        elif self.cursor_idx >= self._row_offset + vis:
            self._row_offset = self.cursor_idx - vis + 1
        max_scroll = max(0, len(self.entries) - vis)
        self._row_offset = max(0, min(self._row_offset, max_scroll))

    def on_resize(self, event: Any = None) -> None:
        self._ensure_cursor_visible()
        self.refresh()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        if self._row_offset > 0:
            self._row_offset = max(0, self._row_offset - 1)
            self.refresh()
            event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        max_scroll = max(0, len(self.entries) - self._visible_rows())
        if self._row_offset < max_scroll:
            self._row_offset = min(max_scroll, self._row_offset + 1)
            self.refresh()
            event.stop()

    def on_click(self, event: events.Click) -> None:
        idx = self._row_offset + event.y
        if 0 <= idx < len(self.entries):
            event.stop()
            if self.on_click_row:
                self.on_click_row(idx)

    def render(self) -> Text:
        w = max(18, self.size.width or 32)
        if not self.entries:
            return Text.from_markup(f"[{TEXT_MUTED}]  No tracks in queue[/]")

        vis = self._visible_rows()
        slice_entries = self.entries[self._row_offset : self._row_offset + vis]
        lines: List[str] = []
        for row_idx, (orig_idx, track) in enumerate(slice_entries, start=self._row_offset):
            is_active = orig_idx == self.active_original_index
            is_cursor = row_idx == self.cursor_idx
            dur = format_ms((track.duration_seconds or 0) * 1000)
            num = f"{orig_idx + 1:02d}"
            prefix = "▶" if is_active else (">" if is_cursor else " ")

            title_budget = max(6, w - len(prefix) - len(num) - len(dur) - 5)
            raw_title = track.title or "Unknown"
            title_plain = raw_title if len(raw_title) <= title_budget else raw_title[: max(1, title_budget - 1)] + "…"
            pad = max(1, w - len(prefix) - len(num) - len(title_plain) - len(dur) - 4)
            title_safe = markup_escape(title_plain)
            row_text = f"{prefix} {num} {title_safe}{' ' * pad}{dur} "

            if is_active:
                lines.append(f"[on {BG_ACTIVE_AMBER} bold {AMBER_PEAK}]{row_text}[/]")
            elif is_cursor:
                lines.append(f"[on {BG_CURSOR} bold {TEXT_MAIN}]{row_text}[/]")
            else:
                lines.append(f"[{TEXT_MAIN}]{prefix} [{TEXT_MUTED}]{num}[/] {title_safe}{' ' * pad}[{TEXT_MUTED}]{dur}[/] [/]")
        return Text.from_markup("\n".join(lines))


class QueuePanel(Widget):
    """Center column: live-filterable active playlist queue."""

    DEFAULT_CSS = f"""
    QueuePanel {{
        width: 1fr;
        height: 100%;
        background: {BG_PANEL};
        border: round {BORDER_SLATE};
        padding: 0 1;
    }}

    #queue-header {{
        width: 100%;
        height: 1;
    }}

    #queue-filter-row {{
        width: 100%;
        height: 1;
        background: {BG_ELEVATED};
        margin: 0 0 1 0;
    }}

    #queue-filter-prefix {{
        width: 3;
        height: 1;
        color: {AMBER_CORE};
        background: {BG_ELEVATED};
        text-style: bold;
        content-align: center middle;
    }}

    #queue-filter {{
        width: 1fr;
        height: 1;
        border: none;
        padding: 0;
        background: {BG_ELEVATED};
        color: {TEXT_MAIN};
    }}

    #queue-filter:focus {{
        border: none;
        color: {AMBER_PEAK};
    }}
    """

    def __init__(
        self,
        on_select_index: Optional[Callable[[int], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.on_select_index = on_select_index
        self._tracks: List[Track] = []
        self._current_index: int = -1
        self._query: str = ""
        self._filtered_entries: List[Tuple[int, Track]] = []
        self._cursor_pos: int = 0

    def compose(self) -> ComposeResult:
        yield Static(id="queue-header")
        with Horizontal(id="queue-filter-row"):
            yield Static("/", id="queue-filter-prefix")
            yield Input(placeholder="filter...", id="queue-filter")
        yield _QueueListView(on_click_row=self._handle_row_click, id="queue-list")

    def on_mount(self) -> None:
        self._apply_filter()

    def on_resize(self, event: Any = None) -> None:
        if self.is_mounted:
            self._render_chrome()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "queue-filter":
            self._query = event.value or ""
            self._cursor_pos = 0
            self._apply_filter()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "queue-filter":
            self.blur_filter(clear=False)

    def _handle_row_click(self, filtered_idx: int) -> None:
        if 0 <= filtered_idx < len(self._filtered_entries):
            self._cursor_pos = filtered_idx
            orig_idx = self._filtered_entries[filtered_idx][0]
            self._sync_view()
            if self.on_select_index:
                self.on_select_index(orig_idx)

    def set_queue(self, tracks: Sequence[Track], current_index: int) -> None:
        """Replace queue snapshot and active playing track index."""
        self._tracks = list(tracks)
        self._current_index = current_index
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._query.strip().lower()
        if not q:
            self._filtered_entries = list(enumerate(self._tracks))
        else:
            self._filtered_entries = [
                (i, t)
                for i, t in enumerate(self._tracks)
                if q in (t.title or "").lower() or q in (t.artist or "").lower()
            ]
        if self._filtered_entries:
            self._cursor_pos = max(0, min(self._cursor_pos, len(self._filtered_entries) - 1))
        else:
            self._cursor_pos = 0
        self._sync_view()

    def _sync_view(self) -> None:
        if not self.is_mounted:
            return
        try:
            list_view = self.query_one("#queue-list", _QueueListView)
            list_view.set_entries(self._filtered_entries, self._current_index, self._cursor_pos)
        except Exception:
            pass
        self._render_chrome()

    def _render_chrome(self) -> None:
        if not self.is_mounted:
            return
        w = max(14, self.size.width or 32)
        try:
            hdr = self.query_one("#queue-header", Static)
        except Exception:
            return

        left_h = "PLAYLIST QUEUE" if w >= 28 else "QUEUE"
        right_h = "[J/K]+[ENTER]" if w >= 28 else "[J/K]"
        if len(left_h) + len(right_h) + 1 > w:
            right_h = ""
        gap_h = max(1, w - len(left_h) - len(right_h)) if right_h else 0
        hdr.update(
            Text.from_markup(
                f"[bold {AMBER_GLOW}]{left_h}[/]{' ' * gap_h}[{TEXT_MUTED}]{markup_escape(right_h)}[/]"
                if right_h
                else f"[bold {AMBER_GLOW}]{left_h}[/]"
            ),
            layout=False,
        )

    def move_cursor(self, delta: int) -> None:
        """Move keyboard selection cursor within the filtered queue."""
        if not self._filtered_entries:
            return
        self._cursor_pos = max(0, min(len(self._filtered_entries) - 1, self._cursor_pos + delta))
        self._sync_view()

    def selected_original_index(self) -> Optional[int]:
        """Return the original queue index of the currently highlighted row, or None."""
        if 0 <= self._cursor_pos < len(self._filtered_entries):
            return self._filtered_entries[self._cursor_pos][0]
        return None

    def focus_filter(self) -> None:
        """Focus the live filter Input."""
        if self.is_mounted:
            try:
                self.query_one("#queue-filter", Input).focus()
            except Exception:
                pass

    def blur_filter(self, clear: bool = False) -> None:
        """Blur the filter Input, optionally clearing the query."""
        if not self.is_mounted:
            return
        try:
            inp = self.query_one("#queue-filter", Input)
            if clear:
                inp.value = ""
                self._query = ""
                self._cursor_pos = 0
                self._apply_filter()
            if inp.has_focus and self.app:
                self.app.set_focus(None)
        except Exception:
            pass

    def clear_filter(self) -> None:
        """Clear filter query and restore full queue view."""
        self.blur_filter(clear=True)

    def has_filter_focus(self) -> bool:
        """Return True if the queue filter Input currently holds focus."""
        if not self.is_mounted:
            return False
        try:
            return bool(self.query_one("#queue-filter", Input).has_focus)
        except Exception:
            return False

    def has_filter_text(self) -> bool:
        """Return True if a non-empty filter query is currently active."""
        return bool(self._query.strip())


class _ClickableChip(Widget):
    """Non-focusable clickable button/chip widget."""

    can_focus = False

    DEFAULT_CSS = f"""
    _ClickableChip {{
        width: 1fr;
        height: 3;
        background: {BG_ELEVATED};
        border: round {BORDER_SLATE};
        content-align: center middle;
    }}
    """

    def __init__(
        self,
        label: str,
        on_press: Optional[Callable[[], None]] = None,
        accent: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self.on_press = on_press
        self._accent = accent
        self._hovered = False
        self._compact_mode = False

    def set_compact(self, compact: bool) -> None:
        self._compact_mode = bool(compact)
        self.styles.height = 1 if self._compact_mode else 3
        self._apply_style()

    def _apply_style(self) -> None:
        if self._compact_mode:
            self.styles.border = "none"
        elif self._accent:
            self.styles.border = ("round", BORDER_AMBER)
        else:
            self.styles.border = ("round", BORDER_SLATE)
        self.styles.background = BG_ACTIVE_AMBER if self._accent else BG_ELEVATED

    def set_label(self, label: str, accent: Optional[bool] = None) -> None:
        changed = label != self._label or (accent is not None and accent != self._accent)
        self._label = label
        if accent is not None:
            self._accent = accent
        if changed:
            self._apply_style()
            self.refresh()

    def on_mount(self) -> None:
        if self._accent:
            self.styles.border = ("round", BORDER_AMBER)
            self.styles.background = BG_ACTIVE_AMBER

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._hovered:
            self._hovered = True
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hovered:
            self._hovered = False
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        if self.on_press:
            self.on_press()

    def render(self) -> Text:
        color = AMBER_PEAK if (self._accent or self._hovered) else TEXT_MAIN
        return Text.from_markup(f"[bold {color}]{self._label}[/]")


class VolumeBar(Widget):
    """Full-width interactive horizontal volume fader supporting click and drag."""

    can_focus = False

    DEFAULT_CSS = f"""
    VolumeBar {{
        width: 1fr;
        height: 1;
        background: {BG_PANEL};
    }}
    """

    def __init__(self, on_volume: Optional[Callable[[int], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_volume = on_volume
        self.volume: int = 100
        self._dragging: bool = False
        self._last_drag_x: Optional[int] = None

    def set_volume(self, volume: int) -> None:
        clamped = max(0, min(100, int(volume)))
        if clamped != self.volume:
            self.volume = clamped
            self.refresh()

    def _set_from_x(self, x: int) -> None:
        if not self.on_volume:
            return
        w = max(4, self.size.width or 20)
        pct = max(0, min(100, round((x / max(1, w - 1)) * 100)))
        self.set_volume(pct)
        self.on_volume(pct)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            self._dragging = True
            self._last_drag_x = event.x
            self.capture_mouse()
            self._set_from_x(event.x)
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging and event.x != self._last_drag_x:
            self._last_drag_x = event.x
            self._set_from_x(event.x)
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()
            if event.x != self._last_drag_x:
                self._set_from_x(event.x)
            self._last_drag_x = None
            event.stop()

    def on_click(self, event: events.Click) -> None:
        if event.button == 1:
            event.stop()

    def render(self) -> Text:
        w = max(8, self.size.width or 24)
        filled = int(round((self.volume / 100.0) * (w - 1)))
        unfilled = max(0, (w - 1) - filled)
        return Text.from_markup(render_arcane_bar(filled, unfilled))


class _MuteLabel(Widget):
    """Non-focusable clickable speaker mute/unmute icon."""

    can_focus = False

    DEFAULT_CSS = f"""
    _MuteLabel {{
        width: 3;
        height: 1;
        content-align: left middle;
        background: {BG_PANEL};
    }}
    """

    def __init__(self, on_mute: Optional[Callable[[], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_mute = on_mute
        self.is_muted = False
        self._hovered = False

    def set_muted(self, muted: bool) -> None:
        if self.is_muted != muted:
            self.is_muted = muted
            self.refresh()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._hovered:
            self._hovered = True
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hovered:
            self._hovered = False
            self.refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        if self.on_mute:
            self.on_mute()

    def render(self) -> Text:
        if self.is_muted:
            return Text.from_markup(f"[bold {AMBER_CORE}]󰖁[/] ")
        color = AMBER_PEAK if self._hovered else TEXT_MAIN
        return Text.from_markup(f"[{color}]󰕾[/] ")


class ControlsPanel(Widget):
    """Right column: transport buttons, secondary mode toggles, and full-width volume."""

    DEFAULT_CSS = f"""
    ControlsPanel {{
        width: 1fr;
        height: 100%;
        background: {BG_PANEL};
        border: round {BORDER_SLATE};
        padding: 0 1;
    }}

    #controls-header {{
        width: 100%;
        height: 1;
    }}

    #transport-row {{
        width: 100%;
        height: 3;
        margin-top: 1;
    }}

    #mode-row {{
        width: 100%;
        height: 3;
    }}

    #volume-box {{
        width: 100%;
        height: 2;
        background: {BG_PANEL};
        border: none;
        padding: 0;
        margin-top: 1;
    }}

    #volume-bar-row {{
        width: 100%;
        height: 1;
    }}

    #vol-pct {{
        width: 100%;
        height: 1;
        content-align: center middle;
        color: {TEXT_MUTED};
    }}

    #controls-spacer {{
        height: 1fr;
    }}

    #controls-hint {{
        width: 100%;
        height: 1;
        content-align: center middle;
        color: {TEXT_MUTED};
    }}
    """

    def __init__(
        self,
        on_prev: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_shuffle: Optional[Callable[[], None]] = None,
        on_repeat: Optional[Callable[[], None]] = None,
        on_volume: Optional[Callable[[int], None]] = None,
        on_mute: Optional[Callable[[], None]] = None,
        on_cycle_device: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.on_repeat = on_repeat
        self.on_volume = on_volume
        self.on_mute = on_mute
        self.on_cycle_device = on_cycle_device
        self._is_playing: bool = False
        self._shuffle_enabled: bool = False
        self._repeat_mode: str = "off"
        self._compact: bool = False

    def compose(self) -> ComposeResult:
        yield Static(id="controls-header")
        with Horizontal(id="transport-row"):
            yield _ClickableChip("|◀ PREV", on_press=self.on_prev, id="btn-prev")
            yield _ClickableChip("▶ PLAY", on_press=self.on_play_pause, accent=True, id="btn-play")
            yield _ClickableChip("NEXT ▶|", on_press=self.on_next, id="btn-next")
        with Horizontal(id="mode-row"):
            yield _ClickableChip("⇄ SHUF: OFF", on_press=self.on_shuffle, id="btn-shuffle")
            yield _ClickableChip("↻ LOOP: OFF", on_press=self.on_repeat, id="btn-repeat")
        with Vertical(id="volume-box"):
            with Horizontal(id="volume-bar-row"):
                yield _MuteLabel(on_mute=self.on_mute, id="vol-mute-btn")
                yield VolumeBar(on_volume=self.on_volume, id="volume-control")
            yield Static("100%", id="vol-pct")
        yield Static(id="controls-spacer")
        yield Static(id="controls-hint")

    def on_mount(self) -> None:
        self._apply_responsive_layout()
        self._render_header()
        self._render_buttons()
        self._render_hint()

    def on_resize(self, event: Any = None) -> None:
        if self.is_mounted:
            self._apply_responsive_layout()
            self._render_header()
            self._render_buttons()
            self._render_hint()

    def _is_compact(self) -> bool:
        try:
            app_h = self.app.size.height if self.app else 40
            app_w = self.app.size.width if self.app else 100
        except Exception:
            app_h, app_w = 40, 100
        col_w = self.size.width or 32
        return app_h < 32 or app_w < 92 or col_w < 26

    def _apply_responsive_layout(self) -> None:
        try:
            app_h = self.app.size.height if self.app else 40
        except Exception:
            app_h = 40
        compact_v = app_h < 32 or (self.size.height and self.size.height < 18)
        self._compact = self._is_compact()

        try:
            t_row = self.query_one("#transport-row")
            m_row = self.query_one("#mode-row")
            v_box = self.query_one("#volume-box")
            chips = [
                self.query_one("#btn-prev", _ClickableChip),
                self.query_one("#btn-play", _ClickableChip),
                self.query_one("#btn-next", _ClickableChip),
                self.query_one("#btn-shuffle", _ClickableChip),
                self.query_one("#btn-repeat", _ClickableChip),
            ]
        except Exception:
            return

        if compact_v:
            t_row.styles.height = 1
            t_row.styles.margin = (0, 0, 0, 0)
            m_row.styles.height = 1
            v_box.styles.height = 2
            v_box.styles.border = "none"
            v_box.styles.margin = (0, 0, 0, 0)
            for c in chips:
                c.set_compact(True)
        else:
            t_row.styles.height = 3
            t_row.styles.margin = (1, 0, 0, 0)
            m_row.styles.height = 3
            v_box.styles.height = 2
            v_box.styles.border = "none"
            v_box.styles.margin = (1, 0, 0, 0)
            for c in chips:
                c.set_compact(False)

    def _render_buttons(self) -> None:
        if not self.is_mounted:
            return
        w = self.size.width or 32
        narrow = w < 30
        try:
            self.query_one("#btn-prev", _ClickableChip).set_label("|◀" if narrow else "|◀ PREV", accent=False)
            self.query_one("#btn-play", _ClickableChip).set_label(
                ("❚❚" if self._is_playing else "▶") if narrow else ("❚❚ PAUSE" if self._is_playing else "▶ PLAY"),
                accent=True,
            )
            self.query_one("#btn-next", _ClickableChip).set_label("▶|" if narrow else "NEXT ▶|", accent=False)
            self.query_one("#btn-shuffle", _ClickableChip).set_label(
                f"SHF:{'ON' if self._shuffle_enabled else 'OFF'}" if narrow else f"⇄ SHUF: {'ON' if self._shuffle_enabled else 'OFF'}",
                accent=self._shuffle_enabled,
            )
            mode = self._repeat_mode if self._repeat_mode in ("off", "all", "one") else "off"
            self.query_one("#btn-repeat", _ClickableChip).set_label(
                f"LP:{mode.upper()}" if narrow else f"↻ LOOP: {mode.upper()}",
                accent=(mode != "off"),
            )
        except Exception:
            pass

    def _render_hint(self) -> None:
        if not self.is_mounted:
            return
        try:
            hint_w = self.query_one("#controls-hint", Static)
        except Exception:
            return
        w = self.size.width or 32
        if w >= 56:
            markup = (
                f"[bold {AMBER_CORE}]\\[Tab][/] [{TEXT_MUTED}]Browse[/] · "
                f"[bold {AMBER_CORE}]\\[Space][/] [{TEXT_MUTED}]Play[/] · "
                f"[bold {AMBER_CORE}]\\[N/P][/] [{TEXT_MUTED}]Track[/] · "
                f"[bold {AMBER_CORE}]\\[+/-][/] [{TEXT_MUTED}]Vol[/] · "
                f"[bold {AMBER_CORE}]\\[Q][/] [{TEXT_MUTED}]Quit[/]"
            )
        elif w >= 32:
            markup = (
                f"[bold {AMBER_CORE}]\\[Tab][/] [{TEXT_MUTED}]Browse[/] · "
                f"[bold {AMBER_CORE}]\\[Space][/] [{TEXT_MUTED}]Play[/] · "
                f"[bold {AMBER_CORE}]\\[Q][/] [{TEXT_MUTED}]Quit[/]"
            )
        else:
            markup = f"[bold {AMBER_CORE}]\\[Tab][/] [{TEXT_MUTED}]·[/] [bold {AMBER_CORE}]\\[Space][/] [{TEXT_MUTED}]·[/] [bold {AMBER_CORE}]\\[Q][/]"
        hint_w.update(Text.from_markup(markup), layout=False)

    def _render_header(self) -> None:
        if not self.is_mounted:
            return
        try:
            hdr = self.query_one("#controls-header", Static)
        except Exception:
            return
        w = max(14, self.size.width or 32)
        left = "MEDIA CONTROLS" if w >= 20 else "CONTROLS"
        hdr.update(Text.from_markup(f"[bold {AMBER_GLOW}]{left}[/]"), layout=False)

    def set_state(
        self,
        is_playing: bool,
        has_track: bool,
        shuffle_enabled: bool,
        repeat_mode: str,
        volume: int,
        device_name: str = "",
    ) -> None:
        """Synchronize transport, mode, and volume displays."""
        self._is_playing = bool(is_playing)
        self._shuffle_enabled = bool(shuffle_enabled)
        self._repeat_mode = repeat_mode if repeat_mode in ("off", "all", "one") else "off"
        if not self.is_mounted:
            return
        self._render_buttons()
        try:
            clamped_vol = max(0, min(100, int(volume)))
            self.query_one("#volume-control", VolumeBar).set_volume(clamped_vol)
            self.query_one("#vol-mute-btn", _MuteLabel).set_muted(clamped_vol == 0)
            self.query_one("#vol-pct", Static).update(f"{clamped_vol:02d}%", layout=False)
        except Exception:
            pass

    def set_volume(self, volume: int) -> None:
        """Update volume slider and percentage readout."""
        if not self.is_mounted:
            return
        clamped = max(0, min(100, int(volume)))
        try:
            self.query_one("#volume-control", VolumeBar).set_volume(clamped)
            self.query_one("#vol-mute-btn", _MuteLabel).set_muted(clamped == 0)
            self.query_one("#vol-pct", Static).update(f"{clamped:02d}%", layout=False)
        except Exception:
            pass

    def set_device_label(self, label: str) -> None:
        """No-op kept for interface compatibility."""
        return
