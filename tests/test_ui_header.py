"""Test Arcane Header widget."""

from bard.ui.header import ArcaneHeader


def test_arcane_header_rendering():
    header = ArcaneHeader(is_playing=True, device_name="Bard", version="0.2.0")
    rendered = header.render()
    plain = rendered.plain
    assert "BARD" in plain
    assert "v0.2.0" in plain
    assert "Arcane Music Player" in plain
    assert "320 kbps" in plain
    assert "Playing" in plain
