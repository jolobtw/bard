"""Tests for bottom command deck widgets: ArtifactPanel, QueuePanel, ControlsPanel."""

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

            title_plain = panel.query_one("#track-title", Static).render().plain
            assert title_plain.strip() == "Select Music"
            assert not any(r in title_plain for r in ("ᛟ", "ᛉ", "☉", "ᛗ", "ᛜ"))
            assert "Press [Tab] to explore" in str(panel.query_one("#track-meta", Static).render())
            assert "ARCANE RESONANCE" not in str(panel.query_one("#art-box", Static).render())
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

            hdr_text = str(panel.query_one("#art-header", Static).render())
            assert "NOW PLAYING" in hdr_text
            assert "ARTIFACT COVER" not in hdr_text
            assert "01/05" in hdr_text
            assert "Chronomancer" in str(panel.query_one("#track-meta", Static).render())
            assert "Codex" in str(panel.query_one("#track-source", Static).render())
            codec_text = str(panel.query_one("#track-codec", Static).render())
            assert "OPUS" not in codec_text
            assert "48kHz" not in codec_text
            assert "Synthwave" in codec_text
            for sel in ("#track-title", "#track-meta", "#track-source", "#track-codec"):
                assert panel.query_one(sel, Static).styles.content_align == ("center", "middle")

            # Marquee scrolls long title with no rune prefix
            t_before = panel.query_one("#track-title", Static).render().plain
            assert not any(r in t_before for r in ("ᛟ", "ᛉ", "☉", "ᛗ", "ᛜ"))
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


