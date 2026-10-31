"""Album art fetcher and 24-bit TrueColor ANSI half-block character mosaic renderer."""

from __future__ import annotations

import io
from typing import Dict, Tuple
from PIL import Image
import requests

_ART_CACHE: Dict[Tuple[str, int, int], str] = {}


def image_to_ansi(img: Image.Image, width: int = 28, height: int = 14) -> str:
    """
    Convert a PIL image into a high-density 24-bit TrueColor ANSI half-block string.
    Each character cell represents 2 vertical pixels using the upper-half block (▀),
    effectively doubling vertical resolution in standard terminals.
    """
    img = img.convert("RGB")
    pixel_height = height * 2
    resized = img.resize((width, pixel_height), Image.Resampling.LANCZOS)
    pixels = resized.load()

    lines = []
    for y in range(0, pixel_height, 2):
        line_chars = []
        for x in range(width):
            top_r, top_g, top_b = pixels[x, y]
            bottom_y = y + 1
            if bottom_y < pixel_height:
                bot_r, bot_g, bot_b = pixels[x, bottom_y]
            else:
                bot_r, bot_g, bot_b = (19, 20, 28)  # Arcane canvas_bg

            # Foreground = top pixel, Background = bottom pixel
            char = f"\x1b[38;2;{top_r};{top_g};{top_b}m\x1b[48;2;{bot_r};{bot_g};{bot_b}m\u2580"
            line_chars.append(char)
        line_chars.append("\x1b[0m")
        lines.append("".join(line_chars))

    return "\n".join(lines)


def render_placeholder(width: int = 28, height: int = 14) -> str:
    """Render an aesthetic Arcane placeholder when no artwork is present."""
    lines = []
    mid_y = height // 2
    for y in range(height):
        if y == mid_y - 1:
            text = "♪  ♫  ♪".center(width)
        elif y == mid_y:
            text = "[ NO ARTWORK ]".center(width)
        else:
            text = " " * width
        lines.append(f"\x1b[48;2;24;26;36m\x1b[38;2;108;112;134m{text}\x1b[0m")
    return "\n".join(lines)


def render_album_art(url: str, width: int = 28, height: int = 14) -> str:
    """Fetch and convert album art URL into ANSI block mosaic with caching."""
    if not url:
        return render_placeholder(width, height)

    cache_key = (url, width, height)
    if cache_key in _ART_CACHE:
        return _ART_CACHE[cache_key]

    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            img = Image.open(io.BytesIO(resp.content))
            ansi_str = image_to_ansi(img, width=width, height=height)
            _ART_CACHE[cache_key] = ansi_str
            return ansi_str
    except Exception:
        pass

    return render_placeholder(width, height)
