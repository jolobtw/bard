"""Top visualization deck: simulated center-outward spectrum and full-width SeekBar."""

from __future__ import annotations

import math
from typing import Any, Callable, List, Optional, Sequence
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from bard.arcane_theme import hex_to_rgb, interpolate_rgb
from bard.ui.palette import (
    AMBER_CORE,
    AMBER_DEEP,
    AMBER_GLOW,
    AMBER_PEAK,
    BG_OBSIDIAN,
    BG_PANEL,
    BORDER_AMBER,
    BORDER_SLATE,
    TEXT_MAIN,
    TEXT_MUTED,
)

SPECTRUM_BLOCKS = (" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
_GRAD_START_RGB = hex_to_rgb("#FF4500")
_GRAD_END_RGB = hex_to_rgb(AMBER_PEAK)


def format_ms(ms: int) -> str:
    """Format milliseconds to mm:ss."""
    total_seconds = max(0, int(ms) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def render_arcane_bar(filled: int, unfilled: int) -> str:
    """Render an Obsidian & Ember gradient bar anchored to the full bar width."""
    total = max(1, filled + unfilled)
    parts: List[str] = []
    if filled > 0:
        for i in range(filled):
            factor = i / total
            color = interpolate_rgb(_GRAD_START_RGB, _GRAD_END_RGB, factor)
            parts.append(f"[{color}]━[/]")
    thumb_color = interpolate_rgb(_GRAD_START_RGB, _GRAD_END_RGB, filled / total)
    parts.append(f"[bold {thumb_color}]●[/]")
    if unfilled > 0:
        parts.append(f"[{BORDER_SLATE}]{'─' * unfilled}[/]")
    return "".join(parts)


def render_flame_progress(progress_ms: int, duration_ms: int, width: int = 50) -> str:
    """Render a gradient progress bar with flanking timestamps."""
    pct = min(1.0, max(0.0, progress_ms / duration_ms)) if duration_ms > 0 else 0.0
    curr_str = format_ms(progress_ms)
    total_str = format_ms(duration_ms)
    bar_width = max(10, width - len(curr_str) - len(total_str) - 4)
    filled_len = int(bar_width * pct)
    unfilled_len = bar_width - filled_len
    bar = render_arcane_bar(max(0, filled_len - 1), max(0, unfilled_len))
    return f"[{TEXT_MAIN}]{curr_str}[/]  {bar}  [{TEXT_MUTED}]{total_str}[/]"


def generate_simulated_bins(
    phase: float,
    n_bins: int = 28,
    prev_bins: Optional[Sequence[float]] = None,
) -> List[float]:
    """Generate smoothed, center-weighted procedural harmonic magnitudes in [0.0, 1.0]."""
    if n_bins <= 0:
        return []

    bins: List[float] = []
    denom = max(1, n_bins - 1)
    for i in range(n_bins):
        norm = i / denom
        # Center sub-bass spine has higher base envelope, tapering toward 16kHz wings
        envelope = 0.25 + 0.72 * math.exp(-2.6 * (norm ** 1.35))
        wave_a = 0.5 + 0.5 * math.sin(phase * 3.1 - i * 0.42)
        wave_b = 0.5 + 0.5 * math.sin(phase * 5.7 + i * 0.73)
        pulse = 0.5 + 0.5 * math.sin(phase * 2.0 - norm * 2.2)
        raw = envelope * (0.45 * wave_a + 0.30 * wave_b + 0.25 * pulse)
        target = max(0.04, min(1.0, raw))

        if prev_bins is not None and i < len(prev_bins):
            prev = prev_bins[i]
            alpha = 0.55 if target > prev else 0.28
            target = prev + (target - prev) * alpha
        bins.append(max(0.0, min(1.0, target)))
    return bins


def mirror_spectrum_bins(half_levels: Sequence[float]) -> List[float]:
    """Mirror half-spectrum magnitudes center-outward: reverse(half) + half."""
    half = list(half_levels)
    return list(reversed(half)) + half


def _row_color(row_from_bottom: int, rows: int) -> str:
    """Return Amber gradient hex color for row index counted from the bottom (0-indexed)."""
    if row_from_bottom >= rows - 2:
        return AMBER_PEAK
    if row_from_bottom >= rows - 5:
        return AMBER_GLOW
    if row_from_bottom >= 2:
        return AMBER_CORE
    return AMBER_DEEP


def render_spectrum_lines(half_levels: Sequence[float], rows: int = 8) -> List[str]:
    """Render center-outward spectrum columns as top-to-bottom Rich markup lines."""
    rows = max(3, rows)
    full_levels = mirror_spectrum_bins(half_levels)
    if not full_levels:
        return ["" for _ in range(rows)]

    lines: List[str] = []
    for top_idx in range(rows):
        row_from_bottom = rows - 1 - top_idx
        color = _row_color(row_from_bottom, rows)
        row_cells: List[str] = []
        for level in full_levels:
            clamped = max(0.0, min(1.0, float(level)))
            total_sub = clamped * rows
            cell_fill = max(0.0, min(1.0, total_sub - row_from_bottom))
            step = min(8, max(0, int(round(cell_fill * 8))))
            ch = SPECTRUM_BLOCKS[step]
            if ch == " ":
                row_cells.append(" ")
            else:
                row_cells.append(f"[{color}]{ch}[/]")
        lines.append("".join(row_cells))
    return lines


class SeekBar(Widget):
    """Full-width timeline scrubber with elapsed left, flex bar, and duration right."""

    DEFAULT_CSS = f"""
    SeekBar {{
        width: 100%;
        height: 1;
        background: {BG_PANEL};
        padding: 0 1;
    }}
    """

    def __init__(self, on_seek: Optional[Callable[[float], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_seek = on_seek
        self.progress_ms: int = 0
        self.duration_ms: int = 0
        self._dragging: bool = False
        self._last_drag_x: Optional[int] = None

    def set_progress(self, progress_ms: int, duration_ms: int) -> None:
        """Update elapsed/total milliseconds and redraw if changed."""
        new_prog = max(0, int(progress_ms))
        new_dur = max(0, int(duration_ms))
        if new_prog == self.progress_ms and new_dur == self.duration_ms:
            return
        self.progress_ms = new_prog
        self.duration_ms = new_dur
        self.refresh()

    def _bar_bounds(self) -> tuple[int, int]:
        """Return (bar_left_x, bar_width) inside widget coordinates."""
        total_w = max(24, self.size.width or 80)
        curr_len = len(format_ms(self.progress_ms))
        total_len = len(format_ms(self.duration_ms))
        # Left padding (1) + curr_str + " [" (2); "] " (2) + total_str + right padding (1)
        bar_left = 1 + curr_len + 2
        bar_w = max(8, total_w - (curr_len + total_len + 6))
        return bar_left, bar_w

    def _seek_from_x(self, x: int) -> None:
        if self.duration_ms <= 0 or not self.on_seek:
            return
        bar_left, bar_w = self._bar_bounds()
        ratio = max(0.0, min(1.0, (x - bar_left) / max(1, bar_w - 1)))
        self.on_seek((self.duration_ms / 1000.0) * ratio)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.y == 0 and event.button == 1:
            self._dragging = True
            self._last_drag_x = event.x
            self.capture_mouse()
            self._seek_from_x(event.x)
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging and event.x != self._last_drag_x:
            self._last_drag_x = event.x
            self._seek_from_x(event.x)
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()
            if event.x != self._last_drag_x:
                self._seek_from_x(event.x)
            self._last_drag_x = None
            event.stop()

    def on_click(self, event: events.Click) -> None:
        if event.button == 1 and event.y == 0:
            event.stop()

    def render(self) -> Text:
        curr_str = format_ms(self.progress_ms)
        total_str = format_ms(self.duration_ms)
        _, bar_w = self._bar_bounds()
        pct = min(1.0, max(0.0, self.progress_ms / self.duration_ms)) if self.duration_ms > 0 else 0.0
        filled = int(round(bar_w * pct))
        unfilled = max(0, bar_w - filled)

        filled_str = f"[{AMBER_CORE}]{'█' * filled}[/]" if filled > 0 else ""
        unfilled_str = f"[{BORDER_SLATE}]{'░' * unfilled}[/]" if unfilled > 0 else ""
        time_color = AMBER_PEAK if self.duration_ms > 0 else TEXT_MUTED
        return Text.from_markup(
            f"[bold {time_color}]{curr_str}[/] [{TEXT_MUTED}][[/]{filled_str}{unfilled_str}[{TEXT_MUTED}]] [/][{TEXT_MUTED}]{total_str}[/]"
        )


class SpectrumDeck(Widget):
    """Top visualization deck with play-state-gated center-outward spectrum and SeekBar."""

    DEFAULT_CSS = f"""
    SpectrumDeck {{
        layout: vertical;
        width: 100%;
        height: auto;
        background: {BG_OBSIDIAN};
        border: double {BORDER_SLATE};
        margin-bottom: 0;
    }}

    SpectrumDeck.-playing {{
        border: double {BORDER_AMBER};
    }}

    #spectrum-header {{
        width: 100%;
        height: 1;
        background: {BG_PANEL};
        padding: 0 1;
    }}

    #spectrum-well {{
        width: 100%;
        height: 9;
        background: {BG_OBSIDIAN};
        content-align: center middle;
    }}

    #spectrum-divider {{
        width: 100%;
        height: 1;
        background: {BG_OBSIDIAN};
        color: {BORDER_SLATE};
    }}
    """

    def __init__(self, on_seek: Optional[Callable[[float], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_seek = on_seek
        self.is_playing: bool = False
        self.has_track: bool = False
        self._phase: float = 0.0
        self._bins: List[float] = []
        self._anim_timer: Any = None

    def compose(self) -> ComposeResult:
        yield Static(id="spectrum-header")
        yield Static(id="spectrum-well")
        yield Static(id="spectrum-divider")
        yield SeekBar(on_seek=self.on_seek, id="progress-bar")

    def on_mount(self) -> None:
        self._render_header()
        self._render_well()
        self._render_divider()

    def on_unmount(self) -> None:
        self._stop_timer()

    def on_resize(self, event: Any = None) -> None:
        if self.is_mounted:
            self._adjust_well_height()
            self._render_header()
            self._render_well()
            self._render_divider()

    def _adjust_well_height(self) -> None:
        try:
            app_h = self.app.size.height if self.app else 40
        except Exception:
            app_h = 40
        target_h = 5 if app_h < 32 else 9
        try:
            well = self.query_one("#spectrum-well", Static)
            well.styles.height = target_h
        except Exception:
            pass

    def _start_timer(self) -> None:
        if self._anim_timer is None and self.is_mounted:
            self._anim_timer = self.set_interval(0.06, self._on_anim_tick)

    def _stop_timer(self) -> None:
        if self._anim_timer is not None:
            try:
                self._anim_timer.stop()
            except Exception:
                pass
            self._anim_timer = None

    def _on_anim_tick(self) -> None:
        if not self.is_playing or not self.is_mounted:
            self._stop_timer()
            return
        self._phase += 0.18
        self._bins = generate_simulated_bins(self._phase, n_bins=self._half_bin_count(), prev_bins=self._bins)
        self._render_well()

    def _half_bin_count(self) -> int:
        w = self.size.width or (self.app.size.width if self.app else 100)
        inner = max(20, w - 2)
        return min(28, max(8, inner // 2))

    def _render_header(self) -> None:
        if not self.is_mounted:
            return
        try:
            hdr = self.query_one("#spectrum-header", Static)
        except Exception:
            return
        w = max(24, hdr.size.width or (self.size.width or 100) - 2)
        left = "BARD // CENTER-OUTWARD HARMONIC SPECTRUM"
        if self.is_playing:
            right = f"[{TEXT_MUTED}]ORIGIN: 0Hz CENTER · STATE:[/] [bold {AMBER_CORE}]● RESONATING[/]"
            right_plain = "ORIGIN: 0Hz CENTER · STATE: ● RESONATING"
        else:
            right = f"[{TEXT_MUTED}]ORIGIN: 0Hz CENTER · STATE: ○ STANDBY[/]"
            right_plain = "ORIGIN: 0Hz CENTER · STATE: ○ STANDBY"

        if len(left) + len(right_plain) + 1 > w:
            left = "BARD // SPECTRUM"
            if self.is_playing:
                right = f"[bold {AMBER_CORE}]● RESONATING[/]"
                right_plain = "● RESONATING"
            else:
                right = f"[{TEXT_MUTED}]○ STANDBY[/]"
                right_plain = "○ STANDBY"

        gap = max(1, w - len(left) - len(right_plain))
        hdr.update(Text.from_markup(f"[bold {AMBER_GLOW}]{left}[/]{' ' * gap}{right}"), layout=False)

    def _render_divider(self) -> None:
        if not self.is_mounted:
            return
        try:
            div = self.query_one("#spectrum-divider", Static)
        except Exception:
            return
        w = max(16, div.size.width or self.size.width or 100)
        color = AMBER_CORE if self.is_playing else BORDER_SLATE
        div.update(Text.from_markup(f"[{color}]{'─' * w}[/]"), layout=False)

    def _render_well(self) -> None:
        if not self.is_mounted:
            return
        try:
            well = self.query_one("#spectrum-well", Static)
        except Exception:
            return

        if not self.is_playing:
            banner = (
                f"[{BORDER_AMBER}]───[/] [bold {AMBER_PEAK}]◈ STANDBY · AWAITING RESONANCE ◈[/] [{BORDER_AMBER}]───[/]\n"
                f"[{TEXT_MUTED}]PRESS [bold {TEXT_MAIN}][SPACE][/bold {TEXT_MAIN}] OR CLICK [bold {AMBER_CORE}][▶ PLAY][/bold {AMBER_CORE}] TO IGNITE SPECTRAL TELEMETRY[/]"
            )
            well.update(Text.from_markup(banner), layout=False)
            return

        n_half = self._half_bin_count()
        if len(self._bins) != n_half:
            self._bins = generate_simulated_bins(self._phase, n_bins=n_half)

        well_h = well.size.height or 9
        bar_rows = max(4, well_h - 1)
        spec_lines = render_spectrum_lines(self._bins, rows=bar_rows)
        total_cols = n_half * 2
        core_label = "◈ 60Hz SUB-CORE ◈"
        if total_cols >= 48:
            side_w = max(6, (total_cols - len(core_label)) // 2)
            left_axis = f"16kHz{' ' * max(1, side_w - 9)}4kHz "
            right_axis = f" 4kHz{' ' * max(1, side_w - 10)}16kHz"
            axis = f"[{TEXT_MUTED}]{left_axis}[/][bold {AMBER_PEAK}]{core_label}[/][{TEXT_MUTED}]{right_axis}[/]"
        else:
            axis = f"[bold {AMBER_PEAK}]{core_label}[/]"

        well.update(Text.from_markup("\n".join(spec_lines + [axis])), layout=False)

    def set_playing(self, is_playing: bool) -> None:
        """Toggle play-state gating on the spectrum visualizer."""
        changed = self.is_playing != bool(is_playing)
        self.is_playing = bool(is_playing)
        self.set_class(self.is_playing, "-playing")
        if self.is_playing:
            if not self._bins:
                self._bins = generate_simulated_bins(self._phase, n_bins=self._half_bin_count())
            self._start_timer()
        else:
            self._stop_timer()
            self._bins = []
        if changed or not self.is_playing:
            self._render_header()
            self._render_divider()
            self._render_well()

    def set_progress(self, progress_ms: int, duration_ms: int) -> None:
        """Update embedded SeekBar."""
        if self.is_mounted:
            try:
                self.query_one("#progress-bar", SeekBar).set_progress(progress_ms, duration_ms)
            except Exception:
                pass

    def set_state(
        self,
        is_playing: bool,
        has_track: bool,
        progress_ms: int,
        duration_ms: int,
    ) -> None:
        """Update spectrum play-state and timeline progress together."""
        self.has_track = bool(has_track)
        self.set_playing(is_playing)
        self.set_progress(progress_ms, duration_ms)
