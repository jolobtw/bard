"""Album art fetcher and 24-bit TrueColor ANSI half-block character mosaic renderer."""

from __future__ import annotations

import io
import os
import re
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageEnhance
import requests

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass

_ART_CACHE: Dict[Tuple[str, int, int], str] = {}
_PIL_CACHE: Dict[str, Image.Image] = {}


def upgrade_thumbnail_url(url: str, target_size: int = 544) -> str:
    """Rewrite Google / YouTube thumbnail URL to request high-resolution (native target_size x target_size)."""
    if not url:
        return url
    url = re.sub(r"=w\d+-h\d+", f"=w{target_size}-h{target_size}", url)
    url = re.sub(r"=s\d+", f"=s{target_size}", url)
    return url


def _sextant_char(mask: int) -> str:
    """Map a 6-bit mask (bits 0..5 = TL, TR, ML, MR, BL, BR) to a Unicode 2x3 sextant block."""
    if mask == 21:
        return "\u258c"  # ▌ left half block
    if mask == 42:
        return "\u2590"  # ▐ right half block
    offset = mask - 1 - (1 if mask > 21 else 0) - (1 if mask > 42 else 0)
    return chr(0x1FB00 + offset)


# 31 canonical 2x3 sextant masks (complements 32..62 are identical by swapping fg/bg)
_SEXTANT_MASKS: List[Tuple[str, Tuple[int, ...], Tuple[int, ...]]] = [
    (
        _sextant_char(m),
        tuple(i for i in range(6) if m & (1 << i)),
        tuple(i for i in range(6) if not (m & (1 << i))),
    )
    for m in range(1, 32)
]


def _best_sextant_cell(
    pts: Tuple[Tuple[int, int, int], ...],
) -> Tuple[str, Tuple[int, int, int], Tuple[int, int, int]]:
    """Find the optimal 2x3 sextant block character and (fg, bg) RGB pair."""
    p0 = pts[0]
    if pts[1] == p0 and pts[2] == p0 and pts[3] == p0 and pts[4] == p0 and pts[5] == p0:
        return ("\u2588", p0, p0)

    best_err = 1 << 60
    best_char = "\u2580"
    best_fg = p0
    best_bg = pts[5]

    for char, fg_idx, bg_idx in _SEXTANT_MASKS:
        fg_n = len(fg_idx)
        bg_n = 6 - fg_n
        fg_r = fg_g = fg_b = 0
        for i in fg_idx:
            r, g, b = pts[i]
            fg_r += r
            fg_g += g
            fg_b += b
        bg_r = bg_g = bg_b = 0
        for i in bg_idx:
            r, g, b = pts[i]
            bg_r += r
            bg_g += g
            bg_b += b

        fr, fg_c, fb = fg_r // fg_n, fg_g // fg_n, fg_b // fg_n
        br, bg_c, bb = bg_r // bg_n, bg_g // bg_n, bg_b // bg_n

        err = 0
        for i in fg_idx:
            r, g, b = pts[i]
            dr, dg, db = r - fr, g - fg_c, b - fb
            err += dr * dr + dg * dg + db * db
        for i in bg_idx:
            r, g, b = pts[i]
            dr, dg, db = r - br, g - bg_c, b - bb
            err += dr * dr + dg * dg + db * db

        if err < best_err:
            best_err = err
            best_char = char
            best_fg = (fr, fg_c, fb)
            best_bg = (br, bg_c, bb)
            if err == 0:
                break

    return (best_char, best_fg, best_bg)


def _image_to_halfblock_ansi(img: Image.Image, width: int, height: int) -> str:
    """Render exact 1x2 half-block TrueColor ANSI mosaic."""
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

            char = f"\x1b[38;2;{top_r};{top_g};{top_b}m\x1b[48;2;{bot_r};{bot_g};{bot_b}m\u2580"
            line_chars.append(char)
        line_chars.append("\x1b[0m")
        lines.append("".join(line_chars))

    return "\n".join(lines)


