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


def test_playlists_and_tracks_caching(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {"id": "p1", "name": "Vibes", "tracks": {"total": 5}, "uri": "spotify:playlist:p1"}
        ]
    }
    with patch("requests.get", return_value=mock_resp) as mock_get:
        p1 = client.get_playlists()
        p2 = client.get_playlists()
        assert p1 == p2
        # Should only have called requests.get once due to caching
        assert mock_get.call_count == 1

    mock_track_resp = MagicMock()
    mock_track_resp.status_code = 200
    mock_track_resp.json.return_value = {
        "items": [
            {"track": {"id": "t1", "name": "Song 1", "artists": [{"name": "Artist 1"}], "duration_ms": 120000, "uri": "spotify:track:t1"}}
        ]
    }
    with patch("requests.get", return_value=mock_track_resp) as mock_get:
        t1 = client.get_playlist_tracks("p1")
        t2 = client.get_playlist_tracks("p1")
        assert t1 == t2
        assert mock_get.call_count == 1


def test_rate_limit_and_quota_handling(tmp_path):
    import time
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "3600"}
    mock_resp.json.return_value = {
        "error": {"status": 429, "message": "Too many requests", "reason": "QUOTA_EXCEEDED"}
    }

    with patch("requests.put", return_value=mock_resp):
        success, msg = client.play()
        assert success is False
        assert "quota" in msg.lower() or "too many requests" in msg.lower()
        assert client.is_rate_limited() is True
        assert client.is_quota_exceeded() is True
        assert client.get_cooldown_seconds() > 3500

    # While rate limited, calls should not trigger network requests
    with patch("requests.put") as mock_put:
        success, msg = client.play()
        assert success is False
        assert mock_put.call_count == 0


def test_get_playlist_tracks_fallback_to_embed_on_403(tmp_path):
    import json
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    # First call: API returns 403 Forbidden
    mock_api_resp = MagicMock()
    mock_api_resp.status_code = 403
    mock_api_resp.json.return_value = {"error": {"status": 403, "message": "Forbidden"}}

    # Second call (fallback): Embed page returns HTML with __NEXT_DATA__
    embed_payload = {
        "props": {
            "pageProps": {
                "state": {
                    "data": {
                        "entity": {
                            "trackList": [
                                {
                                    "uri": "spotify:track:abc123",
                                    "title": "Shared Masterpiece",
                                    "subtitle": "Friend &amp; Artist",
                                    "duration": 215000,
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    mock_embed_resp = MagicMock()
    mock_embed_resp.status_code = 200
    mock_embed_resp.text = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(embed_payload)}</script></html>'

    def mock_get_side_effect(url, *args, **kwargs):
        if "api.spotify.com" in url:
            return mock_api_resp
        return mock_embed_resp

    with patch("requests.get", side_effect=mock_get_side_effect):
        tracks = client.get_playlist_tracks("shared_playlist_id")
        assert len(tracks) == 1
        assert tracks[0]["id"] == "abc123"
        assert tracks[0]["name"] == "Shared Masterpiece"
        assert tracks[0]["artist"] == "Friend & Artist"
        assert tracks[0]["duration_str"] == "03:35"
        assert tracks[0]["uri"] == "spotify:track:abc123"

        # Subsequent call should use cache
        cached_tracks = client.get_playlist_tracks("shared_playlist_id")
        assert cached_tracks == tracks


def test_play_with_offset(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch("requests.put", return_value=mock_resp) as mock_put:
        success, err = client.play(
            context_uri="spotify:playlist:shared1",
            offset={"uri": "spotify:track:t1"},
            device_id="dev1",
        )
        assert success is True
        assert err == ""
        mock_put.assert_called_once()
        _, kwargs = mock_put.call_args
        assert kwargs["json"] == {
            "context_uri": "spotify:playlist:shared1",
            "offset": {"uri": "spotify:track:t1"},
        }


def test_play_recovers_via_transfer_on_404(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.access_token = "valid_token"
    cfg.token_expiry = 9999999999
    client = SpotifyClient(cfg)

    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.json.return_value = {"error": {"status": 404, "message": "Player command failed: No active device found"}}

    with patch("requests.put", return_value=resp_404), \
         patch.object(client, "transfer_playback", return_value=True) as mock_transfer:
        success, err = client.play(device_id="dev1")
        assert success is True
        assert err == ""
        mock_transfer.assert_called_with("dev1", play=True)


def test_ssl_error_self_healing(tmp_path):
    import requests
    cfg = BardConfig(config_path=tmp_path / "config.json")
    cfg.client_id = "test_client"
    client = SpotifyClient(cfg)

    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {
        "access_token": "recovered_token",
        "refresh_token": "recovered_refresh",
        "expires_in": 3600,
    }

    call_count = 0

    def mock_post_ssl_flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if "verify" not in kwargs:
            raise requests.exceptions.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        return mock_success

    with patch("requests.post", side_effect=mock_post_ssl_flaky):
        success = client.exchange_code_for_token("auth_code", "verifier")
        assert success is True
        assert call_count >= 2
        assert cfg.access_token == "recovered_token"



