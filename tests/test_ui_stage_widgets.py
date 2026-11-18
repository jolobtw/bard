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

            # VolumeBar mute toggle & slider drag/click clamping (single click fires once)
            vol_bar = panel.query_one("#volume-control", VolumeBar)
            await pilot.click("#vol-mute-btn")
            assert "mute" in calls

            vol_calls_before = [c for c in calls if isinstance(c, tuple) and c[0] == "vol"]
            await pilot.click("#volume-control", offset=(2, 0))
            vol_calls_after = [c for c in calls if isinstance(c, tuple) and c[0] == "vol"]
            assert len(vol_calls_after) == len(vol_calls_before) + 1

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


def test_markup_escaping_in_dynamic_track_and_device_strings():
    from bard.ui.header import ArcaneHeader
    from bard.ui.stage_widgets import ArtifactPanel, QueuePanel, StatusFooter, _OutputRouteBox

    tricky_title = "Broken [/] Title [Official Audio]"
    tricky_artist = "Artist [Feat. X][/]"
    tricky_device = "DAC [ASIO][/]"

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ArcaneHeader(is_playing=True, device_name=tricky_device)
            yield ArtifactPanel()
            yield QueuePanel()
            yield _OutputRouteBox()
            yield StatusFooter()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            art = app.query_one(ArtifactPanel)
            q = app.query_one(QueuePanel)
            out = app.query_one(_OutputRouteBox)
            ftr = app.query_one(StatusFooter)

            t = Track("id1", tricky_title, tricky_artist, "Album [Deluxe][/]", 200, "")
            q.set_queue([t], 0)
            art.set_track(
                {"id": "id1", "title": tricky_title, "artist": tricky_artist, "album": "Album [Deluxe][/]", "album_art_url": ""},
                queue_pos=(1, 1),
            )
            out.set_device(tricky_device)
            ftr.set_status("PLAYING // [OPUS][/]")
            await pilot.pause()

            assert "[Official Audio]" in art.query_one("#track-title", Static).render().plain
            assert "[/]" in art.query_one("#track-title", Static).render().plain
            assert "[Official Audio]" in q.query_one("#queue-list").render().plain
            assert "[ASIO][/]" in out.render().plain
            assert "[/]" in ftr.render().plain
            assert "[ASIO][/]" in app.query_one(ArcaneHeader).render().plain

    asyncio.run(_run())


def test_output_route_box_two_lines_and_compact_80x24_no_clipping():
    from bard.ui.header import ArcaneHeader
    from bard.ui.zen_stage import ZenStage

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ArcaneHeader(is_playing=False, device_name="Bard")
            yield ZenStage()

    async def _run():
        # Standard size: _OutputRouteBox content height >= 2 so device line is visible
        app_std = TestApp()
        async with app_std.run_test(size=(110, 40)) as pilot:
            stage = app_std.query_one(ZenStage)
            stage.set_audio_device("Speakers (Realtek)")
            await pilot.pause()
            out_box = stage.query_one("#output-route")
            assert out_box.content_size.height >= 2
            assert "Speakers (Realtek)" in out_box.render().plain

        # Compact 80x24: key controls, queue footer SEL, and spectrum header fit cleanly
        app_compact = TestApp()
        async with app_compact.run_test(size=(80, 24)) as pilot:
            stage = app_compact.query_one(ZenStage)
            stage.set_queue([Track("1", "Track One", "Artist", "Album", 120, "")], 0)
            stage.update_playback({"id": "1", "title": "Track One", "artist": "Artist", "duration_ms": 120000, "is_playing": True, "album_art_url": "", "volume": 70})
            await pilot.pause()

            spec_hdr = stage.query_one("#spectrum-header", Static)
            assert "RESONATING" in spec_hdr.render().plain
            assert len(spec_hdr.render().plain.splitlines()) == 1

            q_ftr = stage.query_one("#queue-footer", Static)
            assert "SEL:" in q_ftr.render().plain

            out_box = stage.query_one("#output-route")
            assert out_box.region.bottom <= 24
            assert stage.query_one("#volume-control").region.bottom <= 24

    asyncio.run(_run())
