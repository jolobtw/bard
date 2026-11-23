"""Top visualization deck: simulated center-outward spectrum and full-width SeekBar."""

from __future__ import annotations

import math
from typing import Any, Callable, List, Optional, Sequence
from PIL import Image as PILImage, ImageDraw
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

try:
    from textual_image._terminal import get_cell_size as _get_cell_size
    from textual_image.widget import (
        AutoRenderable as _TextualAutoRenderable,
        TGPImage as _TextualTGPImage,
        TGPRenderable as _TextualTGPRenderable,
    )
except Exception:  # pragma: no cover - optional runtime fallback
    _get_cell_size = None
    _TextualAutoRenderable = None
    _TextualTGPImage = None
    _TextualTGPRenderable = None

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
_SPEC_DEEP_RGB = hex_to_rgb(AMBER_DEEP)
_SPEC_CORE_RGB = hex_to_rgb(AMBER_CORE)
_SPEC_PEAK_RGB = hex_to_rgb(AMBER_PEAK)


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
        # Center sub-bass spine has higher base envelope, tapering toward outer wings
        envelope = 0.25 + 0.72 * math.exp(-2.6 * (norm ** 1.35))
        wave_a = 0.5 + 0.5 * math.sin(phase * 3.1 - norm * 11.5)
        wave_b = 0.5 + 0.5 * math.sin(phase * 5.7 + norm * 19.5)
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


def _is_tgp_mode() -> bool:
    """Return True when active terminal supports Kitty TGP pixel graphics."""
    return (
        _TextualTGPImage is not None
        and _TextualAutoRenderable is not None
        and _TextualTGPRenderable is not None
        and _TextualAutoRenderable is _TextualTGPRenderable
    )


def _hex_to_rgb_tuple(hex_color: str) -> tuple[int, int, int]:
    cleaned = hex_color.strip().lstrip("#")
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def _row_rgb(t: float) -> tuple[int, int, int]:
    """Return smooth interpolated Amber (R, G, B) for normalized height t in [0.0, 1.0]."""
    t = max(0.0, min(1.0, t))
    if t <= 0.45:
        f = t / 0.45
        a, b = _SPEC_DEEP_RGB, _SPEC_CORE_RGB
    else:
        f = (t - 0.45) / 0.55
        a, b = _SPEC_CORE_RGB, _SPEC_PEAK_RGB
    return (
        int(a[0] + (b[0] - a[0]) * f),
        int(a[1] + (b[1] - a[1]) * f),
        int(a[2] + (b[2] - a[2]) * f),
    )


def _row_color(row_from_bottom: int, rows: int) -> str:
    """Return smooth interpolated Amber gradient hex color for row index counted from bottom."""
    t = max(0.0, min(1.0, row_from_bottom / max(1, rows - 1)))
    if t <= 0.45:
        return interpolate_rgb(_SPEC_DEEP_RGB, _SPEC_CORE_RGB, t / 0.45)
    return interpolate_rgb(_SPEC_CORE_RGB, _SPEC_PEAK_RGB, (t - 0.45) / 0.55)


def update_peak_hold(
    levels: Sequence[float],
    prev_peaks: Optional[Sequence[float]] = None,
    decay: float = 0.035,
) -> List[float]:
    """Track falling peak-hold levels in [0.0, 1.0] for each half-spectrum bin."""
    out: List[float] = []
    for i, lvl in enumerate(levels):
        v = max(0.0, min(1.0, float(lvl)))
        prev = prev_peaks[i] if (prev_peaks is not None and i < len(prev_peaks)) else v
        out.append(max(v, max(0.0, prev - decay)))
    return out


