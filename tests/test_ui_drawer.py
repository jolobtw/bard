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
