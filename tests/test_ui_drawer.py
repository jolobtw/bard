"""Tests for CurtainDrawer widget with YouTube Music."""

from unittest.mock import MagicMock
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import OptionList, Input, Static

from bard.ui.curtain_drawer import CurtainDrawer
from bard.models import Track


def test_drawer_initialization_with_ytmusic():
    """Verify CurtainDrawer initializes with client keyword argument and tracks models."""
    mock_client = MagicMock()
    mock_client.get_trending.return_value = [
        Track(id="1", title="Enemy", artist="Imagine Dragons", album="Arcane", duration_seconds=173, thumbnail_url="")
    ]
    mock_play = MagicMock()
    drawer = CurtainDrawer(client=mock_client, on_play=mock_play)
    assert drawer is not None
    assert drawer.client == mock_client
    assert drawer.on_play == mock_play
    assert drawer.is_open() is False
    drawer.toggle()
    assert drawer.is_open() is True
    drawer.hide()
    assert drawer.is_open() is False


def test_drawer_categories_list():
    """Verify predefined categories match specification."""
    mock_client = MagicMock()
    drawer = CurtainDrawer(client=mock_client)
    category_names = [c["name"] for c in drawer.categories]
    assert "🔥 Trending Hits" in category_names
    assert "⚡ Arcane & Cyberpunk" in category_names
    assert "☕ Lo-Fi Beats" in category_names
    assert "🌌 Synthwave Chill" in category_names
    assert "🔍 Search Tracks..." in category_names


def test_drawer_loads_trending_on_open():
    """Verify opening drawer loads trending tracks into right column."""
    mock_client = MagicMock()
    sample_tracks = [
        Track(id="t1", title="Enemy", artist="Imagine Dragons", album="Arcane", duration_seconds=173, thumbnail_url=""),
        Track(id="t2", title="Dynasties & Dystopia", artist="Denzel Curry", album="Arcane", duration_seconds=178, thumbnail_url=""),
    ]
    mock_client.get_trending.return_value = sample_tracks

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            assert not drawer.is_open()
            drawer.toggle()
            assert drawer.is_open()

            # Wait for background worker to populate
            await asyncio.sleep(0.1)
            mock_client.get_trending.assert_called()
            tlist = drawer.query_one("#track-list", OptionList)
            assert tlist.option_count == 2
            first_prompt = str(tlist.get_option_at_index(0).prompt)
            assert "Enemy" in first_prompt
            assert "Imagine Dragons" in first_prompt
            assert "02:53" in first_prompt

    asyncio.run(_test())


def test_drawer_category_switch():
    """Verify selecting different categories triggers appropriate client searches."""
    mock_client = MagicMock()
    mock_client.get_trending.return_value = []
    mock_client.search.return_value = [
        Track(id="lofi1", title="Chill Beat", artist="Lofi Girl", album="Beats", duration_seconds=120, thumbnail_url="")
    ]

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.05)

            # Switch to category 2 (Lo-Fi Beats)
            drawer.select_category(2)
            await asyncio.sleep(0.1)
            mock_client.search.assert_called_with("lofi hip hop chill beats")
            tlist = drawer.query_one("#track-list", OptionList)
            assert tlist.option_count == 1
            assert "Chill Beat" in str(tlist.get_option_at_index(0).prompt)

    asyncio.run(_test())


def test_drawer_search_input_submission():
    """Verify typing query into search input searches YouTube Music."""
    mock_client = MagicMock()
    mock_client.get_trending.return_value = []
    mock_client.search.return_value = [
        Track(id="s1", title="Resonance", artist="HOME", album="Odyssey", duration_seconds=212, thumbnail_url="")
    ]

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.05)

            drawer.open_search()
            search_input = drawer.query_one("#search-input", Input)
            assert search_input.has_class("-visible")

            # Simulate submitting query
            search_input.value = "HOME Resonance"
            await drawer.on_input_submitted(Input.Submitted(search_input, value="HOME Resonance"))
            await asyncio.sleep(0.1)

            mock_client.search.assert_called_with("HOME Resonance")
            tlist = drawer.query_one("#track-list", OptionList)
            assert tlist.option_count == 1
            assert "Resonance" in str(tlist.get_option_at_index(0).prompt)

    asyncio.run(_test())


def test_drawer_select_track_invokes_on_play():
    """Verify selecting a track from tracklist calls on_play(track) and closes drawer."""
    mock_client = MagicMock()
    target_track = Track(id="t1", title="Enemy", artist="Imagine Dragons", album="Arcane", duration_seconds=173, thumbnail_url="")
    mock_client.get_trending.return_value = [target_track]
    mock_play = MagicMock()

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client, on_play=mock_play)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.1)

            tlist = drawer.query_one("#track-list", OptionList)
            # Select first track
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(0), 0))
            mock_play.assert_called_once_with(target_track)
            assert not drawer.is_open()

    asyncio.run(_test())


def test_drawer_empty_search_results():
    """Verify empty search results display friendly notice without crashing."""
    mock_client = MagicMock()
    mock_client.get_trending.return_value = []

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.1)

            tlist = drawer.query_one("#track-list", OptionList)
            assert tlist.option_count == 1
            assert "No tracks found" in str(tlist.get_option_at_index(0).prompt)

    asyncio.run(_test())


def test_drawer_keyboard_navigation_and_search_shortcut():
    """Verify '/' opens search and arrow keys navigate columns."""
    from textual import events

    mock_client = MagicMock()
    mock_client.get_trending.return_value = [
        Track(id="t1", title="Enemy", artist="Imagine Dragons", album="Arcane", duration_seconds=173, thumbnail_url="")
    ]

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.1)

            search_input = drawer.query_one("#search-input", Input)
            assert not search_input.has_class("-visible")

            # Press '/' to open search
            drawer.on_key(events.Key("slash", "slash"))
            assert search_input.has_class("-visible")

            # Press Escape while in search to close it
            search_input.focus()
            drawer.on_key(events.Key("escape", "escape"))
            assert not search_input.has_class("-visible")

            # Switch right with 'right' key
            drawer.on_key(events.Key("right", "right"))
            await asyncio.sleep(0.05)
            tlist = drawer.query_one("#track-list", OptionList)
            assert tlist.has_focus

            # Switch left with 'left' key
            drawer.on_key(events.Key("left", "left"))
            await asyncio.sleep(0.05)
            clist = drawer.query_one("#category-list", OptionList)
            assert clist.has_focus

    asyncio.run(_test())


def test_drawer_backward_compatibility_selectors_and_properties():
    """Verify legacy playlist selectors and properties resolve seamlessly."""
    mock_client = MagicMock()
    drawer = CurtainDrawer(spotify_client=mock_client)
    assert drawer.client == mock_client
    assert drawer.playlists == drawer.categories

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            # Query legacy #playlist-list and #playlist-header
            plist = drawer.query_one("#playlist-list", OptionList)
            phead = drawer.query_one("#playlist-header", Static)
            pcol = drawer.query_one("#playlist-column")
            assert plist.id == "category-list"
            assert phead.id == "category-header"
            assert pcol.id == "category-column"

    asyncio.run(_test())

