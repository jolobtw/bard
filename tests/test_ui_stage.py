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


def test_render_arcane_bar_gradient():
    from bard.ui.zen_stage import render_arcane_bar
    half_bar = render_arcane_bar(filled=5, unfilled=5)
    assert "#FF4500" in half_bar
    assert "#FFD166" not in half_bar  # Gradient spans full width, so midpoint hasn't reached gold yet
    assert "●" in half_bar
    assert "─" * 5 in half_bar

    full_bar = render_arcane_bar(filled=10, unfilled=0)
    assert "#FF4500" in full_bar
    assert "#FFD166" in full_bar


def test_zen_stage_empty_state_rendering():
    from textual.app import App, ComposeResult
    from bard.ui.zen_stage import ZenStage
    from textual.widgets import Static
    import asyncio

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        app = TestApp()
        async with app.run_test():
            stage = app.query_one(ZenStage)
            stage.refresh_stage()
            title = stage.query_one("#track-title", Static)
            assert "Select Music" in str(title.render())
            art_center = stage.query_one("#art-center")
            assert art_center.display is False
            art = stage.query_one("#art-box", Static)
            assert str(art.render()) == ""

            # Verify transition to playing state displays art and title
            stage.update_playback({
                "title": "Arcane Echoes",
                "artist": "Vi & Jinx",
                "album": "Piltover Nights",
                "duration_ms": 180000,
                "progress_ms": 30000,
                "is_playing": True,
                "album_art_url": "",
                "volume": 75,
                "device_name": "Studio Monitors",
            })
            assert art_center.display is True
            assert "Arcane Echoes" in str(title.render())

            # Transition back to empty state
            stage.update_playback(None)
            assert art_center.display is False
            assert "Select Music" in str(title.render())

    asyncio.run(_test())


def test_zen_stage_responsive_art_sizing():
    from textual.app import App, ComposeResult
    from bard.ui.zen_stage import ZenStage
    import asyncio

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        # Compact terminal (<32 height or <86 width)
        app_compact = TestApp()
        async with app_compact.run_test(size=(80, 24)):
            stage = app_compact.query_one(ZenStage)
            assert stage.get_art_dimensions() == (32, 14)

        # Hero terminal (>=32 height and >=86 width)
        app_hero = TestApp()
        async with app_hero.run_test(size=(100, 40)):
            stage = app_hero.query_one(ZenStage)
            assert stage.get_art_dimensions() == (46, 20)

    asyncio.run(_test())


def test_zen_stage_responsive_playback_rendering():
    from textual.app import App, ComposeResult
    from bard.ui.zen_stage import ZenStage
    import asyncio

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        # Compact terminal: art lines should be 14 rows
        app_compact = TestApp()
        async with app_compact.run_test(size=(80, 24)):
            stage = app_compact.query_one(ZenStage)
            stage.update_playback({
                "title": "Song 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "duration_ms": 180000,
                "progress_ms": 30000,
                "is_playing": True,
                "album_art_url": "",
            })
            assert len(stage._cached_art_ansi.split("\n")) == 14

        # Hero terminal: art lines should be 20 rows
        app_hero = TestApp()
        async with app_hero.run_test(size=(100, 40)):
            stage = app_hero.query_one(ZenStage)
            stage.update_playback({
                "title": "Song 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "duration_ms": 180000,
                "progress_ms": 30000,
                "is_playing": True,
                "album_art_url": "",
            })
            assert len(stage._cached_art_ansi.split("\n")) == 20

    asyncio.run(_test())


def test_zen_stage_large_terminal_art_sizing():
    from textual.app import App, ComposeResult
    from bard.ui.zen_stage import ZenStage
    import asyncio

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        app_large = TestApp()
        async with app_large.run_test(size=(120, 48)):
            stage = app_large.query_one(ZenStage)
            assert stage.get_art_dimensions() == (58, 25)

    asyncio.run(_test())


