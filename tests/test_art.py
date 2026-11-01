"""Test Album Art rendering and ANSI block converter."""

import io
from PIL import Image
from bard.art import image_to_ansi, render_album_art, render_sigil_art


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


