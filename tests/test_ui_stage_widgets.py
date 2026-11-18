"""Tests for bottom command deck widgets: ArtifactPanel, QueuePanel, ControlsPanel, StatusFooter."""

import asyncio
from textual.app import App, ComposeResult
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import Input, Static

from bard.models import Track


def test_artifact_panel_empty_active_codec_and_marquee():
    from bard.ui.stage_widgets import ArtifactPanel

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ArtifactPanel()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(40, 32)) as pilot:
            panel = app.query_one(ArtifactPanel)
            await pilot.pause()

            assert "Select Music" in str(panel.query_one("#track-title", Static).render())
            assert "Press [Tab] to explore" in str(panel.query_one("#track-meta", Static).render())
            assert "ARCANE RESONANCE" in str(panel.query_one("#art-box", Static).render())
            assert "--/--" in str(panel.query_one("#art-header", Static).render())

            long_title = "An Extraordinary Symphony of Arcane Echoes and Shadows"
            panel.set_track(
                {
                    "id": "trk_99",
                    "title": long_title,
                    "artist": "Chronomancer",
                    "album": "Codex",
                    "playlist_source": "Synthwave",
                    "album_art_url": "",
                    "is_playing": True,
                },
                queue_pos=(1, 5),
                audio_info={"codec": "opus", "samplerate": 48000},
            )
            await pilot.pause()

            assert "01/05" in str(panel.query_one("#art-header", Static).render())
            assert "Chronomancer" in str(panel.query_one("#track-meta", Static).render())
            assert "Codex" in str(panel.query_one("#track-source", Static).render())
            codec_text = str(panel.query_one("#track-codec", Static).render())
            assert "[OPUS · 48kHz]" in codec_text
            assert "FLAC" not in codec_text
            assert "BPM" not in codec_text

            # Marquee scrolls long title
            t_before = str(panel.query_one("#track-title", Static).render())
            panel._marquee_pause = 0
            panel._advance_title_marquee()
            t_after = str(panel.query_one("#track-title", Static).render())
            assert t_after != t_before

            # Empty audio_info omits codec badge cleanly
            panel.set_track(
                {"id": "trk_1", "title": "Short", "artist": "Art", "album": "", "album_art_url": ""},
                queue_pos=(1, 1),
                audio_info={},
            )
            await pilot.pause()
            assert str(panel.query_one("#track-codec", Static).render()) == ""

    asyncio.run(_run())


def test_queue_panel_filter_cursor_empty_match_and_click():
    from bard.ui.stage_widgets import QueuePanel

    selected = []
    tracks = [
        Track("t1", "Aetheric Astrolabe", "Chronomancer", "Codex", 214, ""),
        Track("t2", "Obsidian Obelisk", "Vanguard", "Codex", 248, ""),
        Track("t3", "Solar Eclipse", "Vanguard", "Horizon", 196, ""),
    ]

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield QueuePanel(on_select_index=lambda idx: selected.append(idx))

    async def _run():
        app = TestApp()
        async with app.run_test(size=(44, 24)) as pilot:
            panel = app.query_one(QueuePanel)
            panel.set_queue(tracks, current_index=0)
            await pilot.pause()

            assert "ARCHIVE: 3/3 TRACKS" in str(panel.query_one("#queue-footer", Static).render())
            assert panel.selected_original_index() == 0

            # Filter to "obelisk" -> index 1 in original queue
            panel.focus_filter()
            q_input = panel.query_one("#queue-filter", Input)
            q_input.value = "obelisk"
            await pilot.pause()
            assert "ARCHIVE: 1/3 TRACKS" in str(panel.query_one("#queue-footer", Static).render())
            assert panel.selected_original_index() == 1

            # Blur keeping filter -> still filtered, cursor navigable
            panel.blur_filter(clear=False)
            await pilot.pause()
            assert panel.has_filter_text() is True
            assert panel.selected_original_index() == 1

            # Filter to zero matches -> safe ARCHIVE: 0/3, SEL: --, cursor returns None
            q_input.value = "zzzzz_no_match"
            await pilot.pause()
            footer_empty = str(panel.query_one("#queue-footer", Static).render())
            assert "ARCHIVE: 0/3 TRACKS" in footer_empty
            assert "SEL: --" in footer_empty
            panel.move_cursor(1)
            assert panel.selected_original_index() is None

            # Clear filter restores all 3 tracks; clicking row 2 triggers on_select_index(2)
            panel.clear_filter()
            await pilot.pause()
            assert "ARCHIVE: 3/3 TRACKS" in str(panel.query_one("#queue-footer", Static).render())
            await pilot.click("#queue-list", offset=(4, 2))
            assert selected[-1] == 2

    asyncio.run(_run())


def test_controls_panel_non_focusable_buttons_volume_and_output_route():
    from bard.ui.stage_widgets import ControlsPanel, VolumeBar

    calls = []

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ControlsPanel(
                on_prev=lambda: calls.append("prev"),
                on_play_pause=lambda: calls.append("play"),
                on_next=lambda: calls.append("next"),
                on_shuffle=lambda: calls.append("shuffle"),
                on_repeat=lambda: calls.append("repeat"),
                on_volume=lambda v: calls.append(("vol", v)),
                on_mute=lambda: calls.append("mute"),
                on_cycle_device=lambda: calls.append("device"),
            )

    async def _run():
        app = TestApp()
        async with app.run_test(size=(44, 22)) as pilot:
            panel = app.query_one(ControlsPanel)
            await pilot.pause()

            for btn_id in ("#btn-prev", "#btn-play", "#btn-next", "#btn-shuffle", "#btn-repeat"):
                w = panel.query_one(btn_id)
                assert w.can_focus is False

            await pilot.click("#btn-prev")
            await pilot.click("#btn-play")
            await pilot.click("#btn-next")
            await pilot.click("#btn-shuffle")
            await pilot.click("#btn-repeat")
            await pilot.click("#output-route")
            assert calls[:6] == ["prev", "play", "next", "shuffle", "repeat", "device"]

            panel.set_state(
                is_playing=True,
                has_track=True,
                shuffle_enabled=True,
                repeat_mode="one",
                volume=64,
                device_name="WASAPI // Speakers",
            )
            await pilot.pause()
            assert "LOOP: ONE" in str(panel.query_one("#btn-repeat").render())
            assert "SHUF: ON" in str(panel.query_one("#btn-shuffle").render())
            assert "WASAPI // Speakers" in str(panel.query_one("#output-route").render())

            # VolumeBar mute toggle & slider drag/click clamping
            vol_bar = panel.query_one("#volume-control", VolumeBar)
            await pilot.click("#vol-mute-btn")
            assert "mute" in calls

            vw = vol_bar.size.width
            vol_bar.on_mouse_down(MouseDown(vol_bar, x=0, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            vol_bar.on_mouse_move(MouseMove(vol_bar, x=vw + 10, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            vol_bar.on_mouse_up(MouseUp(vol_bar, x=vw + 10, y=0, delta_x=0, delta_y=0, button=1, shift=False, meta=False, ctrl=False))
            assert ("vol", 100) in calls

    asyncio.run(_run())


def test_status_footer_truthful_content():
    from bard.ui.stage_widgets import StatusFooter

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield StatusFooter()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 5)) as pilot:
            footer = app.query_one(StatusFooter)
            footer.set_status("RESONATING // OPUS 48kHz")
            await pilot.pause()
            text = str(footer.render())
            assert "BARD // UTF-8" in text
            assert "24-BIT TRUECOLOR" in text
            assert "RESONATING // OPUS 48kHz" in text
            assert "/dev/pts/0" not in text

    asyncio.run(_run())
