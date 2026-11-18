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
    from bard.ui.spectrum import render_spectrum_lines

    lines = render_spectrum_lines([1.0, 0.5], rows=8)
    assert len(lines) == 8
    # Top row has peak color, bottom row has deep amber color
    assert "#FFD28A" in lines[0]
    assert "#8F3900" in lines[-1]
    assert "█" in lines[-1]


def test_spectrum_deck_play_state_gating_and_rapid_toggle():
    from bard.ui.spectrum import SpectrumDeck

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield SpectrumDeck()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 20)) as pilot:
            deck = app.query_one(SpectrumDeck)
            await pilot.pause()

            # Paused / idle: strictly dormant banner, no spectrum axis or bars
            rendered_idle = str(deck.query_one("#spectrum-well").render())
            assert "STANDBY · AWAITING RESONANCE" in rendered_idle
            assert "60Hz SUB-CORE" not in rendered_idle

            # Playing: spectrum active
            deck.set_state(is_playing=True, has_track=True, progress_ms=10000, duration_ms=120000)
            await pilot.pause()
            rendered_playing = str(deck.query_one("#spectrum-well").render())
            assert "STANDBY · AWAITING RESONANCE" not in rendered_playing
            assert "60Hz SUB-CORE" in rendered_playing
            assert "RESONATING" in str(deck.query_one("#spectrum-header").render())

            # Rapid toggle back to paused clears immediately
            deck.set_state(is_playing=False, has_track=True, progress_ms=10000, duration_ms=120000)
            await pilot.pause()
            rendered_paused = str(deck.query_one("#spectrum-well").render())
            assert "STANDBY · AWAITING RESONANCE" in rendered_paused
            assert "60Hz SUB-CORE" not in rendered_paused

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

            # Click left of bar start -> clamps to 0.0
            await pilot.click("#progress-bar", offset=(0, 0))
            assert seeks[-1] == 0.0

            # Click past right edge -> clamps to duration (100.0)
            await pilot.click("#progress-bar", offset=(max(0, w - 1), 0))
            assert seeks[-1] == 100.0

            # Drag to midpoint
            bar.on_mouse_down(MouseDown(bar, x=w // 2, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            bar.on_mouse_move(MouseMove(bar, x=w // 2, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            bar.on_mouse_up(MouseUp(bar, x=w // 2, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            assert 40.0 <= seeks[-1] <= 60.0

    asyncio.run(_run())