def render_spectrum_image(
    half_levels: Sequence[float],
    width_px: int,
    height_px: int,
    peaks: Optional[Sequence[float]] = None,
) -> PILImage.Image:
    """Render smooth per-pixel gradient bars with rounded caps and peak pips for TGP."""
    w = max(32, int(width_px))
    h = max(16, int(height_px))
    canvas = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
    half = list(half_levels)
    if not half:
        return canvas

    full_levels = mirror_spectrum_bins(half)
    full_peaks = mirror_spectrum_bins(peaks) if peaks and len(peaks) == len(half) else None
    n_bars = len(full_levels)

    # Compute bar pitch so leftmost bar starts at x=0 and rightmost bar ends at x=w-1
    pitch = w / max(1, n_bars)
    bar_w = max(2, int(round(pitch * 0.52)))
    if n_bars > 1:
        step = (w - bar_w) / (n_bars - 1)
    else:
        step = 0.0

    # Precompute vertical gradient LUT (top-to-bottom)
    grad_colors = [_row_rgb(1.0 - (y / max(1, h - 1))) for y in range(h)]
    draw = ImageDraw.Draw(canvas)

    for idx, level in enumerate(full_levels):
        x0 = int(round(idx * step))
        x1 = min(w - 1, x0 + bar_w - 1)
        clamped = max(0.04, min(1.0, float(level)))
        bar_h = max(2, int(round(clamped * (h - 3))))
        y_top = h - bar_h

        # Subtle soft outer amber bloom behind each bar
        bloom_pad = max(1, bar_w // 3)
        bx0 = max(0, x0 - bloom_pad)
        bx1 = min(w - 1, x1 + bloom_pad)
        by0 = max(0, y_top - 2)
        draw.rounded_rectangle([bx0, by0, bx1, h - 1], radius=max(1, (bx1 - bx0) // 2), fill=(255, 100, 0, 48))

        # Per-row vertical gradient inside rounded bar silhouette
        radius = max(1, bar_w // 2)
        for y in range(y_top, h):
            inset = 0
            dy = y - y_top
            if dy < radius and bar_w >= 4:
                # Round the top cap cleanly
                r = radius
                dx = math.sqrt(max(0.0, r * r - (r - dy - 0.5) ** 2))
                inset = max(0, int(round(r - dx)))
            lx0 = x0 + inset
            lx1 = max(lx0, x1 - inset)
            r_c, g_c, b_c = grad_colors[y]
            draw.line([(lx0, y), (lx1, y)], fill=(r_c, g_c, b_c, 255))

        # Floating peak-hold pip
        if full_peaks is not None:
            pk = max(clamped, min(1.0, float(full_peaks[idx])))
            pk_y = max(0, min(h - 2, h - 1 - int(round(pk * (h - 2)))))
            if pk_y < y_top - 2:
                draw.rectangle([x0, pk_y, x1, min(h - 1, pk_y + 1)], fill=(255, 210, 138, 240))

    return canvas


def render_spectrum_lines(
    half_levels: Sequence[float],
    rows: int = 8,
    target_width: Optional[int] = None,
    smooth_halfblock: bool = False,
    peaks: Optional[Sequence[float]] = None,
) -> List[str]:
    """Render center-outward spectrum columns with 1-space bar gaps as top-to-bottom Rich lines."""
    rows = max(3, rows)
    half = list(half_levels)
    if not half:
        return ["" for _ in range(rows)]

    center_gap = 1
    if target_width is not None and target_width >= 7:
        if target_width % 2 == 1:
            n_bars = (target_width + 1) // 2
            if n_bars == 2 * len(half) - 1 and len(half) > 1:
                full_levels = list(reversed(half[1:])) + half
                full_peaks = (list(reversed(peaks[1:])) + list(peaks)) if (peaks and len(peaks) == len(half)) else None
            else:
                full_levels = mirror_spectrum_bins(half)
                full_peaks = mirror_spectrum_bins(peaks) if (peaks and len(peaks) == len(half)) else None
        else:
            full_levels = mirror_spectrum_bins(half)
            full_peaks = mirror_spectrum_bins(peaks) if (peaks and len(peaks) == len(half)) else None
            wings_w = 4 * len(half) - 2
            center_gap = max(2, target_width - wings_w)
    else:
        full_levels = mirror_spectrum_bins(half)
        full_peaks = mirror_spectrum_bins(peaks) if (peaks and len(peaks) == len(half)) else None

    split_idx = len(full_levels) // 2
    quarter_left = max(1, split_idx // 2)
    quarter_right = min(len(full_levels) - 1, split_idx + (len(full_levels) - split_idx) // 2)
    lines: List[str] = []
    sub_rows = rows * 2

    for top_idx in range(rows):
        row_from_bottom = rows - 1 - top_idx
        row_cells: List[str] = []

        if smooth_halfblock:
            bot_sub = row_from_bottom * 2
            top_sub = bot_sub + 1
            bot_color = _row_color(bot_sub, sub_rows)
            top_color = _row_color(top_sub, sub_rows)

            for idx, level in enumerate(full_levels):
                clamped = max(0.0, min(1.0, float(level)))
                filled_subs = clamped * sub_rows
                has_bot = filled_subs >= bot_sub + 0.35
                has_top = filled_subs >= top_sub + 0.35

                # Peak-hold pip check
                pip_top = False
                pip_bot = False
                if full_peaks is not None:
                    pk_sub = min(sub_rows - 1, max(0, int(round(max(clamped, float(full_peaks[idx])) * (sub_rows - 1)))))
                    if pk_sub == top_sub and not has_top:
                        pip_top = True
                    elif pk_sub == bot_sub and not has_bot:
                        pip_bot = True

                if has_top and has_bot:
                    row_cells.append(f"[{bot_color} on {top_color}]▄[/]")
                elif has_bot:
                    if pip_top:
                        row_cells.append(f"[{bot_color} on {AMBER_PEAK}]▄[/]")
                    else:
                        row_cells.append(f"[{bot_color}]▄[/]")
                elif pip_top:
                    row_cells.append(f"[{AMBER_PEAK}]▀[/]")
                elif pip_bot:
                    row_cells.append(f"[{AMBER_PEAK}]▄[/]")
                else:
                    row_cells.append(" ")
        else:
            color = _row_color(row_from_bottom, rows)
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

        if center_gap == 2:
            left_str = " ".join(row_cells[:split_idx])
            right_str = " ".join(row_cells[split_idx:])
            lines.append(f"{left_str}  {right_str}")
        elif center_gap >= 4:
            # Distribute extra spaces symmetrically (2 in center, 1 each at quarters)
            # so there is never a 4-space hole that looks like a missing middle bar.
            q_l = " ".join(row_cells[:quarter_left])
            q_ml = " ".join(row_cells[quarter_left:split_idx])
            q_mr = " ".join(row_cells[split_idx:quarter_right])
            q_r = " ".join(row_cells[quarter_right:])
            mid_pad = " " * (center_gap - 2)
            lines.append(f"{q_l}  {q_ml}{mid_pad}{q_mr}  {q_r}")
        else:
            lines.append(" ".join(row_cells))
    return lines


class SeekBar(Widget):
    """Full-width timeline scrubber with elapsed left, flex bar, and duration right."""

    DEFAULT_CSS = f"""
    SeekBar {{
        width: 100%;
        height: 1;
        margin-top: 1;
        background: transparent;
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
        filled = int((bar_w - 1) * pct)
        unfilled = max(0, (bar_w - 1) - filled)
        bar = render_arcane_bar(filled, unfilled)
        curr_color = TEXT_MAIN if self.duration_ms > 0 else TEXT_MUTED
        return Text.from_markup(f"[{curr_color}]{curr_str}[/]  {bar}  [{TEXT_MUTED}]{total_str}[/]")


class SpectrumDeck(Widget):
    """Top visualization deck with play-state-gated center-outward spectrum and SeekBar."""

    DEFAULT_CSS = f"""
    SpectrumDeck {{
        layout: vertical;
        width: 100%;
        height: auto;
        background: transparent;
        border: round {BORDER_SLATE};
        margin-bottom: 0;
    }}

    #spectrum-well {{
        width: 100%;
        height: 4;
        padding: 0 1;
        background: transparent;
        content-align: center middle;
    }}
    """

    def __init__(self, on_seek: Optional[Callable[[float], None]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_seek = on_seek
        self.is_playing: bool = False
        self.has_track: bool = False
        self._phase: float = 0.0
        self._bins: List[float] = []
        self._peaks: List[float] = []
        self._anim_timer: Any = None

    def compose(self) -> ComposeResult:
        yield Static(id="spectrum-well")
        yield SeekBar(on_seek=self.on_seek, id="progress-bar")

    def on_mount(self) -> None:
        self._render_well()

    def on_unmount(self) -> None:
        self._stop_timer()

    def on_resize(self, event: Any = None) -> None:
        if self.is_mounted:
            self._adjust_well_height()
            self._render_well()

    def _adjust_well_height(self) -> None:
        try:
            app_h = self.app.size.height if self.app else 40
        except Exception:
            app_h = 40
        target_h = 3 if app_h < 32 else 4
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
        self._peaks = update_peak_hold(self._bins, self._peaks)
        self._render_well()

    def _target_well_width(self) -> int:
        well_w = 0
        try:
            well_w = self.query_one("#spectrum-well", Static).size.width
        except Exception:
            pass
        w = well_w or self.size.width or (self.app.size.width - 4 if self.app else 100)
        return max(24, w - 2)

    def _half_bin_count(self) -> int:
        target_w = self._target_well_width()
        if target_w % 2 == 1:
            n_bars = (target_w + 1) // 2
            return max(6, (n_bars + 1) // 2)
        return max(6, target_w // 4)

    def _render_well(self) -> None:
        if not self.is_mounted:
            return
        try:
            well = self.query_one("#spectrum-well", Static)
        except Exception:
            return

        if not self.is_playing:
            banner = f"[{BORDER_SLATE}]───────────[/]  [{TEXT_MUTED}]Awaiting Resonance[/]  [{BORDER_SLATE}]───────────[/]"
            well.update(Text.from_markup(banner), layout=False)
            return

        n_half = self._half_bin_count()
        if len(self._bins) != n_half:
            self._bins = generate_simulated_bins(self._phase, n_bins=n_half)
        if len(self._peaks) != n_half:
            self._peaks = update_peak_hold(self._bins)

        well_h = max(3, well.size.height or 4)
        target_w = self._target_well_width()
        spec_lines = render_spectrum_lines(
            self._bins,
            rows=well_h,
            target_width=target_w,
        )
        well.update(Text.from_markup("\n".join(spec_lines)), layout=False)

    def set_playing(self, is_playing: bool) -> None:
        """Toggle play-state gating on the spectrum visualizer."""
        changed = self.is_playing != bool(is_playing)
        self.is_playing = bool(is_playing)
        if self.is_playing:
            if not self._bins:
                self._bins = generate_simulated_bins(self._phase, n_bins=self._half_bin_count())
                self._peaks = update_peak_hold(self._bins)
            self._start_timer()
        else:
            self._stop_timer()
            self._bins = []
            self._peaks = []
        if changed or not self.is_playing:
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
