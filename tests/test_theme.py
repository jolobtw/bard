"""Test Arcane Theme integration in Bard."""

from bard.arcane_theme import load_theme


def test_theme_loads_valid_palette():
    theme = load_theme()
    assert "palette" in theme
    palette = theme["palette"]
    assert palette["canvas_bg"] == "#13141C"
    assert palette["panel_bg"] == "#181A24"
    assert palette["border_active"] == "#FF7A00"
    assert palette["accent_flame"] == "#FF7A00"
