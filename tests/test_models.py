"""Tests for core data models."""

from bard.models import Track


def test_track_instantiation_and_dict():
    track = Track(
        id="video123",
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        duration_seconds=248,
        thumbnail_url="https://example.com/thumb.jpg",
    )
    assert track.id == "video123"
    assert track.title == "Get Lucky"
    assert track.artist == "Daft Punk"
    assert track.album == "Random Access Memories"
    assert track.duration_seconds == 248
    assert track.thumbnail_url == "https://example.com/thumb.jpg"
    assert track.stream_url is None
    assert track.duration_ms == 248000

    d = track.to_dict()
    assert d["id"] == "video123"
    assert d["title"] == "Get Lucky"
    assert d["artist"] == "Daft Punk"
    assert d["album"] == "Random Access Memories"
    assert d["duration_seconds"] == 248
    assert d["duration_ms"] == 248000
    assert d["thumbnail_url"] == "https://example.com/thumb.jpg"
    assert d["album_art_url"] == "https://example.com/thumb.jpg"
    assert d["stream_url"] is None


def test_track_with_stream_url():
    track = Track(
        id="video456",
        title="One More Time",
        artist="Daft Punk",
        album="Discovery",
        duration_seconds=320,
        thumbnail_url="https://example.com/discovery.jpg",
        stream_url="https://googlevideo.com/videoplayback?id=video456",
    )
    assert track.stream_url == "https://googlevideo.com/videoplayback?id=video456"
    d = track.to_dict()
    assert d["stream_url"] == "https://googlevideo.com/videoplayback?id=video456"
