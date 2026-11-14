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
    assert ("🔍 Search Music..." in category_names or "🔍 Search Tracks..." in category_names)


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
            lines = first_prompt.split("\n")
            assert len(lines) == 2
            assert "Enemy" in lines[0]
            assert "Imagine Dragons" in lines[1]
            assert "02:53" in lines[1]

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


def test_drawer_populate_tracks_race_condition_protection():
    """Verify _populate_tracks ignores results that do not match active category or search query."""
    mock_client = MagicMock()
    drawer = CurtainDrawer(client=mock_client)
    # Default category index 0 is "trending"
    drawer._current_cat_idx = 0

    stale_tracks = [Track(id="s", title="Stale", artist="A", album="", duration_seconds=100, thumbnail_url="")]
    valid_tracks = [Track(id="v", title="Valid", artist="A", album="", duration_seconds=100, thumbnail_url="")]

    # Stale category response (e.g. from arcane) is ignored
    drawer._populate_tracks("arcane", stale_tracks)
    assert drawer.tracks == []

    # Matching category response is accepted
    drawer._populate_tracks("trending", valid_tracks)
    assert drawer.tracks == valid_tracks

    # Now simulate active search category
    drawer.select_category(4)  # "search" category
    drawer._active_query = "synthwave"

    search_stale = [Track(id="old", title="Old Search", artist="A", album="", duration_seconds=100, thumbnail_url="")]
    search_valid = [Track(id="new", title="New Search", artist="A", album="", duration_seconds=100, thumbnail_url="")]

    # Stale search query is ignored
    drawer._populate_tracks("search:lofi", search_stale)
    assert drawer.tracks == valid_tracks  # Not updated to search_stale

    # Active search query is accepted
    drawer._populate_tracks("search:synthwave", search_valid)
    assert drawer.tracks == search_valid


def test_drawer_search_category_selection_by_id():
    """Verify search is opened by category id matching 'search', not hardcoded index 4."""
    mock_client = MagicMock()
    drawer = CurtainDrawer(client=mock_client)
    # Rearrange categories so "search" is at index 0
    drawer.categories = [
        {"id": "search", "name": "🔍 Search Tracks...", "query": ""},
        {"id": "trending", "name": "🔥 Trending Hits", "query": None},
    ]

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer.toggle()
            await asyncio.sleep(0.05)

            clist = drawer.query_one("#category-list", OptionList)
            # Select index 0 (which is now "search")
            drawer.on_option_list_option_selected(OptionList.OptionSelected(clist, clist.get_option_at_index(0), 0))
            await asyncio.sleep(0.05)

            search_input = drawer.query_one("#search-input", Input)
            assert search_input.has_class("-visible")

    asyncio.run(_test())


def test_drawer_library_categories_when_authenticated():
    """Verify authenticated user gets personal library categories and disconnect action."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    drawer = CurtainDrawer(client=mock_client)
    category_ids = [c["id"] for c in drawer.categories]
    assert "liked" in category_ids
    assert "library_playlists" in category_ids
    assert "history" in category_ids
    assert "disconnect_account" in category_ids
    assert "connect_account" not in category_ids


def test_drawer_library_categories_when_unauthenticated():
    """Verify unauthenticated user gets curated feeds and connect action without library categories."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = False
    drawer = CurtainDrawer(client=mock_client)
    category_ids = [c["id"] for c in drawer.categories]
    assert "liked" not in category_ids
    assert "library_playlists" not in category_ids
    assert "history" not in category_ids
    assert "connect_account" in category_ids
    assert "disconnect_account" not in category_ids
    assert "trending" in category_ids


