"""Unit tests for YTMusicClient."""

from unittest.mock import MagicMock, patch
import pytest

from bard.models import Track
from bard.ytmusic_client import YTMusicClient


def test_search_normalizes_tracks():
    mock_raw_results = [
        {
            "resultType": "song",
            "videoId": "abc1234",
            "title": "Harder, Better, Faster, Stronger",
            "artists": [{"name": "Daft Punk"}],
            "album": {"name": "Discovery"},
            "duration_seconds": 224,
            "thumbnails": [{"url": "https://img.jpg", "width": 120, "height": 120}],
        }
    ]
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.search.return_value = mock_raw_results
        client = YTMusicClient()
        tracks = client.search("Daft Punk")
        assert len(tracks) == 1
        assert tracks[0].id == "abc1234"
        assert tracks[0].title == "Harder, Better, Faster, Stronger"
        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].album == "Discovery"
        assert tracks[0].duration_seconds == 224
        assert tracks[0].thumbnail_url == "https://img.jpg"


def test_search_handles_missing_keys_and_edge_cases():
    mock_raw_results = [
        # Track with minimal keys and duration as string
        {
            "videoId": "xyz789",
            "title": "Minimal Song",
            "duration": "3:30",
        },
        # Track with empty / None fields
        {
            "videoId": "none_fields",
            "title": None,
            "artists": None,
            "album": None,
            "duration_seconds": None,
            "thumbnails": [],
        },
        # Invalid item without videoId should be skipped
        {
            "resultType": "artist",
            "artist": "Only Artist",
        },
    ]
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.search.return_value = mock_raw_results
        client = YTMusicClient()
        tracks = client.search("test")

        assert len(tracks) == 2
        assert tracks[0].id == "xyz789"
        assert tracks[0].duration_seconds == 210
        assert tracks[0].artist == "Unknown Artist"
        assert tracks[0].album == ""

        assert tracks[1].id == "none_fields"
        assert tracks[1].title == "Unknown Title"
        assert tracks[1].artist == "Unknown Artist"
        assert tracks[1].album == ""
        assert tracks[1].duration_seconds == 0
        assert tracks[1].thumbnail_url == ""


def test_search_handles_exception_gracefully():
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.search.side_effect = RuntimeError("API Network Error")
        client = YTMusicClient()
        tracks = client.search("fail")
        assert tracks == []


def test_get_playlist_tracks():
    mock_playlist_payload = {
        "title": "Synthwave Favorites",
        "tracks": [
            {
                "videoId": "synth01",
                "title": "Resonance",
                "artists": [{"name": "HOME"}],
                "album": {"name": "Odyssey"},
                "duration_seconds": 212,
                "thumbnails": [{"url": "https://home.jpg"}],
            }
        ],
    }
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.get_playlist.return_value = mock_playlist_payload
        client = YTMusicClient()
        tracks = client.get_playlist_tracks("PL123")
        assert len(tracks) == 1
        assert tracks[0].id == "synth01"
        assert tracks[0].title == "Resonance"
        assert tracks[0].artist == "HOME"
        assert tracks[0].album == "Odyssey"


def test_get_playlist_tracks_handles_exception():
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.get_playlist.side_effect = Exception("404 Not Found")
        client = YTMusicClient()
        tracks = client.get_playlist_tracks("invalid_pl")
        assert tracks == []


def test_get_trending_from_direct_videos():
    mock_charts = {
        "videos": [
            {
                "videoId": "hit1",
                "title": "Hot Hit",
                "artists": [{"name": "Pop Star"}],
                "album": {"name": "Summer 2026"},
                "duration_seconds": 180,
                "thumbnails": [{"url": "https://hit1.jpg"}],
            }
        ]
    }
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.get_charts.return_value = mock_charts
        client = YTMusicClient()
        tracks = client.get_trending("US")
        assert len(tracks) == 1
        assert tracks[0].id == "hit1"
        assert tracks[0].title == "Hot Hit"


def test_get_trending_from_playlist_link():
    mock_charts = {
        "videos": [
            {
                "title": "Trending 20 United States",
                "playlistId": "PL_TREND_US",
            }
        ]
    }
    mock_playlist_payload = {
        "tracks": [
            {
                "videoId": "trend_song_1",
                "title": "Trending Song",
                "artists": [{"name": "Artist"}],
                "album": None,
                "duration_seconds": 200,
                "thumbnails": [],
            }
        ]
    }
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.get_charts.return_value = mock_charts
        mock_instance.get_playlist.return_value = mock_playlist_payload
        client = YTMusicClient()
        tracks = client.get_trending("US")
        assert len(tracks) == 1
        assert tracks[0].id == "trend_song_1"
        assert tracks[0].title == "Trending Song"


def test_get_trending_fallback_to_search():
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.get_charts.side_effect = Exception("Charts unavailable")
        mock_instance.search.return_value = [
            {
                "videoId": "search_trend_1",
                "title": "Fallback Trend",
                "artists": [{"name": "Fallback Artist"}],
                "duration_seconds": 150,
            }
        ]
        client = YTMusicClient()
        tracks = client.get_trending("US")
        assert len(tracks) == 1
        assert tracks[0].id == "search_trend_1"
        assert tracks[0].title == "Fallback Trend"


def test_get_stream_url_success():
    with patch("bard.ytmusic_client.yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            "url": "https://manifest.googlevideo.com/audio_stream_123"
        }
        MockYDL.return_value.__enter__.return_value = mock_ydl_instance

        client = YTMusicClient()
        url = client.get_stream_url("abc1234")
        assert url == "https://manifest.googlevideo.com/audio_stream_123"


def test_get_stream_url_failure_returns_none():
    with patch("bard.ytmusic_client.yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = Exception("Video unavailable")
        MockYDL.return_value.__enter__.return_value = mock_ydl_instance

        client = YTMusicClient()
        url = client.get_stream_url("unavailable_id")
        assert url is None


def test_get_stream_url_empty_id():
    client = YTMusicClient()
    assert client.get_stream_url("") is None
    assert client.get_stream_url(None) is None


def test_init_with_auth_header():
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        client = YTMusicClient(auth_header="custom_auth_token")
        MockYTMusic.assert_called_with(auth="custom_auth_token")
