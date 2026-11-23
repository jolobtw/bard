"""Tests for Obsidian & Ember palette, simulated center-outward spectrum, and SeekBar."""

import asyncio
from textual.app import App, ComposeResult
from textual.events import MouseDown, MouseMove, MouseUp


def test_palette_tokens_and_deterministic_rune():
    from bard.ui.palette import (
        AMBER_CORE,
        AMBER_DEEP,
        AMBER_GLOW,
        AMBER_PEAK,
        BG_OBSIDIAN,
        BG_PANEL,
        RUNES,
        track_rune,
    )

    assert BG_OBSIDIAN == "#0D0E11"
    assert BG_PANEL == "#14161A"
    assert AMBER_DEEP == "#8F3900"
    assert AMBER_CORE == "#FF7B00"
    assert AMBER_GLOW == "#FF9E2C"
    assert AMBER_PEAK == "#FFD28A"

    assert track_rune("") == "ᛟ"
    r1 = track_rune("vid_12345")
    r2 = track_rune("vid_12345")
    assert r1 == r2
    assert r1 in RUNES


def test_mirror_and_generate_simulated_bins():
    from bard.ui.spectrum import generate_simulated_bins, mirror_spectrum_bins

    assert mirror_spectrum_bins([0.9, 0.4, 0.1]) == [0.1, 0.4, 0.9, 0.9, 0.4, 0.1]

    bins = generate_simulated_bins(phase=0.5, n_bins=28)
    assert len(bins) == 28
    assert all(0.0 <= b <= 1.0 for b in bins)

    # Center sub-bass bins should carry higher average energy than outer 16kHz wings
    center_avg = sum(
        sum(generate_simulated_bins(phase=p * 0.3, n_bins=28)[:4]) / 4
        for p in range(20)
    ) / 20
    wing_avg = sum(
        sum(generate_simulated_bins(phase=p * 0.3, n_bins=28)[-4:]) / 4
        for p in range(20)
    ) / 20
    assert center_avg > wing_avg


def test_render_spectrum_lines_gradient_and_blocks():
    import re
    from bard.ui.spectrum import render_spectrum_lines

    lines = render_spectrum_lines([1.0, 0.5], rows=8)
    assert len(lines) == 8
    # Top row has peak color, bottom row has deep amber color, with smooth per-row gradient (> 4 colors)
    assert "#FFD28A" in lines[0]
    assert "#8F3900" in lines[-1]
    assert "█" in lines[-1]
    colors = {re.search(r"#[0-9A-F]{6}", line).group(0) for line in lines}
    assert len(colors) == 8
    # Bottom row has 4 bars separated by 1-space gaps: "█ █ █ █"
    plain_bottom = re.sub(r"\[/?[^\]]*\]", "", lines[-1])
    assert plain_bottom == "█ █ █ █"


def test_spectrum_deck_expands_full_width():
    from bard.ui.spectrum import SeekBar, SpectrumDeck

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield SpectrumDeck()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(140, 20)) as pilot:
            deck = app.query_one(SpectrumDeck)
            deck.set_state(is_playing=True, has_track=True, progress_ms=0, duration_ms=100000)
            await pilot.pause()
            well_w = deck.query_one("#spectrum-well").size.width
            bottom_line = deck.query_one("#spectrum-well").render().plain.splitlines()[-1]
            bar_line = deck.query_one("#progress-bar", SeekBar).render().plain
            # Visualizer never spills past SeekBar timestamps and keeps uniform 1-space bar gaps
            assert well_w - 3 <= len(bottom_line) <= len(bar_line) == well_w - 2
            assert "  " not in bottom_line
            assert bottom_line[0] in "▁▂▃▄▅▆▇█"
            assert bottom_line[-1] in "▁▂▃▄▅▆▇█"
            assert len(bottom_line) > 56

    asyncio.run(_run())