def test_artifact_panel_displays_art_after_empty_mount():
    import io
    from unittest.mock import MagicMock, patch
    from PIL import Image
    from bard.ui.stage_widgets import ArtifactPanel

    img = Image.new("RGB", (16, 16), color=(255, 123, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    resp = MagicMock()
    resp.status_code = 200
    resp.content = buf.getvalue()

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ArtifactPanel()

    async def _run():
        app = TestApp()
        with patch("bard.art.requests.get", return_value=resp):
            async with app.run_test(size=(120, 36)) as pilot:
                panel = app.query_one(ArtifactPanel)
                await pilot.pause()
                art_box = panel.query_one("#art-box", Static)
                assert art_box.size.height == 0

                panel.set_track(
                    {
                        "id": "trk_art",
                        "title": "With Art",
                        "artist": "Artist",
                        "album": "Album",
                        "album_art_url": "https://example.com/test_cover_after_empty.jpg",
                    },
                    queue_pos=(1, 1),
                )
                await pilot.pause()
                assert art_box.size.width >= 14
                assert art_box.size.height >= 5
                assert "▁" in art_box.render().plain
                art_center = panel.query_one("#art-center")
                left_pad = art_box.region.x - art_center.region.x
                right_pad = art_center.region.right - art_box.region.right
                assert left_pad > 0 and abs(left_pad - right_pad) <= 1

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

            assert len(panel.query("#queue-footer")) == 0
            assert panel.selected_original_index() == 0

            # Filter to "obelisk" -> index 1 in original queue
            panel.focus_filter()
            q_input = panel.query_one("#queue-filter", Input)
            q_input.value = "obelisk"
            await pilot.pause()
            assert "Obsidian Obelisk" in panel.query_one("#queue-list").render().plain
            assert panel.selected_original_index() == 1

            # Blur keeping filter -> still filtered, cursor navigable
            panel.blur_filter(clear=False)
            await pilot.pause()
            assert panel.has_filter_text() is True
            assert panel.selected_original_index() == 1

            # Filter to zero matches -> safe empty message, cursor returns None
            q_input.value = "zzzzz_no_match"
            await pilot.pause()
            assert "No tracks in queue" in panel.query_one("#queue-list").render().plain
            panel.move_cursor(1)
            assert panel.selected_original_index() is None

            # Clear filter restores all 3 tracks; clicking row 2 triggers on_select_index(2)
            panel.clear_filter()
            await pilot.pause()
            assert "Solar Eclipse" in panel.query_one("#queue-list").render().plain
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
            assert calls[:5] == ["prev", "play", "next", "shuffle", "repeat"]
            assert len(panel.query("#output-route")) == 0
            assert "AUDIO SINK" not in str(panel.query_one("#controls-header", Static).render())

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
            assert "●" in str(panel.query_one("#volume-control", VolumeBar).render())

            # Orange Powerline play/pause pill flanked by Prev and Next icons on a single compact row
            btn_prev = panel.query_one("#btn-prev")
            btn_play = panel.query_one("#btn-play")
            btn_next = panel.query_one("#btn-next")
            play_plain = btn_play.render().plain
            assert "\ue0b6" in play_plain and "\ue0b4" in play_plain
            assert "󰏤" in play_plain
            assert "󰒮" in btn_prev.render().plain
            assert "󰒭" in btn_next.render().plain
            assert btn_prev.region.y == btn_play.region.y == btn_next.region.y
            assert btn_prev.region.x < btn_play.region.x < btn_next.region.x
            assert panel.query_one("#transport-row").size.height == 1

            panel.set_state(
                is_playing=False,
                has_track=True,
                shuffle_enabled=True,
                repeat_mode="one",
                volume=64,
            )
            await pilot.pause()
            assert "󰐊" in btn_play.render().plain

            # VolumeBar speaker icon on left (unmuted 󰕾, muted 󰖁), borderless container, pct centered below bar
            vol_box = panel.query_one("#volume-box")
            vol_bar = panel.query_one("#volume-control", VolumeBar)
            vol_pct = panel.query_one("#vol-pct", Static)
            mute_btn = panel.query_one("#vol-mute-btn")
            assert vol_box.styles.border_top[0] in ("", "none")
            assert len(panel.query("#vol-label")) == 0
            assert "M: MUTE" not in str(mute_btn.render())
            assert "󰕾" in mute_btn.render().plain
            assert mute_btn.region.y == vol_bar.region.y
            assert mute_btn.region.x < vol_bar.region.x
            assert vol_pct.region.y == vol_bar.region.y + 1

            panel.set_volume(0)
            await pilot.pause()
            assert "󰖁" in mute_btn.render().plain

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


def test_markup_escaping_in_dynamic_track_and_device_strings():
    from bard.ui.header import ArcaneHeader
    from bard.ui.stage_widgets import ArtifactPanel, QueuePanel

    tricky_title = "Broken [/] Title [Official Audio]"
    tricky_artist = "Artist [Feat. X][/]"
    tricky_device = "DAC [ASIO][/]"

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ArcaneHeader(is_playing=True, device_name=tricky_device)
            yield ArtifactPanel()
            yield QueuePanel()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            art = app.query_one(ArtifactPanel)
            q = app.query_one(QueuePanel)

            t = Track("id1", tricky_title, tricky_artist, "Album [Deluxe][/]", 200, "")
            q.set_queue([t], 0)
            art.set_track(
                {"id": "id1", "title": tricky_title, "artist": tricky_artist, "album": "Album [Deluxe][/]", "album_art_url": ""},
                queue_pos=(1, 1),
            )
            await pilot.pause()

            assert "[Official Audio]" in art.query_one("#track-title", Static).render().plain
            assert "[/]" in art.query_one("#track-title", Static).render().plain
            assert "[Official Audio]" in q.query_one("#queue-list").render().plain
            assert "[ASIO][/]" in app.query_one(ArcaneHeader).render().plain

    asyncio.run(_run())


def test_compact_80x24_no_clipping():
    from bard.ui.header import ArcaneHeader
    from bard.ui.zen_stage import ZenStage

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ArcaneHeader(is_playing=False, device_name="Bard")
            yield ZenStage()

    async def _run():
        app_std = TestApp()
        async with app_std.run_test(size=(110, 40)) as pilot:
            stage = app_std.query_one(ZenStage)
            await pilot.pause()
            assert len(stage.query("#spectrum-header")) == 0
            assert len(stage.query("#status-footer")) == 0
            assert len(stage.query("#output-route")) == 0
            assert len(stage.query("#queue-footer")) == 0
            assert len(stage.query("#controls-header")) == 0

            from bard.ui.spectrum import SpectrumDeck
            from bard.ui.stage_widgets import ArtifactPanel, ControlsPanel, QueuePanel
            right_pane = stage.query_one("#right-pane")
            assert [type(c) for c in right_pane.children] == [SpectrumDeck, QueuePanel]
            art_panel = stage.query_one(ArtifactPanel)
            queue_panel = stage.query_one(QueuePanel)
            assert art_panel.query_one(ControlsPanel).id == "controls-panel"
            assert queue_panel.size.width > art_panel.size.width

        app_compact = TestApp()
        async with app_compact.run_test(size=(80, 24)) as pilot:
            stage = app_compact.query_one(ZenStage)
            stage.set_queue([Track("1", "Track One", "Artist", "Album", 120, "")], 0)
            stage.update_playback({"id": "1", "title": "Track One", "artist": "Artist", "duration_ms": 120000, "is_playing": True, "album_art_url": "", "volume": 70})
            await pilot.pause()

            assert stage.query_one("#volume-control").region.bottom <= 24

    asyncio.run(_run())


def test_transparent_terminal_background_and_ansi_patch():
    from rich.color import Color as RichColor
    from rich.style import Style as RichStyle
    from textual.strip import Strip
    from bard.ui.header import ArcaneHeader
    from bard.ui.spectrum import SeekBar, SpectrumDeck
    from bard.ui.stage_widgets import ArtifactPanel, ControlsPanel, QueuePanel
    from bard.ui.transparency import enable_terminal_transparency
    from bard.ui.zen_stage import ZenStage

    enable_terminal_transparency()

    style_black = RichStyle(color=RichColor.parse("#FF9E2C"), bgcolor=RichColor.parse("#000000"))
    ansi_black = Strip.render_ansi(style_black, color_system=3)
    assert "48;2;0;0;0" not in ansi_black
    assert "38;2;255;158;44" in ansi_black

    style_pill = RichStyle(color=RichColor.parse("#0D0E11"), bgcolor=RichColor.parse("#FF7B00"))
    ansi_pill = Strip.render_ansi(style_pill, color_system=3)
    assert "48;2;255;123;0" in ansi_pill

    class TestApp(App):
        CSS = "App, Screen { background: transparent; }"

        def compose(self) -> ComposeResult:
            yield ArcaneHeader(is_playing=False, device_name="Bard")
            yield ZenStage()

    async def _run():
        app = TestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            for selector_or_cls in (
                ArcaneHeader,
                ZenStage,
                SpectrumDeck,
                SeekBar,
                ArtifactPanel,
                QueuePanel,
                ControlsPanel,
            ):
                w = app.query_one(selector_or_cls)
                assert w.styles.background.a == 0.0

            play_spans = app.query_one("#btn-play").render().spans
            # Powerline caps (first & last chars) must have no opaque panel bgcolor
            cap_styles = [s for s in play_spans if s.start == 0]
            assert all(s.style.bgcolor is None for s in cap_styles)

    asyncio.run(_run())


def test_artifact_panel_sixel_mode_renders_sixel_lines():
    import io
    from unittest.mock import MagicMock, patch
    from PIL import Image as PILImage
    from textual.geometry import Region
    from textual_image.widget import SixelImage, SixelRenderable
    import bard.ui.stage_widgets as sw

    img = PILImage.new("RGB", (32, 32), color=(255, 123, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    resp = MagicMock(status_code=200, content=buf.getvalue())

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield sw.ArtifactPanel()

    async def _run():
        with (
            patch.object(sw, "_TextualAutoImage", SixelImage),
            patch.object(sw, "_TextualAutoRenderable", SixelRenderable),
            patch("bard.art.requests.get", return_value=resp),
        ):
            app = TestApp()
            async with app.run_test(size=(120, 42)) as pilot:
                panel = app.query_one(sw.ArtifactPanel)
                panel.set_track(
                    {
                        "id": "trk_sixel",
                        "title": "Sixel Track",
                        "artist": "Artist",
                        "album": "Album",
                        "album_art_url": "https://example.com/sixel_regression.jpg",
                    },
                    queue_pos=(1, 1),
                )
                await pilot.pause()
                box = panel.query_one("#art-box", SixelImage)
                assert box.size.width >= 30 and box.size.height >= 15
                assert box.image is not None and box.image.size == (32, 32)  # Borderless in Sixel mode
                assert len(box.children) == 1
                lines = box.children[0].render_lines(Region(0, 0, box.size.width, box.size.height))
                assert any("\x1bP" in seg.text for ln in lines for seg in ln)

    asyncio.run(_run())
