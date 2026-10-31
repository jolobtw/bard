"""
arcane_theme.py
Live Auto-Sync Master Design System for Python / Textual & Rich Terminal Apps.
Compatible with JIRA TUI, Claude-generated apps, and standalone terminal scripts.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

RAW_THEME_URL = "https://raw.githubusercontent.com/jolobtw/arcane-theme/main/theme.json"

DEFAULT_THEME: Dict[str, Any] = {
    "name": "Arcane Flame & Slate",
    "version": "1.0.0",
    "palette": {
        "canvas_bg": "#13141C",
        "panel_bg": "#181A24",
        "selection_bg": "#262938",
        "border_active": "#FF7A00",
        "border_muted": "#2E3244",
        "accent_flame": "#FF7A00",
        "accent_flame_deep": "#E64A19",
        "accent_amber": "#FFAF00",
        "accent_gold": "#FFD166",
        "gradient_start": "#FF4500",
        "gradient_end": "#FFD166",
        "alert_bg": "#4D1A00",
        "text_bright": "#FFFFFF",
        "text_regular": "#A6ADC8",
        "text_muted": "#6C7086",
        "status_error": "#FF4D4D",
        "status_success": "#A6E3A1",
        "status_info": "#89DCEB",
        "folder_warm": "#C5A880",
    },
    "header": {
        "star_glyph": "✦",
        "star_color": "#FF7A00",
        "title_glyph": "❖",
        "title_gradient": ["#FF4500", "#FFD166"],
        "separator_glyph": "❖",
        "separator_color": "#6C7086",
        "tagline_color": "#6C7086",
        "divider_glyph": "─",
        "divider_color": "#2E3244",
    },
    "badges": {
        "background": "#262938",
        "text_color": "#6C7086",
        "active_text_color": "#FFD166",
        "alert_background": "#4D1A00",
        "alert_text_color": "#FFD166",
    },
    "backdrop": {
        "dim_opacity": 0.65,
        "dimmed_text": "#3E4259",
        "dimmed_border": "#1A1C28",
        "dimmed_accent": "#663100",
        "dimmed_canvas": "#0A0B0F",
    },
}

def get_config_path() -> Path:
    """Returns ~/.config/arcane/theme.json on macOS, Linux, and Windows."""
    home = Path(os.path.expanduser("~"))
    return home / ".config" / "arcane" / "theme.json"

def _sync_remote_theme(cache_path: Path):
    """Silent non-blocking background fetch from GitHub."""
    try:
        req = urllib.request.Request(
            RAW_THEME_URL,
            headers={"User-Agent": "ArcaneTheme-AutoSync/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                content = resp.read().decode("utf-8")
                # Validate JSON before writing
                parsed = json.loads(content)
                if "palette" in parsed:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(content, encoding="utf-8")
    except Exception:
        # Offline or rate-limited: silently ignore
        pass

def load_theme() -> Dict[str, Any]:
    """
    Loads active design tokens from ~/.config/arcane/theme.json.
    Spawns a background thread to check GitHub for updates automatically.
    """
    cfg_file = get_config_path()
    theme_data = DEFAULT_THEME

    if cfg_file.is_file():
        try:
            theme_data = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            theme_data = DEFAULT_THEME
    else:
        try:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text(json.dumps(DEFAULT_THEME, indent=2), encoding="utf-8")
        except Exception:
            pass

    # Non-blocking background sync from GitHub
    t = threading.Thread(target=_sync_remote_theme, args=(cfg_file,), daemon=True)
    t.start()

    return theme_data

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def interpolate_rgb(c1: Tuple[int, int, int], c2: Tuple[int, int, int], factor: float) -> str:
    r = int(c1[0] + (c2[0] - c1[0]) * factor)
    g = int(c1[1] + (c2[1] - c1[1]) * factor)
    b = int(c1[2] + (c2[2] - c1[2]) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"

def render_rich_gradient(text: str, start_hex: str, end_hex: str) -> str:
    """Renders text with a smooth character-by-character color gradient in Rich syntax."""
    chars = list(text)
    if not chars:
        return ""
    if len(chars) == 1:
        return f"[{start_hex}]{chars[0]}[/]"

    c1 = hex_to_rgb(start_hex)
    c2 = hex_to_rgb(end_hex)

    res = []
    for i, ch in enumerate(chars):
        factor = i / (len(chars) - 1)
        color = interpolate_rgb(c1, c2, factor)
        res.append(f"[{color} bold]{ch}[/]")
    return "".join(res)

def format_rich_header(
    app_title: str,
    tagline: str,
    badges: List[str] | None = None,
    width: int = 100,
    theme: Dict[str, Any] | None = None,
) -> str:
    """
    Renders the exact 2-row Arcane header matching Tome:
    Row 1: [Star] [❖ TITLE] [❖] [Tagline]   ...badges...
    Row 2: Horizontal rule in muted border color
    """
    th = theme or load_theme()
    hdr = th.get("header", {})
    pal = th.get("palette", {})
    bdg = th.get("badges", {})

    star = f"[{hdr.get('star_color', '#FF7A00')} bold]{hdr.get('star_glyph', '✦')}[/]"
    title_text = f"{hdr.get('title_glyph', '❖')} {app_title.upper()}"
    grad = hdr.get("title_gradient", ["#FF4500", "#FFD166"])
    title_rendered = render_rich_gradient(title_text, grad[0], grad[1])

    sep = f"[{hdr.get('separator_color', '#6C7086')}]{hdr.get('separator_glyph', '❖')}[/]"
    tagline_rendered = f"[{hdr.get('tagline_color', '#6C7086')} italic]{tagline}[/]"

    left_markup = f"{star} {title_rendered} {sep} {tagline_rendered}"

    # Render badges on right
    rendered_badges = []
    if badges:
        bg = bdg.get("background", "#262938")
        fg = bdg.get("text_color", "#6C7086")
        for b in badges:
            rendered_badges.append(f"[on {bg} {fg}] {b} [/]")

    right_markup = " ".join(rendered_badges)

    # Calculate gap (ignoring tags for visible length)
    import re
    strip_tags = lambda s: re.sub(r"\[.*?\]", "", s)
    left_vis_w = len(strip_tags(left_markup))
    right_vis_w = len(strip_tags(right_markup))

    gap = max(1, width - left_vis_w - right_vis_w - 2)
    row1 = f" {left_markup}{' ' * gap}{right_markup}"

    div_color = hdr.get("divider_color", "#2E3244")
    div_glyph = hdr.get("divider_glyph", "─")
    row2 = f"[{div_color}]{div_glyph * max(10, width)}[/]"

    return f"{row1}\n{row2}"

def get_textual_css(theme: Dict[str, Any] | None = None) -> str:
    """Returns Textual TCSS variables matching the active palette."""
    th = theme or load_theme()
    p = th.get("palette", {})
    return f"""
/* Arcane Flame & Slate Master Textual Variables */
$canvas-bg: {p.get('canvas_bg', '#13141C')};
$panel-bg: {p.get('panel_bg', '#181A24')};
$selection-bg: {p.get('selection_bg', '#262938')};
$border-active: {p.get('border_active', '#FF7A00')};
$border-muted: {p.get('border_muted', '#2E3244')};
$accent-flame: {p.get('accent_flame', '#FF7A00')};
$accent-amber: {p.get('accent_amber', '#FFAF00')};
$accent-gold: {p.get('accent_gold', '#FFD166')};
$text-bright: {p.get('text_bright', '#FFFFFF')};
$text-regular: {p.get('text_regular', '#A6ADC8')};
$text-muted: {p.get('text_muted', '#6C7086')};
$status-error: {p.get('status_error', '#FF4D4D')};
$status-success: {p.get('status_success', '#A6E3A1')};

ModalScreen {
    background: rgba(0, 0, 0, 0.65);
}
"""
