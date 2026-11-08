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


def test_client_get_liked_songs():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_liked_songs.return_value = {
            "tracks": [
                {
                    "videoId": "v1",
                    "title": "Liked Track 1",
                    "artists": [{"name": "Artist 1"}],
                    "duration_seconds": 180,
                    "thumbnails": [],
                }
            ]
        }
        tracks = client.get_liked_songs()
        assert len(tracks) == 1
        assert tracks[0].title == "Liked Track 1"
        assert tracks[0].id == "v1"


def test_client_get_liked_songs_error_or_unauthenticated():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_liked_songs.side_effect = Exception("Auth required")
        tracks = client.get_liked_songs()
        assert tracks == []


def test_client_get_library_playlists():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_library_playlists.return_value = [
            {
                "playlistId": "PL123",
                "title": "Synth Favorites",
                "count": "24",
                "thumbnails": [{"url": "https://img.jpg/thumb.jpg"}],
            }
        ]
        playlists = client.get_library_playlists()
        assert len(playlists) == 1
        assert playlists[0]["id"] == "PL123"
        assert playlists[0]["title"] == "Synth Favorites"
        assert playlists[0]["count"] == "24"
        assert playlists[0]["thumbnail_url"] == "https://img.jpg/thumb.jpg"


def test_client_get_library_playlists_error():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_library_playlists.side_effect = RuntimeError("Network error")
        assert client.get_library_playlists() == []


def test_client_get_history():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_history.return_value = [
            {
                "videoId": "hist1",
                "title": "Past Track",
                "artists": [{"name": "Artist Past"}],
                "duration_seconds": 210,
                "thumbnails": [],
            }
        ]
        history = client.get_history()
        assert len(history) == 1
        assert history[0].id == "hist1"
        assert history[0].title == "Past Track"


def test_client_get_history_error():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_history.side_effect = Exception("User not signed in")
        assert client.get_history() == []


def test_client_get_album_tracks():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_album.return_value = {
            "title": "Discovery",
            "thumbnails": [{"url": "https://img.jpg/discovery.jpg"}],
            "artists": [{"name": "Daft Punk"}],
            "tracks": [
                {
                    "videoId": "d1",
                    "title": "One More Time",
                    "artists": [{"name": "Daft Punk"}],
                    "duration_seconds": 320,
                    "thumbnails": None,
                },
                {
                    "videoId": "d2",
                    "title": "Aerodynamic",
                    "duration_seconds": 207,
                    "thumbnails": None,
                },
            ],
        }
        tracks = client.get_album_tracks("MPREb_123")
        assert len(tracks) == 2
        assert tracks[0].id == "d1"
        assert tracks[0].title == "One More Time"
        assert tracks[0].album == "Discovery"
        assert tracks[0].thumbnail_url == "https://img.jpg/discovery.jpg"
        assert tracks[1].artist == "Daft Punk"


def test_client_get_album_tracks_empty_or_error():
    client = YTMusicClient()
    assert client.get_album_tracks("") == []
    assert client.get_album_tracks("   ") == []

    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_album.side_effect = Exception("Album not found")
        assert client.get_album_tracks("invalid_album") == []


def test_client_get_artist_top_tracks():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_artist.return_value = {
            "name": "Daft Punk",
            "thumbnails": [{"url": "https://img.jpg/artist.jpg"}],
            "songs": {
                "results": [
                    {
                        "videoId": "top1",
                        "title": "Get Lucky",
                        "duration_seconds": 248,
                    }
                ]
            },
        }
        tracks = client.get_artist_top_tracks("UC_channel123")
        assert len(tracks) == 1
        assert tracks[0].id == "top1"
        assert tracks[0].title == "Get Lucky"
        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].thumbnail_url == "https://img.jpg/artist.jpg"


