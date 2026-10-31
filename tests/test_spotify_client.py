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