def image_to_ansi(img: Image.Image, width: int = 46, height: int = 20) -> str:
    """
    Convert a PIL image into a high-resolution 24-bit TrueColor ANSI mosaic.
    Uses 2x3 Unicode sextant blocks (6 sub-pixels per character cell) for
    6x pixel density when rendering artwork, and preserves exact 1x2 half-block
    mapping when source matches (width, height*2).
    """
    img = img.convert("RGB")
    if img.size == (width, height * 2):
        return _image_to_halfblock_ansi(img, width=width, height=height)

    sub_w = width * 2
    sub_h = height * 3
    resized = img.resize((sub_w, sub_h), Image.Resampling.LANCZOS)
    resized = ImageEnhance.Sharpness(resized).enhance(1.15)
    pixels = resized.load()

    lines = []
    for cy in range(height):
        y0 = cy * 3
        y1 = y0 + 1
        y2 = y0 + 2
        line_chars = []
        for cx in range(width):
            x0 = cx * 2
            x1 = x0 + 1
            char, (fr, fg, fb), (br, bg, bb) = _best_sextant_cell((
                pixels[x0, y0],
                pixels[x1, y0],
                pixels[x0, y1],
                pixels[x1, y1],
                pixels[x0, y2],
                pixels[x1, y2],
            ))
            line_chars.append(f"\x1b[38;2;{fr};{fg};{fb}m\x1b[48;2;{br};{bg};{bb}m{char}")
        line_chars.append("\x1b[0m")
        lines.append("".join(line_chars))

    return "\n".join(lines)


def render_sigil_art(width: int = 46, height: int = 20) -> str:
    """Render a mystical 24-bit TrueColor Arcane musical sigil emblem."""
    bg_ansi = "\x1b[48;2;24;26;36m"
    gold = "\x1b[38;2;255;209;102m"
    flame = "\x1b[38;2;255;122;0m"
    amber = "\x1b[38;2;255;165;0m"
    subtext = "\x1b[38;2;166;173;200m"
    muted = "\x1b[38;2;108;112;134m"
    reset = "\x1b[0m"

    sigil_lines = [
        f"{muted}·  {gold}✦  {muted}·",
        f"{muted}╭─── {flame}◈ {muted}───╮",
        f"{muted}╭─╯   {amber}◇   ◇   {muted}╰─╮",
        f"{muted}│     {subtext}♫     ♫     {muted}│",
        f"{muted}│   {amber}( (  {gold}◈  {amber}) )   {muted}│",
        f"{flame}◈──  {amber}◇  {gold}✦ ❖ ✦  {amber}◇  {flame}──◈",
        f"{muted}│   {amber}( (  {gold}◈  {amber}) )   {muted}│",
        f"{muted}│     {subtext}♫     ♫     {muted}│",
        f"{muted}╰─╮   {amber}◇   ◇   {muted}╭─╯",
        f"{muted}╰─── {flame}◈ {muted}───╯",
        f"{muted}·  {gold}✦  {muted}·",
        f"{muted}✧  {gold}ARCANE RESONANCE  {muted}✧",
    ]

    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')

    if len(sigil_lines) < height:
        top_pad = (height - len(sigil_lines)) // 2
        bottom_pad = height - len(sigil_lines) - top_pad
        lines = [""] * top_pad + sigil_lines + [""] * bottom_pad
    else:
        lines = sigil_lines[:height]

    formatted = []
    for line in lines:
        plain_len = len(ansi_escape.sub('', line))
        left_pad = max(0, (width - plain_len) // 2)
        right_pad = max(0, width - plain_len - left_pad)
        full_line = f"{bg_ansi}{' ' * left_pad}{line}{' ' * right_pad}{reset}"
        formatted.append(full_line)

    return "\n".join(formatted)


def render_placeholder(width: int = 46, height: int = 20) -> str:
    """Render an aesthetic Arcane placeholder when no artwork is present."""
    return render_sigil_art(width=width, height=height)


def _safe_fetch_image_bytes(url: str, timeout: int = 5) -> Optional[bytes]:
    """Fetch raw image bytes with automatic SSL certificate verification self-healing."""
    if not url:
        return None
    url = upgrade_thumbnail_url(url)
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.content
    except requests.exceptions.SSLError:
        try:
            import certifi
            resp = requests.get(url, verify=certifi.where(), timeout=timeout)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, verify=False, timeout=timeout)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
    except Exception:
        pass
    return None