def test_client_search_all():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.search.return_value = [
            {
                "resultType": "song",
                "videoId": "s1",
                "title": "Song One",
                "artists": [{"name": "Artist One"}],
                "duration_seconds": 180,
                "thumbnails": [{"url": "https://img.jpg/s1.jpg"}],
            },
            {
                "resultType": "album",
                "browseId": "alb1",
                "playlistId": "OLAK_alb1",
                "title": "Greatest Hits",
                "artists": [{"name": "Artist One"}],
                "year": "2024",
                "thumbnails": [{"url": "https://img.jpg/alb1.jpg"}],
            },
            {
                "resultType": "artist",
                "browseId": "art1",
                "artist": "Artist One",
                "thumbnails": [{"url": "https://img.jpg/art1.jpg"}],
            },
        ]
        res = client.search_all("Artist One")
        assert "songs" in res
        assert "albums" in res
        assert "artists" in res

        assert len(res["songs"]) == 1
        assert res["songs"][0].id == "s1"
        assert res["songs"][0].title == "Song One"

        assert len(res["albums"]) == 1
        assert res["albums"][0]["browse_id"] == "alb1"
        assert res["albums"][0]["title"] == "Greatest Hits"
        assert res["albums"][0]["artist"] == "Artist One"
        assert res["albums"][0]["year"] == "2024"

        assert len(res["artists"]) == 1
        assert res["artists"][0]["browse_id"] == "art1"
        assert res["artists"][0]["name"] == "Artist One"


def test_client_search_all_empty_or_error():
    client = YTMusicClient()
    assert client.search_all("") == {"songs": [], "albums": [], "artists": []}
    assert client.search_all("   ") == {"songs": [], "albums": [], "artists": []}

    with patch.object(client, "_ytm") as mock_ytm, \
         patch.object(client, "_anon") as mock_anon:
        mock_ytm.search.side_effect = Exception("API rate limited")
        mock_anon.search.side_effect = Exception("API rate limited")
        assert client.search_all("fail") == {"songs": [], "albums": [], "artists": []}


def test_client_is_authenticated(tmp_path):
    empty_token = tmp_path / "empty_oauth.json"
    client_anon = YTMusicClient(token_path=empty_token)
    assert client_anon.is_authenticated() is False

    with patch("bard.ytmusic_client.YTMusic"), \
         patch("bard.ytmusic_client.OAuthCredentials"):
        mock_oauth = MagicMock()
        mock_oauth.is_authenticated.return_value = True
        client_auth = YTMusicClient(oauth=mock_oauth)
        assert client_auth.is_authenticated() is True


def test_client_init_with_oauth_loads_credentials(tmp_path):
    token_file = tmp_path / "oauth.json"
    import json
    token_file.write_text(
        json.dumps({
            "access_token": "mock_token",
            "refresh_token": "mock_refresh",
            "token_type": "Bearer",
            "expires_at": 9999999999,
        })
    )

    from bard.oauth import YTMusicOAuth
    oauth = YTMusicOAuth(token_path=token_file)

    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic, \
         patch("bard.ytmusic_client.OAuthCredentials") as MockOAuthCreds:
        client = YTMusicClient(oauth=oauth)
        MockOAuthCreds.assert_called_once_with(
            client_id=oauth.client_id,
            client_secret=oauth.client_secret,
        )
        MockYTMusic.assert_called_once_with(
            auth=str(token_file),
            oauth_credentials=MockOAuthCreds.return_value,
        )
        assert client.is_authenticated() is True


def test_client_init_oauth_failure_falls_back_to_anonymous(tmp_path):
    token_file = tmp_path / "oauth.json"
    import json
    token_file.write_text(
        json.dumps({
            "access_token": "mock_token",
            "refresh_token": "mock_refresh",
            "token_type": "Bearer",
            "expires_at": 9999999999,
        })
    )

    from bard.oauth import YTMusicOAuth
    oauth = YTMusicOAuth(token_path=token_file)

    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        # First call with auth fails, second call (fallback) succeeds
        MockYTMusic.side_effect = [RuntimeError("Invalid oauth payload"), MagicMock()]
        client = YTMusicClient(oauth=oauth)
        assert MockYTMusic.call_count == 2
        assert client.is_authenticated() is False
