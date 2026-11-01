"""Test CurtainDrawer widget."""

from unittest.mock import MagicMock
from bard.ui.curtain_drawer import CurtainDrawer


def test_drawer_initialization():
    mock_client = MagicMock()
    mock_client.get_playlists.return_value = [
        {"id": "p1", "name": "Synthwave", "tracks_count": 10, "uri": "spotify:playlist:p1"}
    ]
    mock_client.get_playlist_tracks.return_value = [
        {"id": "t1", "name": "Resonance", "duration_str": "03:32", "uri": "spotify:track:t1"}
    ]
    
    drawer = CurtainDrawer(mock_client)
    assert drawer.is_open() is False
    drawer.add_class("-visible")
    assert drawer.is_open() is True
    drawer.hide()
    assert drawer.is_open() is False


def test_drawer_instant_open_and_loading_state():
    from textual.app import App, ComposeResult
    from textual.widgets import OptionList
    import asyncio
    import time

    mock_client = MagicMock()
    # Simulate a slow network response
    def slow_playlists(*args, **kwargs):
        time.sleep(0.1)
        return [{"id": "p1", "name": "Synthwave", "tracks_count": 1, "uri": "spotify:playlist:p1"}]
    mock_client.get_playlists.side_effect = slow_playlists
    mock_client.get_playlist_tracks.return_value = []

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield CurtainDrawer(mock_client)

    async def _test():
        app = TestApp()
        async with app.run_test():
            drawer = app.query_one(CurtainDrawer)
            assert not drawer.is_open()
            drawer.toggle()
            # Must open immediately
            assert drawer.is_open()
            plist = drawer.query_one("#playlist-list", OptionList)
            # Should show loading prompt
            assert plist.option_count > 0
            opt = plist.get_option_at_index(0)
            assert "Deciphering" in str(opt.prompt) or "Loading" in str(opt.prompt)
            # Wait for background worker to complete
            await asyncio.sleep(0.2)
            assert len(drawer.playlists) == 1
            assert "Synthwave" in str(plist.get_option_at_index(0).prompt)

    asyncio.run(_test())