def test_drawer_refresh_categories():
    """Verify refresh_categories rebuilds category list upon auth change."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = False
    drawer = CurtainDrawer(client=mock_client)
    assert "connect_account" in [c["id"] for c in drawer.categories]

    mock_client.is_authenticated.return_value = True
    drawer.refresh_categories()
    assert "liked" in [c["id"] for c in drawer.categories]
    assert "disconnect_account" in [c["id"] for c in drawer.categories]


def test_drawer_account_callbacks():
    """Verify on_connect_account and on_disconnect_account callbacks are invoked on selection."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = False
    on_connect = MagicMock()
    on_disconnect = MagicMock()

    drawer = CurtainDrawer(
        client=mock_client,
        on_connect_account=on_connect,
        on_disconnect_account=on_disconnect,
    )

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer.toggle()
            await asyncio.sleep(0.05)
            clist = drawer.query_one("#category-list", OptionList)
            # Find connect_account index
            conn_idx = [i for i, c in enumerate(drawer.categories) if c["id"] == "connect_account"][0]
            drawer.on_option_list_option_selected(
                OptionList.OptionSelected(clist, clist.get_option_at_index(conn_idx), conn_idx)
            )
            on_connect.assert_called_once()

            # Now simulate authenticated
            mock_client.is_authenticated.return_value = True
            drawer.refresh_categories()
            await asyncio.sleep(0.05)
            disc_idx = [i for i, c in enumerate(drawer.categories) if c["id"] == "disconnect_account"][0]
            drawer.on_option_list_option_selected(
                OptionList.OptionSelected(clist, clist.get_option_at_index(disc_idx), disc_idx)
            )
            on_disconnect.assert_called_once()

    asyncio.run(_test())


