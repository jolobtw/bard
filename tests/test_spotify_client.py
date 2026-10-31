"""Test Spotify Web API Client."""

from unittest.mock import MagicMock, patch
from bard.config import BardConfig
from bard.spotify_client import SpotifyClient, generate_pkce_pair


def test_pkce_generation():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert verifier != challenge


def test_get_playback_state(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    
    client = SpotifyClient(cfg)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "is_playing": True,
        "progress_ms": 60000,
        "item": {
            "name": "Starboy",
            "duration_ms": 230000,
            "artists": [{"name": "The Weeknd"}, {"name": "Daft Punk"}],
            "album": {
                "name": "Starboy",
                "images": [{"url": "https://example.com/art.jpg"}],
            },
        },
        "device": {"name": "Bard", "volume_percent": 80},
    }
    
    with patch("requests.get", return_value=mock_response):
        state = client.get_playback()
        assert state is not None
        assert state["title"] == "Starboy"
        assert state["artist"] == "The Weeknd, Daft Punk"
        assert state["album"] == "Starboy"
        assert state["duration_ms"] == 230000
        assert state["progress_ms"] == 60000
        assert state["is_playing"] is True
        assert state["volume"] == 80
        assert state["album_art_url"] == "https://example.com/art.jpg"


def test_get_playlists_both_schemas(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    # Modern schema: total is inside 'items'
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {"id": "p1", "name": "Vibes", "items": {"total": 42}, "uri": "spotify:playlist:p1"},
            {"id": "p2", "name": "Chill", "tracks": {"total": 15}, "uri": "spotify:playlist:p2"},
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        playlists = client.get_playlists()
        assert len(playlists) == 2
        assert playlists[0]["tracks_count"] == 42
        assert playlists[1]["tracks_count"] == 15


def test_get_playlist_tracks_items_schema(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "item": {
                    "id": "t1",
                    "name": "Dance Yrself Clean",
                    "artists": [{"name": "LCD Soundsystem"}],
                    "duration_ms": 536000,
                    "uri": "spotify:track:t1",
                }
            }
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        tracks = client.get_playlist_tracks("p1")
        assert len(tracks) == 1
        assert tracks[0]["name"] == "Dance Yrself Clean"
        assert tracks[0]["artist"] == "LCD Soundsystem"
        assert tracks[0]["duration_str"] == "08:56"
