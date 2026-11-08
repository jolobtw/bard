"""YouTube Music client for catalog search, playlists, and stream URL extraction."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import yt_dlp
from ytmusicapi import YTMusic

from bard.models import Track

logger = logging.getLogger(__name__)


def _parse_duration(val: Any) -> int:
    """Parse duration into seconds from int, float, or colon-delimited string (e.g. '3:45')."""
    if isinstance(val, (int, float)):
        return max(0, int(val))
    if isinstance(val, str):
        try:
            parts = [int(p) for p in val.strip().split(":")]
            if len(parts) == 1:
                return max(0, parts[0])
            elif len(parts) == 2:
                return max(0, parts[0] * 60 + parts[1])
            elif len(parts) == 3:
                return max(0, parts[0] * 3600 + parts[1] * 60 + parts[2])
        except Exception:
            return 0
    return 0


def _parse_artist(item: Dict[str, Any]) -> str:
    """Extract display artist string from raw track dict."""
    artists = item.get("artists")
    if artists:
        if isinstance(artists, list):
            names = [
                str(a.get("name", "")) if isinstance(a, dict) else str(a)
                for a in artists
                if (isinstance(a, dict) and a.get("name")) or (isinstance(a, str) and a)
            ]
            if names:
                return ", ".join(names)
        elif isinstance(artists, str) and artists.strip():
            return artists.strip()

    artist = item.get("artist")
    if artist:
        if isinstance(artist, str) and artist.strip():
            return artist.strip()
        elif isinstance(artist, dict) and artist.get("name"):
            return str(artist["name"]).strip()

    author = item.get("author")
    if author:
        if isinstance(author, str) and author.strip():
            return author.strip()
        elif isinstance(author, list):
            names = [str(a.get("name", a)) for a in author if a]
            if names:
                return ", ".join(names)

    return "Unknown Artist"


def _parse_album(item: Dict[str, Any]) -> str:
    """Extract album name string from raw track dict."""
    album = item.get("album")
    if album:
        if isinstance(album, dict):
            return str(album.get("name") or "").strip()
        elif isinstance(album, str):
            return album.strip()
    return ""


def _parse_thumbnail(item: Dict[str, Any]) -> str:
    """Extract thumbnail URL from raw track dict."""
    if "thumbnail_url" in item and isinstance(item["thumbnail_url"], str):
        return item["thumbnail_url"]

    thumbs = item.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1]
        if isinstance(last, dict) and "url" in last:
            return str(last["url"])
        elif isinstance(last, str):
            return last
    elif isinstance(thumbs, str):
        return thumbs
    return ""


class YTMusicClient:
    """Client for YouTube Music catalog search and audio stream extraction."""

    def __init__(self, auth_header: Optional[str] = None):
        self.auth_header = auth_header
        try:
            self.ytmusic = YTMusic(auth=auth_header)
        except Exception as exc:
            logger.warning(
                "Failed to initialize YTMusic with auth_header: %s; falling back to unauthenticated",
                exc,
            )
            self.ytmusic = YTMusic()

    def _normalize_track(self, item: Dict[str, Any]) -> Optional[Track]:
        """Convert a raw dictionary result from ytmusicapi to a Track model."""
        if not isinstance(item, dict):
            return None

        video_id = item.get("videoId") or item.get("id")
        if not video_id or not isinstance(video_id, str):
            return None

        title = item.get("title")
        if not title:
            title = "Unknown Title"
        elif not isinstance(title, str):
            title = str(title)

        artist = _parse_artist(item)
        album = _parse_album(item)

        duration_sec = item.get("duration_seconds")
        if duration_sec is None or not isinstance(duration_sec, (int, float)):
            duration_sec = _parse_duration(item.get("duration") or duration_sec)
        else:
            duration_sec = max(0, int(duration_sec))

        thumbnail_url = _parse_thumbnail(item)

        return Track(
            id=video_id,
            title=title,
            artist=artist,
            album=album,
            duration_seconds=duration_sec,
            thumbnail_url=thumbnail_url,
        )

    def search(self, query: str, limit: int = 25) -> List[Track]:
        """Search YouTube Music for tracks matching query."""
        if not query or not query.strip():
            return []

        try:
            # First attempt search with songs filter
            raw_results = self.ytmusic.search(query.strip(), filter="songs", limit=limit)
        except Exception as exc:
            logger.debug("ytmusic search with filter='songs' failed: %s; trying unfiltered", exc)
            try:
                raw_results = self.ytmusic.search(query.strip(), limit=limit)
            except Exception as e:
                logger.error("ytmusic search failed: %s", e)
                return []

        if not isinstance(raw_results, list):
            return []

        tracks: List[Track] = []
        for item in raw_results:
            track = self._normalize_track(item)
            if track is not None:
                tracks.append(track)
            if len(tracks) >= limit:
                break

        return tracks

    def get_playlist_tracks(self, playlist_id: str) -> List[Track]:
        """Retrieve tracks from a YouTube Music playlist."""
        if not playlist_id:
            return []

        try:
            playlist_data = self.ytmusic.get_playlist(playlist_id)
        except Exception as exc:
            logger.error("Failed to fetch playlist %s: %s", playlist_id, exc)
            return []

        if not isinstance(playlist_data, dict):
            return []

        raw_tracks = playlist_data.get("tracks", [])
        if not isinstance(raw_tracks, list):
            return []

        tracks: List[Track] = []
        for item in raw_tracks:
            track = self._normalize_track(item)
            if track is not None:
                tracks.append(track)

        return tracks

    def get_trending(self, country: str = "US") -> List[Track]:
        """Fetch trending tracks/charts for a given country."""
        try:
            charts = self.ytmusic.get_charts(country=country)
            if isinstance(charts, dict):
                videos_data = charts.get("videos", [])
                if isinstance(videos_data, dict):
                    videos_data = videos_data.get("items", [])

                if isinstance(videos_data, list):
                    # Check if videos contains tracks directly (has videoId)
                    direct_tracks = [
                        self._normalize_track(item)
                        for item in videos_data
                        if isinstance(item, dict) and "videoId" in item
                    ]
                    valid_direct = [t for t in direct_tracks if t is not None]
                    if valid_direct:
                        return valid_direct

                    # Check if videos has chart playlists (has playlistId)
                    playlist_id = None
                    for item in videos_data:
                        if isinstance(item, dict) and "playlistId" in item:
                            if "trending" in item.get("title", "").lower():
                                playlist_id = item["playlistId"]
                                break
                    if (
                        not playlist_id
                        and videos_data
                        and isinstance(videos_data[0], dict)
                        and "playlistId" in videos_data[0]
                    ):
                        playlist_id = videos_data[0]["playlistId"]

                    if playlist_id:
                        tracks = self.get_playlist_tracks(playlist_id)
                        if tracks:
                            return tracks

                # Also check "tracks" section if present in charts
                raw_tracks = charts.get("tracks", [])
                if isinstance(raw_tracks, list):
                    tracks = [
                        self._normalize_track(item)
                        for item in raw_tracks
                        if isinstance(item, dict) and "videoId" in item
                    ]
                    valid_tracks = [t for t in tracks if t is not None]
                    if valid_tracks:
                        return valid_tracks
        except Exception as exc:
            logger.debug("get_charts failed: %s; falling back to search", exc)

        # Fallback to search query
        return self.search("Trending", limit=25)

    def get_stream_url(self, video_id: str) -> Optional[str]:
        """Resolve a direct audio stream URL for a YouTube video using yt-dlp."""
        if not video_id or not isinstance(video_id, str):
            return None

        url = video_id if video_id.startswith("http") else f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info or not isinstance(info, dict):
                    return None

                if "url" in info and info["url"]:
                    return str(info["url"])

                formats = info.get("formats")
                if isinstance(formats, list):
                    for fmt in reversed(formats):
                        if isinstance(fmt, dict) and fmt.get("url"):
                            return str(fmt["url"])

                return None
        except Exception as exc:
            logger.error("Failed to extract stream URL for %s: %s", video_id, exc)
            return None