def test_spectrum_deck_play_state_gating_and_rapid_toggle():
    from bard.ui.spectrum import SeekBar, SpectrumDeck

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield SpectrumDeck()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 20)) as pilot:
            deck = app.query_one(SpectrumDeck)
            await pilot.pause()

            # Paused / idle: subtle dormant banner, no spectrum bars
            rendered_idle = str(deck.query_one("#spectrum-well").render())
            assert "Awaiting Resonance" in rendered_idle
            assert not any(ch in rendered_idle for ch in "▁▂▃▄▅▆▇█")

            # Playing: spectrum active (no header banner noise and no kHz axis)
            deck.set_state(is_playing=True, has_track=True, progress_ms=10000, duration_ms=120000)
            await pilot.pause()
            rendered_playing = str(deck.query_one("#spectrum-well").render())
            assert "Awaiting Resonance" not in rendered_playing
            assert "kHz" not in rendered_playing
            assert "60Hz" not in rendered_playing
            assert any(ch in rendered_playing for ch in "▁▂▃▄▅▆▇█")
            assert len(deck.query("#spectrum-header")) == 0
            assert len(deck.query("#spectrum-divider")) == 0
            assert deck.styles.border_top[0] == "round"

            # Progress scrubber uses subtle line/thumb bar with spacing below visualizer
            well_w = deck.query_one("#spectrum-well")
            bar_w = deck.query_one("#progress-bar", SeekBar)
            assert bar_w.region.y >= well_w.region.bottom + 1
            bar_rendered = str(bar_w.render())
            assert "●" in bar_rendered

            # Rapid toggle back to paused clears immediately
            deck.set_state(is_playing=False, has_track=True, progress_ms=10000, duration_ms=120000)
            await pilot.pause()
            rendered_paused = str(deck.query_one("#spectrum-well").render())
            assert "Awaiting Resonance" in rendered_paused
            assert not any(ch in rendered_paused for ch in "▁▂▃▄▅▆▇█")

    asyncio.run(_run())


def test_seekbar_click_and_drag_clamps_bounds():
    from bard.ui.spectrum import SeekBar, SpectrumDeck

    seeks = []

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield SpectrumDeck(on_seek=lambda s: seeks.append(round(s, 2)))

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 20)) as pilot:
            deck = app.query_one(SpectrumDeck)
            deck.set_state(is_playing=True, has_track=True, progress_ms=20000, duration_ms=100000)
            await pilot.pause()
            bar = deck.query_one("#progress-bar", SeekBar)
            w = bar.size.width

            # Click left of bar start -> clamps to 0.0, fires exactly once per click
            before_count = len(seeks)
            await pilot.click("#progress-bar", offset=(0, 0))
            assert len(seeks) == before_count + 1
            assert seeks[-1] == 0.0

            # Click past right edge -> clamps to duration (100.0), fires once
            before_count = len(seeks)
            await pilot.click("#progress-bar", offset=(max(0, w - 1), 0))
            assert len(seeks) == before_count + 1
            assert seeks[-1] == 100.0

            # Drag to midpoint
            bar.on_mouse_down(MouseDown(bar, x=w // 2, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            bar.on_mouse_move(MouseMove(bar, x=w // 2, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            bar.on_mouse_up(MouseUp(bar, x=w // 2, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            assert 40.0 <= seeks[-1] <= 60.0

    asyncio.run(_run())


def test_smooth_halfblock_and_tgp_pixel_spectrum():
    import re
    from unittest.mock import patch
    from PIL import Image as PILImage
    import bard.ui.spectrum as sp

    # 8-stop dual-color half-block renderer with peak-hold pips
    lines = sp.render_spectrum_lines([1.0, 0.25], rows=4, smooth_halfblock=True, peaks=[1.0, 0.9])
    assert len(lines) == 4
    assert " on " in lines[-1]  # Dual-color fg+bg per cell
    assert "#FFD28A" in lines[0]  # Peak-hold pip on top row
    plain_bottom = re.sub(r"\[/?[^\]]*\]", "", lines[-1])
    assert plain_bottom == "▄ ▄ ▄ ▄"

    # TGP pixel-art spectrum canvas
    img = sp.render_spectrum_image([0.9, 0.4, 0.2], width_px=240, height_px=80, peaks=[0.95, 0.85, 0.5])
    assert isinstance(img, PILImage.Image)
    assert img.mode == "RGBA" and img.size == (240, 80)
    assert img.getpixel((0, 0))[3] == 0  # Transparent background
    assert img.getpixel((0, 79))[3] == 255  # Leftmost bar anchored at x=0
    assert img.getpixel((239, 79))[3] == 255  # Rightmost bar anchored at x=w-1

    # SpectrumDeck uses character-cell #spectrum-well even in TGP terminals so
    # 16 FPS spectrum updates never evict Ghostty's TGP album-art cache.
    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield sp.SpectrumDeck()

    async def _run():
        with patch.object(sp, "_is_tgp_mode", return_value=True):
            app = TestApp()
            async with app.run_test(size=(100, 20)) as pilot:
                deck = app.query_one(sp.SpectrumDeck)
                await pilot.pause()
                assert len(deck.query("#spectrum-tgp")) == 0
                deck.set_state(is_playing=True, has_track=True, progress_ms=5000, duration_ms=100000)
                await pilot.pause()
                assert any(ch in str(deck.query_one("#spectrum-well").render()) for ch in "▁▂▃▄▅▆▇█")

    asyncio.run(_run())
