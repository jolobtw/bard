"""Test ZenStage formatting and logic."""

from bard.ui.zen_stage import format_ms, render_flame_progress


def test_format_ms():
    assert format_ms(0) == "00:00"
    assert format_ms(65000) == "01:05"
    assert format_ms(230000) == "03:50"


def test_render_flame_progress():
    output = render_flame_progress(progress_ms=30000, duration_ms=60000, width=30)
    assert "00:30" in output
    assert "01:00" in output
    assert "●" in output