def test_drawer_drill_down_playlist_and_back_navigation():
    """Verify selecting a library playlist drills down into its tracks and back button restores playlists."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.get_library_playlists.return_value = [
        {"id": "PL_1", "title": "Synth Hits", "count": "15", "thumbnail_url": ""},
        {"id": "PL_2", "title": "Arcane Mix", "count": "8", "thumbnail_url": ""},
    ]
    mock_client.get_playlist_tracks.return_value = [
        Track(id="t_pl1", title="Guns for Hire", artist="Woodkid", album="Arcane", duration_seconds=226, thumbnail_url=""),
        Track(id="t_pl2", title="Playground", artist="Bea Miller", album="Arcane", duration_seconds=230, thumbnail_url=""),
    ]
    mock_play = MagicMock()

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client, on_play=mock_play)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.05)

            # Select library_playlists category
            pl_cat_idx = [i for i, c in enumerate(drawer.categories) if c["id"] == "library_playlists"][0]
            drawer.select_category(pl_cat_idx)
            await asyncio.sleep(0.1)

            mock_client.get_library_playlists.assert_called()
            tlist = drawer.query_one("#track-list", OptionList)
            assert tlist.option_count == 2
            assert "Synth Hits" in str(tlist.get_option_at_index(0).prompt)

            # Click second playlist (Arcane Mix) -> drill down
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(1), 1))
            await asyncio.sleep(0.1)

            mock_client.get_playlist_tracks.assert_called_with("PL_2")
            assert len(drawer._nav_stack) == 1

            # In drilled-down view: item 0 must be Back button
            assert tlist.option_count == 3  # 1 back button + 2 tracks
            assert "Back" in str(tlist.get_option_at_index(0).prompt)
            assert "Guns for Hire" in str(tlist.get_option_at_index(1).prompt)

            # Select item 0 (Back button) -> return to playlists
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(0), 0))
            await asyncio.sleep(0.05)

            assert len(drawer._nav_stack) == 0
            assert tlist.option_count == 2
            assert "Synth Hits" in str(tlist.get_option_at_index(0).prompt)
            assert "Arcane Mix" in str(tlist.get_option_at_index(1).prompt)

    asyncio.run(_test())


def test_drawer_drill_down_album_search_and_keyboard_back():
    """Verify selecting an album from search drills down and Backspace/Left navigates back."""
    from textual import events

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = False
    album_item = {
        "id": "MPREb_album1",
        "browse_id": "MPREb_album1",
        "title": "Arcane League of Legends",
        "artist": "Various Artists",
        "year": "2021",
        "thumbnail_url": "",
    }
    song_item = Track(id="s1", title="Enemy", artist="Imagine Dragons", album="Arcane", duration_seconds=173, thumbnail_url="")

    mock_client.search_all.return_value = {
        "songs": [song_item],
        "albums": [album_item],
        "artists": [],
    }
    mock_client.get_album_tracks.return_value = [
        Track(id="a1", title="Playground", artist="Bea Miller", album="Arcane", duration_seconds=230, thumbnail_url="")
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
            s_input = drawer.query_one("#search-input", Input)
            await drawer.on_input_submitted(Input.Submitted(s_input, value="Arcane"))
            await asyncio.sleep(0.1)

            tlist = drawer.query_one("#track-list", OptionList)
            # Both song and album in results
            assert tlist.option_count >= 2

            # Select album item (index 1)
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(1), 1))
            await asyncio.sleep(0.1)

            mock_client.get_album_tracks.assert_called_with("MPREb_album1")
            assert len(drawer._nav_stack) == 1
            assert tlist.option_count == 2  # [Back] + Playground
            assert "Back" in str(tlist.get_option_at_index(0).prompt)

            # Test keyboard backspace navigation
            tlist.focus()
            drawer.on_key(events.Key("backspace", "backspace"))
            await asyncio.sleep(0.05)

            assert len(drawer._nav_stack) == 0
            assert tlist.option_count >= 2

    asyncio.run(_test())


def test_drawer_drill_down_select_track_and_left_key_back():
    """Verify playing a track from drilled-down view works, and 'left' key navigates back."""
    from textual import events

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.get_library_playlists.return_value = [
        {"id": "PL_1", "title": "Lo-Fi Nights", "count": "10", "thumbnail_url": ""}
    ]
    track_1 = Track(id="t1", title="Night Walk", artist="Chill Guy", album="Lofi", duration_seconds=150, thumbnail_url="")
    mock_client.get_playlist_tracks.return_value = [track_1]
    mock_play = MagicMock()

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(client=mock_client, on_play=mock_play)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            drawer.toggle()
            await asyncio.sleep(0.05)

            # Select library_playlists
            pl_idx = [i for i, c in enumerate(drawer.categories) if c["id"] == "library_playlists"][0]
            drawer.select_category(pl_idx)
            await asyncio.sleep(0.05)

            tlist = drawer.query_one("#track-list", OptionList)
            # Drill down into playlist
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(0), 0))
            await asyncio.sleep(0.05)

            assert len(drawer._nav_stack) == 1
            # Option 0 is Back, Option 1 is Night Walk
            assert "Back" in str(tlist.get_option_at_index(0).prompt)
            assert "Night Walk" in str(tlist.get_option_at_index(1).prompt)

            # Test 'left' arrow navigates back when inside drill-down
            tlist.focus()
            drawer.on_key(events.Key("left", "left"))
            await asyncio.sleep(0.05)

            assert len(drawer._nav_stack) == 0
            assert tlist.option_count == 1
            assert "Lo-Fi Nights" in str(tlist.get_option_at_index(0).prompt)

            # Drill down again and play track
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(0), 0))
            await asyncio.sleep(0.05)

            # Select track at index 1
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(1), 1))
            mock_play.assert_called_once_with(track_1)
            assert not drawer.is_open()

    asyncio.run(_test())


def test_drawer_shuffle_shortcut_category_trigger():
    """Verify pressing 's' on a category triggers on_shuffle_play callback."""
    from textual import events

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    drawer = CurtainDrawer(client=mock_client)

    shuffled_payloads = []
    drawer.on_shuffle_play = lambda payload: shuffled_payloads.append(payload)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            clist = drawer.query_one("#category-list", OptionList)
            liked_idx = next(i for i, c in enumerate(drawer.categories) if c["id"] == "liked")
            clist.highlighted = liked_idx

            drawer.on_key(events.Key("s", "s"))
            assert len(shuffled_payloads) == 1
            assert shuffled_payloads[0]["id"] == "liked"
            assert shuffled_payloads[0]["type"] == "category"

    asyncio.run(_test())


def test_drawer_shuffle_shortcut_playlist_trigger():
    """Verify pressing 's' on a user playlist in track list triggers on_shuffle_play."""
    from textual import events

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.get_library_playlists.return_value = [
        {"id": "PL_fav", "title": "My Favorite Tracks", "count": "50", "thumbnail_url": ""}
    ]
    drawer = CurtainDrawer(client=mock_client)

    shuffled_payloads = []
    drawer.on_shuffle_play = lambda payload: shuffled_payloads.append(payload)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            # Open library playlists
            playlists_idx = next(i for i, c in enumerate(drawer.categories) if c["id"] == "library_playlists")
            drawer.select_category(playlists_idx)
            await asyncio.sleep(0.1)

            tlist = drawer.query_one("#track-list", OptionList)
            tlist.focus()
            tlist.highlighted = 0
            await asyncio.sleep(0.05)

            drawer.on_key(events.Key("s", "s"))
            assert len(shuffled_payloads) == 1
            assert shuffled_payloads[0]["id"] == "PL_fav"
            assert shuffled_payloads[0]["title"] == "My Favorite Tracks"
            assert shuffled_payloads[0]["type"] == "playlist"

    asyncio.run(_test())


def test_drawer_shuffle_shortcut_ignored_in_search():
    """Verify pressing 's' when search input is focused is ignored by drawer shuffle."""
    from textual import events

    mock_client = MagicMock()
    drawer = CurtainDrawer(client=mock_client)

    shuffled_payloads = []
    drawer.on_shuffle_play = lambda payload: shuffled_payloads.append(payload)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer.open_search()
            s_input = drawer.query_one("#search-input", Input)
            s_input.focus()

            drawer.on_key(events.Key("s", "s"))
            assert len(shuffled_payloads) == 0

    asyncio.run(_test())


def test_drawer_shuffle_shortcut_in_drilled_down_playlist():
    """Verify pressing 's' while viewing tracks of a drilled-down playlist shuffles that playlist."""
    from textual import events

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.get_library_playlists.return_value = [
        {"id": "PL_fav", "title": "My Favorite Tracks", "count": "50", "thumbnail_url": ""}
    ]
    mock_client.get_playlist_tracks.return_value = [
        Track(id="t1", title="Track 1", artist="Artist", album="Album", duration_seconds=180, thumbnail_url="")
    ]
    drawer = CurtainDrawer(client=mock_client)

    shuffled_payloads = []
    drawer.on_shuffle_play = lambda payload: shuffled_payloads.append(payload)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield drawer

    async def _test():
        app = TestApp()
        async with app.run_test():
            playlists_idx = next(i for i, c in enumerate(drawer.categories) if c["id"] == "library_playlists")
            drawer.select_category(playlists_idx)
            await asyncio.sleep(0.1)

            tlist = drawer.query_one("#track-list", OptionList)
            # Drill down into playlist at index 0
            drawer.on_option_list_option_selected(OptionList.OptionSelected(tlist, tlist.get_option_at_index(0), 0))
            await asyncio.sleep(0.1)

            assert len(drawer._nav_stack) == 1
            tlist.focus()
            tlist.highlighted = 1  # Highlight the track inside the playlist

            drawer.on_key(events.Key("s", "s"))
            assert len(shuffled_payloads) == 1
            assert shuffled_payloads[0]["id"] == "PL_fav"
            assert shuffled_payloads[0]["title"] == "My Favorite Tracks"
            assert shuffled_payloads[0]["type"] == "playlist"

    asyncio.run(_test())





