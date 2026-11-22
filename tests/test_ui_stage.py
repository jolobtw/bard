"""Test ZenStage two-tier layout, formatting, spectrum gating, queue, and controls."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Static

from bard.models import Track
from bard.ui.zen_stage import format_ms, render_arcane_bar, render_flame_progress


def test_format_ms():
    assert format_ms(0) == "00:00"
    assert format_ms(65000) == "01:05"
    assert format_ms(230000) == "03:50"


def test_render_flame_progress():
    output = render_flame_progress(progress_ms=30000, duration_ms=60000, width=30)
    assert "00:30" in output
    assert "01:00" in output
    assert "●" in output


def test_render_arcane_bar_gradient():
    half_bar = render_arcane_bar(filled=5, unfilled=5)
    assert "#FF4500" in half_bar
    assert "#FFD28A" not in half_bar
    assert "●" in half_bar
    assert "─" * 5 in half_bar

    full_bar = render_arcane_bar(filled=10, unfilled=0)
    assert "#FF4500" in full_bar
    assert "#FFD28A" in full_bar


def test_zen_stage_empty_and_active_state_rendering():
    from bard.ui.zen_stage import ZenStage

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        app = TestApp()
        async with app.run_test(size=(110, 40)) as pilot:
            stage = app.query_one(ZenStage)
            stage.refresh_stage()
            await pilot.pause()

            title = stage.query_one("#track-title", Static)
            assert "Select Music" in str(title.render())
            assert "Awaiting Resonance" in str(stage.query_one("#spectrum-well", Static).render())
            assert "ARCANE RESONANCE" not in str(stage.query_one("#art-box", Static).render())

            stage.update_playback({
                "id": "track_1",
                "title": "Arcane Echoes",
                "artist": "Vi & Jinx",
                "album": "Piltover Nights",
                "playlist_source": "Synthwave Favorites",
                "duration_ms": 180000,
                "progress_ms": 30000,
                "is_playing": True,
                "album_art_url": "",
                "volume": 75,
                "device_name": "YouTube Music",
            })
            await pilot.pause()
            assert "Arcane Echoes" in str(title.render())
            spec_plain = str(stage.query_one("#spectrum-well", Static).render())
            assert any(ch in spec_plain for ch in "▁▂▃▄▅▆▇█")
            assert "kHz" not in spec_plain
            assert "ARCANE RESONANCE" not in str(stage.query_one("#art-box", Static).render())

            stage.update_playback(None)
            await pilot.pause()
            assert "Select Music" in str(title.render())
            assert "Awaiting Resonance" in str(stage.query_one("#spectrum-well", Static).render())

    asyncio.run(_test())


def test_zen_stage_responsive_layout_and_art_sizing():
    from bard.ui.zen_stage import ZenStage

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        for dims in ((80, 24), (100, 40), (120, 48)):
            app = TestApp()
            async with app.run_test(size=dims) as pilot:
                stage = app.query_one(ZenStage)
                stage.update_playback({
                    "id": "t1",
                    "title": "Song 1",
                    "artist": "Artist 1",
                    "album": "Album 1",
                    "duration_ms": 180000,
                    "progress_ms": 30000,
                    "is_playing": True,
                    "album_art_url": "",
                })
                await pilot.pause()
                w, h = stage.get_art_dimensions()
                assert w >= 12
                if dims == (80, 24):
                    assert h >= 0
                else:
                    assert h >= 3

    asyncio.run(_test())


def test_zen_stage_clickable_controls_queue_and_seek_volume():
    from bard.ui.spectrum import SeekBar
    from bard.ui.stage_widgets import VolumeBar
    from bard.ui.zen_stage import ZenStage

    calls = []

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage(
                on_prev=lambda: calls.append("prev"),
                on_play_pause=lambda: calls.append("play_pause"),
                on_next=lambda: calls.append("next"),
                on_shuffle=lambda: calls.append("shuffle"),
                on_repeat=lambda: calls.append("repeat"),
                on_seek=lambda sec: calls.append(("seek", round(sec, 1))),
                on_volume=lambda vol: calls.append(("vol", vol)),
                on_mute=lambda: calls.append("mute"),
                on_select_queue_index=lambda idx: calls.append(("queue", idx)),
                on_cycle_device=lambda: calls.append("device"),
            )

    async def _test():
        app = TestApp()
        async with app.run_test(size=(110, 40)) as pilot:
            stage = app.query_one(ZenStage)
            seek_bar = stage.query_one("#progress-bar", SeekBar)
            vol_bar = stage.query_one("#volume-control", VolumeBar)

            await pilot.click("#btn-prev")
            await pilot.click("#btn-play")
            await pilot.click("#btn-next")
            await pilot.click("#btn-shuffle")
            await pilot.click("#btn-repeat")
            assert calls[:5] == ["prev", "play_pause", "next", "shuffle", "repeat"]
            assert len(stage.query("#output-route")) == 0

            stage.set_shuffle(True)
            stage.set_repeat("one")
            assert "SHUF: ON" in str(stage.query_one("#btn-shuffle").render())
            assert "LOOP: ONE" in str(stage.query_one("#btn-repeat").render())

            tracks = [
                Track("1", "Alpha", "A", "Alb", 120, ""),
                Track("2", "Beta", "B", "Alb", 150, ""),
            ]
            stage.set_queue(tracks, 0)
            stage.move_queue_cursor(1)
            assert stage.get_selected_queue_index() == 1

            stage.set_audio_info({"codec": "opus", "samplerate": 48000})
            stage.update_playback({
                "id": "1",
                "title": "Alpha",
                "artist": "A",
                "album": "Alb",
                "duration_ms": 100000,
                "progress_ms": 10000,
                "is_playing": True,
                "album_art_url": "",
                "volume": 80,
            })
            await pilot.pause()
            assert vol_bar.volume == 80
            assert "48kHz" not in str(stage.query_one("#track-codec", Static).render())

            await pilot.click("#vol-mute-btn")
            assert "mute" in calls
            await pilot.click("#volume-control", offset=(max(1, vol_bar.size.width // 2), 0))
            assert any(isinstance(c, tuple) and c[0] == "vol" for c in calls)

            await pilot.click("#progress-bar", offset=(max(1, seek_bar.size.width // 2), 0))
            assert any(isinstance(c, tuple) and c[0] == "seek" for c in calls)

    asyncio.run(_test())


def test_zen_stage_full_height_now_playing_and_queue_matched_spectrum():
    from bard.ui.zen_stage import ArtifactPanel, QueuePanel, SpectrumDeck, ZenStage

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        app = TestApp()
        async with app.run_test(size=(120, 42)) as pilot:
            stage = app.query_one(ZenStage)
            await pilot.pause()

            artifact = stage.query_one("#artifact-panel", ArtifactPanel)
            spectrum = stage.query_one("#spectrum-deck", SpectrumDeck)
            queue = stage.query_one("#queue-panel", QueuePanel)

            assert artifact.region.height == stage.region.height
            assert spectrum.region.width == queue.region.width
            assert artifact.region.right <= spectrum.region.x
            assert spectrum.region.bottom <= queue.region.y

            art_w, art_h = stage.get_art_dimensions()
            assert art_w > 32
            assert art_h > 14

    asyncio.run(_test())
