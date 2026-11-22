"""Test Album Art rendering and ANSI block converter."""

import io
from PIL import Image
from bard.art import (
    fetch_image,
    image_to_ansi,
    render_album_art,
    render_sigil_art,
    upgrade_thumbnail_url,
)


def test_image_to_ansi():
    # Create a simple 2x2 test image:
    # Top-Left: Red, Top-Right: Green
    # Bottom-Left: Blue, Bottom-Right: Yellow
    img = Image.new("RGB", (2, 2))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((1, 0), (0, 255, 0))
    img.putpixel((0, 1), (0, 0, 255))
    img.putpixel((1, 1), (255, 255, 0))
    
    ansi_output = image_to_ansi(img, width=2, height=1)
    assert "\u2580" in ansi_output  # Upper half block
    assert "255;0;0" in ansi_output  # Red foreground
    assert "0;0;255" in ansi_output  # Blue background


def test_render_album_art_fallback_empty():
    res = render_album_art("")
    assert "NO ARTWORK" in res or "♫" in res


def test_render_sigil_art():
    res = render_sigil_art(width=32, height=12)
    lines = res.split("\n")
    assert len(lines) == 12
    # Must contain arcane runes
    assert "✦" in res or "◈" in res or "◇" in res
    assert "♫" in res or "♪" in res


def test_render_album_art_ssl_error_self_healing():
    import requests
    from unittest.mock import MagicMock, patch

    img = Image.new("RGB", (4, 4), color=(255, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = img_bytes

    call_count = 0

    def mock_get(url, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if "verify" not in kwargs:
            raise requests.exceptions.SSLError("certificate verify failed")
        return mock_resp

    with patch("requests.get", side_effect=mock_get):
        res = render_album_art("https://i.scdn.co/image/test_art_ssl", width=4, height=2)
        assert "\u2580" in res
        assert "ARCANE RESONANCE" not in res
        assert call_count >= 2


def test_upgrade_thumbnail_url_rewrites_dimensions():
    low_res = "https://yt3.googleusercontent.com/abc=w60-h60-l90-rj"
    high_res = upgrade_thumbnail_url(low_res, target_size=544)
    assert "=w544-h544" in high_res


def test_upgrade_thumbnail_url_handles_s_param():
    low_res = "https://lh3.googleusercontent.com/xyz=s120"
    high_res = upgrade_thumbnail_url(low_res, target_size=544)
    assert "=s544" in high_res or "=w544-h544" in high_res


def test_fetch_image_calls_upgrade_thumbnail():
    from unittest.mock import patch
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake-bytes"
        content = fetch_image("https://lh3.googleusercontent.com/xyz=s120")
        assert content == b"fake-bytes"
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "=s544" in args[0]



def test_upgrade_thumbnail_url_non_matching_url():
    url = "https://example.com/cover.jpg"
    assert upgrade_thumbnail_url(url) == url


def test_render_album_art_hero_dimensions():
    # Should render 46 chars wide by 20 rows high
    ansi = render_album_art("", width=46, height=20)
    lines = ansi.split("\n")
    assert len(lines) == 20


def test_render_album_art_default_hero_dimensions():
    # Default without explicit dimensions should now be 20 rows high
    ansi = render_album_art("")
    lines = ansi.split("\n")
    assert len(lines) == 20


def test_image_to_ansi_uses_quadrant_blocks_for_higher_resolution():
    # High-res image with horizontal split (left red, right blue) should use left-half block ▌
    img = Image.new("RGB", (16, 16))
    for y in range(16):
        for x in range(16):
            img.putpixel((x, y), (255, 0, 0) if x < 8 else (0, 0, 255))

    ansi_output = image_to_ansi(img, width=4, height=4)
    lines = ansi_output.split("\n")
    assert len(lines) == 4
    # Quadrant/sextant renderer can represent vertical splits using ▌ (\u258c)
    assert any(ch in ansi_output for ch in ("\u258c", "\u2598", "\u259d", "\u2596", "\u2597", "\u259a", "\u259e"))


def test_image_to_ansi_uses_sextant_blocks():
    # 4x6 image with top 2 rows red and bottom 4 rows blue -> exact 2x3 sextant 🬎 (U+1FB0E, top 2/3)
    img = Image.new("RGB", (4, 6))
    for y in range(6):
        for x in range(4):
            img.putpixel((x, y), (255, 0, 0) if y < 2 else (0, 0, 255))

    ansi_output = image_to_ansi(img, width=2, height=2)
    lines = ansi_output.split("\n")
    assert len(lines) == 2
    assert "\U0001fb0e" in lines[0]


def test_frame_art_ansi_thin_zero_gap_border():
    from rich.text import Text
    from bard.art import frame_art_ansi

    assert frame_art_ansi("") == ""

    sample = "\x1b[38;2;255;0;0m███\x1b[0m\n\x1b[38;2;0;255;0m███\x1b[0m"
    framed = frame_art_ansi(sample, border_hex="#FF7A00", bg_hex="#13141C")
    lines = framed.split("\n")
    assert len(lines) == 4  # 2 art rows + top + bottom

    plain_lines = [Text.from_ansi(line).plain for line in lines]
    assert plain_lines[0] == " ▁▁▁ "
    assert plain_lines[1] == "▕███▏"
    assert plain_lines[2] == "▕███▏"
    assert plain_lines[3] == " ▔▔▔ "

    framed_transparent = frame_art_ansi(sample, border_hex="#FF7A00", bg_hex="transparent")
    assert "48;2;" not in framed_transparent.split("\n")[0]
    assert [Text.from_ansi(line).plain for line in framed_transparent.split("\n")] == plain_lines


def test_apply_arcane_glow_tgp_rgba_and_sixel_rgb():
    from bard.art import apply_arcane_glow, render_glow_album_art

    cover = Image.new("RGB", (100, 100), color=(20, 40, 80))

    # TGP mode (bg_hex=None): RGBA with transparent corners and warm amber glow near cover edge
    tgp_img = apply_arcane_glow(cover, bg_hex=None)
    assert tgp_img.mode == "RGBA"
    assert tgp_img.width > cover.width and tgp_img.height > cover.height
    assert tgp_img.getpixel((0, 0))[3] < 20  # Outer corner fades out
    pad = (tgp_img.width - cover.width) // 2
    edge_px = tgp_img.getpixel((pad - 3, tgp_img.height // 2))
    assert edge_px[0] > edge_px[2] and edge_px[3] > 50  # Warm amber/ember glow

    # Sixel mode (bg_hex="#0D0E11"): opaque RGB pre-blended onto obsidian
    sixel_img = apply_arcane_glow(cover, bg_hex="#0D0E11")
    assert sixel_img.mode == "RGB"
    assert sixel_img.size == tgp_img.size
    corner_px = sixel_img.getpixel((0, 0))
    assert corner_px[0] <= 20 and corner_px[1] <= 20 and corner_px[2] <= 25

    # Cached wrapper returns identical cached object for same URL + bg_hex
    c1 = render_glow_album_art("https://example.com/glow_test.jpg", cover, bg_hex=None)
    c2 = render_glow_album_art("https://example.com/glow_test.jpg", cover, bg_hex=None)
    assert c1 is c2