def fetch_image(url: str, timeout: int = 5) -> Optional[bytes]:
    """Fetch raw image bytes with thumbnail upgrading and automatic SSL certificate verification self-healing."""
    return _safe_fetch_image_bytes(url, timeout=timeout)


def fetch_pil_image(url: str, timeout: int = 5) -> Optional[Image.Image]:
    """Fetch and decode album art as a cached RGB PIL Image for Sixel/TGP rendering."""
    if not url:
        return None
    upgraded = upgrade_thumbnail_url(url)
    if upgraded in _PIL_CACHE:
        return _PIL_CACHE[upgraded]

    content = _safe_fetch_image_bytes(upgraded, timeout=timeout)
    if content:
        try:
            img = Image.open(io.BytesIO(content)).convert("RGB")
            _PIL_CACHE[upgraded] = img
            return img
        except Exception:
            pass
    return None


def render_album_art(url: str, width: int = 46, height: int = 20) -> str:
    """Fetch and convert album art URL into ANSI block mosaic with caching."""
    if not url:
        return render_placeholder(width, height)

    url = upgrade_thumbnail_url(url)
    cache_key = (url, width, height)
    if cache_key in _ART_CACHE:
        return _ART_CACHE[cache_key]

    content = _safe_fetch_image_bytes(url, timeout=5)
    if content:
        try:
            img = Image.open(io.BytesIO(content))
            ansi_str = image_to_ansi(img, width=width, height=height)
            _ART_CACHE[cache_key] = ansi_str
            return ansi_str
        except Exception:
            pass

    return render_placeholder(width, height)


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _hex_to_rgb_tuple(hex_color: str) -> Tuple[int, int, int]:
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) != 6:
        return (255, 122, 0)
    try:
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))
    except ValueError:
        return (255, 122, 0)


def frame_art_ansi(
    art_ansi: str,
    border_hex: str = "#FF7A00",
    bg_hex: str = "#13141C",
) -> str:
    """Wrap ANSI album art in a 1/8-cell thin zero-gap border using Unicode block elements."""
    if not art_ansi:
        return ""

    lines = art_ansi.split("\n")
    art_width = max((len(_ANSI_ESCAPE_RE.sub("", line)) for line in lines), default=0)
    if art_width <= 0:
        return art_ansi

    br, bg, bb = _hex_to_rgb_tuple(border_hex)
    rst = "\x1b[0m"
    if not bg_hex or bg_hex.strip().lower() in ("transparent", "none"):
        fg_bg = f"\x1b[38;2;{br};{bg};{bb}m"
        corner = " "
    else:
        cr, cg, cb = _hex_to_rgb_tuple(bg_hex)
        fg_bg = f"\x1b[38;2;{br};{bg};{bb}m\x1b[48;2;{cr};{cg};{cb}m"
        bg_only = f"\x1b[48;2;{cr};{cg};{cb}m"
        corner = f"{bg_only} {rst}"

    top = f"{corner}{fg_bg}{'▁' * art_width}{rst}{corner}"
    bottom = f"{corner}{fg_bg}{'▔' * art_width}{rst}{corner}"
    left = f"{fg_bg}▕{rst}"
    right = f"{fg_bg}▏{rst}"

    framed = [top]
    for line in lines:
        framed.append(f"{left}{line}{right}")
    framed.append(bottom)
    return "\n".join(framed)