def test_zen_stage_clickable_transport_buttons_and_shuffle():
    from textual.app import App, ComposeResult
    from bard.ui.zen_stage import SeekBar, TransportBar, VolumeBar, ZenStage
    import asyncio

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
            )

    async def _test():
        app = TestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            stage = app.query_one(ZenStage)
            transport = stage.query_one("#transport-controls", TransportBar)
            vol_bar = stage.query_one("#volume-control", VolumeBar)
            seek_bar = stage.query_one("#progress-bar", SeekBar)

            assert transport.is_playing is False
            assert transport.shuffle_enabled is False
            assert transport.repeat_mode == "off"

            # Click each hit-zone inside TransportBar
            await pilot.click("#transport-controls", offset=(1, 1))   # Prev
            await pilot.click("#transport-controls", offset=(8, 1))   # Play pill
            await pilot.click("#transport-controls", offset=(14, 1))  # Next
            await pilot.click("#transport-controls", offset=(6, 3))   # Shuffle (row 3)
            await pilot.click("#transport-controls", offset=(10, 3))  # Repeat (row 3)
            assert calls[:5] == ["prev", "play_pause", "next", "shuffle", "repeat"]

            stage.set_shuffle(True)
            assert transport.shuffle_enabled is True
            stage.set_repeat("one")
            assert transport.repeat_mode == "one"

            stage.update_playback({
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "Test Album",
                "duration_ms": 100000,
                "progress_ms": 10000,
                "is_playing": True,
                "album_art_url": "",
                "volume": 80,
            })
            assert transport.is_playing is True
            assert vol_bar.volume == 80
            await pilot.pause()

            # Click speaker icon on left (x < 3) to mute, and slider bar (x >= 3) to set volume
            await pilot.click("#volume-control", offset=(1, 1))
            assert "mute" in calls
            await pilot.click("#volume-control", offset=(12, 1))
            assert any(isinstance(c, tuple) and c[0] == "vol" for c in calls)

            # Click seek bar on row 0
            await pilot.click("#progress-bar", offset=(seek_bar.size.width // 2, 0))
            assert any(isinstance(c, tuple) and c[0] == "seek" for c in calls)

    asyncio.run(_test())


def test_zen_stage_visual_refinements_footer_pill_border_and_marquee():
    from textual.app import App, ComposeResult
    from textual.widgets import Static
    from bard.ui.zen_stage import SeekBar, ZenStage
    import asyncio

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ZenStage()

    async def _test():
        app = TestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            stage = app.query_one(ZenStage)
            art_box = stage.query_one("#art-box", Static)
            title = stage.query_one("#track-title", Static)
            source = stage.query_one("#track-source", Static)
            hint = stage.query_one("#controls-hint", Static)
            seek_bar = stage.query_one("#progress-bar", SeekBar)
            assert len(stage.query("#track-kicker")) == 0

            stage.refresh_stage()
            await pilot.pause()

            # 1. Single-line shortcut footer
            hint_text = str(hint.render())
            assert "[Tab] Explore" in hint_text
            assert "[Q] Quit" in hint_text
            assert hint.size.height == 1

            # 2. Album art rounded border
            assert art_box.styles.border_top[0] == "round"

            # 3. Status pill & timestamp contrast
            long_title = "An Extraordinary Symphony of Arcane Echoes and Shadows"
            stage.update_playback({
                "title": long_title,
                "artist": "Artist",
                "album": "Album",
                "playlist_source": "Synthwave Favorites",
                "duration_ms": 393000,
                "progress_ms": 185000,
                "is_playing": True,
                "album_art_url": "",
            })
            await pilot.pause()
            assert "Synthwave Favorites" in str(source.render())

            seek_rendered = str(seek_bar.render())
            assert "03:05" in seek_rendered
            assert "/ 06:33" in seek_rendered

            # Paused state keeps metadata clean with no status kicker
            stage.update_playback({
                "title": long_title,
                "artist": "Artist",
                "album": "Album",
                "duration_ms": 393000,
                "progress_ms": 185000,
                "is_playing": False,
                "album_art_url": "",
            })
            await pilot.pause()

            # 4. Marquee scroll advances after initial pause
            initial_visible = str(title.render())
            assert long_title.startswith(initial_visible)
            assert "…" not in initial_visible
            stage._marquee_pause = 0
            stage._advance_title_marquee()
            scrolled_visible = str(title.render())
            assert scrolled_visible != initial_visible
            assert scrolled_visible in long_title

    asyncio.run(_test())



