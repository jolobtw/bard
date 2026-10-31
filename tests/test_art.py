"""Test Album Art rendering and ANSI block converter."""

import io
from PIL import Image
from bard.art import image_to_ansi, render_album_art


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
