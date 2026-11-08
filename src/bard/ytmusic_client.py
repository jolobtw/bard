"""YouTube Music client for catalog search, playlists, and stream URL extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yt_dlp
from ytmusicapi import OAuthCredentials, YTMusic

from bard.models import Track
from bard.oauth import YTMusicOAuth

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
    """Client for YouTube Music catalog search, personal library, and audio stream extraction."""

    def __init__(
        self,
        auth_header: Optional[str] = None,
        oauth: Optional[YTMusicOAuth] = None,
        token_path: Optional[Union[Path, str]] = None,
    ):
        self.auth_header = auth_header
        self._oauth = oauth
        self._authenticated = False

        if auth_header:
            try:
                self._ytm = YTMusic(auth=auth_header)
                self._authenticated = True
            except Exception as exc:
                logger.warning(
                    "Failed to initialize YTMusic with auth_header: %s; falling back to unauthenticated",
                    exc,
                )
                self._ytm = YTMusic()
                self._authenticated = False
        else:
            if self._oauth is None:
                self._oauth = YTMusicOAuth(token_path=Path(token_path) if token_path else None)

            if self._oauth.is_authenticated():
                try:
                    oauth_creds = OAuthCredentials(
                        client_id=str(self._oauth.client_id),
                        client_secret=str(self._oauth.client_secret),
                    )
                    self._ytm = YTMusic(
                        auth=str(self._oauth.token_path),
                        oauth_credentials=oauth_creds,
                    )
                    self._authenticated = True
                except Exception as exc:
                    logger.warning(
                        "Failed to initialize YTMusic with OAuth credentials: %s; falling back to unauthenticated",
                        exc,
                    )
                    self._ytm = YTMusic()
                    self._authenticated = False
            else:
                self._ytm = YTMusic()
                self._authenticated = False

    @property
    def ytmusic(self) -> YTMusic:
        """Alias for underlying YTMusic client instance."""
        return self._ytm

    @ytmusic.setter
    def ytmusic(self, val: YTMusic) -> None:
        self._ytm = val

    def is_authenticated(self) -> bool:
        """Check whether the client is authenticated with YouTube Music."""
        return self._authenticated

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
            raw_results = self._ytm.search(query.strip(), filter="songs", limit=limit)
        except Exception as exc:
            logger.debug("ytmusic search with filter='songs' failed: %s; trying unfiltered", exc)
            try:
                raw_results = self._ytm.search(query.strip(), limit=limit)
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
            playlist_data = self._ytm.get_playlist(playlist_id)
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
            charts = self._ytm.get_charts(country=country)
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

    def get_liked_songs(self, limit: int = 50) -> List[Track]:
        """Retrieve user's liked songs from YouTube Music."""
        try:
            raw_data = self._ytm.get_liked_songs(limit=limit)
        except Exception as exc:
            logger.debug("Failed to fetch liked songs: %s", exc)
            return []

        if isinstance(raw_data, dict):
            raw_tracks = raw_data.get("tracks", [])
        elif isinstance(raw_data, list):
            raw_tracks = raw_data
        else:
            return []

        if not isinstance(raw_tracks, list):
            return []

        tracks: List[Track] = []
        for item in raw_tracks:
            if not isinstance(item, dict):
                continue
            track = self._normalize_track(item)
            if track is not None:
                tracks.append(track)
                if len(tracks) >= limit:
                    break
        return tracks

    def get_library_playlists(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve playlists from the user's library."""
        try:
            raw_playlists = self._ytm.get_library_playlists(limit=limit)
        except Exception as exc:
            logger.debug("Failed to fetch library playlists: %s", exc)
            return []

        if not isinstance(raw_playlists, list):
            return []

        playlists: List[Dict[str, Any]] = []
        for p in raw_playlists:
            if not isinstance(p, dict):
                continue
            playlist_id = p.get("playlistId") or p.get("id") or ""
            title = p.get("title") or "Untitled Playlist"
            count = p.get("count") or p.get("trackCount") or p.get("itemCount") or ""
            thumb = _parse_thumbnail(p)
            playlists.append({
                "id": playlist_id,
                "title": title,
                "count": str(count) if count != "" else "",
                "thumbnail_url": thumb,
            })
            if len(playlists) >= limit:
                break
        return playlists

    def get_history(self) -> List[Track]:
        """Retrieve playback history from YouTube Music."""
        try:
            raw_items = self._ytm.get_history()
        except Exception as exc:
            logger.debug("Failed to fetch history: %s", exc)
            return []

        if not isinstance(raw_items, list):
            return []

        tracks: List[Track] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            track = self._normalize_track(item)
            if track is not None:
                tracks.append(track)
        return tracks

    def get_album_tracks(self, browse_id: str) -> List[Track]:
        """Retrieve tracks for a given album browse ID."""
        if not browse_id or not browse_id.strip():
            return []

        try:
            album_data = self._ytm.get_album(browse_id.strip())
        except Exception as exc:
            logger.debug("Failed to fetch album tracks for %s: %s", browse_id, exc)
            return []

        if not isinstance(album_data, dict):
            return []

        raw_tracks = album_data.get("tracks", [])
        if not isinstance(raw_tracks, list):
            return []

        album_thumb = _parse_thumbnail(album_data)
        album_title = album_data.get("title") or ""
        album_artists = album_data.get("artists")

        tracks: List[Track] = []
        for item in raw_tracks:
            if not isinstance(item, dict):
                continue
            item_copy = dict(item)
            if not item_copy.get("thumbnails") and album_thumb:
                item_copy["thumbnail_url"] = album_thumb
            if not item_copy.get("album") and album_title:
                item_copy["album"] = album_title
            if not item_copy.get("artists") and album_artists:
                item_copy["artists"] = album_artists

            track = self._normalize_track(item_copy)
            if track is not None:
                tracks.append(track)

        return tracks

    def get_artist_top_tracks(self, channel_id: str) -> List[Track]:
        """Retrieve top tracks for an artist channel ID."""
        if not channel_id or not channel_id.strip():
            return []

        try:
            artist_data = self._ytm.get_artist(channel_id.strip())
        except Exception as exc:
            logger.debug("Failed to fetch artist top tracks for %s: %s", channel_id, exc)
            return []

        if not isinstance(artist_data, dict):
            return []

        songs_section = artist_data.get("songs")
        raw_tracks = []
        if isinstance(songs_section, dict):
            raw_tracks = songs_section.get("results", [])
        elif isinstance(songs_section, list):
            raw_tracks = songs_section

        if not isinstance(raw_tracks, list):
            return []

        artist_thumb = _parse_thumbnail(artist_data)
        artist_name = artist_data.get("name")

        tracks: List[Track] = []
        for item in raw_tracks:
            if not isinstance(item, dict):
                continue
            item_copy = dict(item)
            if not item_copy.get("thumbnails") and artist_thumb:
                item_copy["thumbnail_url"] = artist_thumb
            if not item_copy.get("artists") and not item_copy.get("artist") and artist_name:
                item_copy["artist"] = artist_name

            track = self._normalize_track(item_copy)
            if track is not None:
                tracks.append(track)

        return tracks

    def search_all(self, query: str, limit: int = 25) -> Dict[str, Any]:
        """Search YouTube Music across songs, albums, and artists."""
        empty_result: Dict[str, Any] = {"songs": [], "albums": [], "artists": []}
        if not query or not query.strip():
            return empty_result

        try:
            raw_results = self._ytm.search(query.strip(), limit=limit)
        except Exception as exc:
            logger.debug("search_all failed for query '%s': %s", query, exc)
            return empty_result

        if not isinstance(raw_results, list):
            return empty_result

        songs: List[Track] = []
        albums: List[Dict[str, Any]] = []
        artists: List[Dict[str, Any]] = []

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            result_type = str(item.get("resultType") or "").lower()

            if result_type in ("song", "video"):
                track = self._normalize_track(item)
                if track is not None:
                    songs.append(track)
            elif result_type == "album":
                album_id = item.get("browseId") or item.get("playlistId") or ""
                albums.append({
                    "id": album_id,
                    "browse_id": item.get("browseId") or "",
                    "browseId": item.get("browseId") or "",
                    "playlist_id": item.get("playlistId") or "",
                    "playlistId": item.get("playlistId") or "",
                    "title": item.get("title") or "Unknown Album",
                    "artist": _parse_artist(item),
                    "year": str(item.get("year") or ""),
                    "thumbnail_url": _parse_thumbnail(item),
                })
            elif result_type == "artist":
                artist_id = item.get("browseId") or item.get("channelId") or ""
                artists.append({
                    "id": artist_id,
                    "browse_id": item.get("browseId") or "",
                    "browseId": item.get("browseId") or "",
                    "name": item.get("artist") or item.get("name") or "Unknown Artist",
                    "thumbnail_url": _parse_thumbnail(item),
                })
            else:
                if "videoId" in item:
                    track = self._normalize_track(item)
                    if track is not None:
                        songs.append(track)
                elif item.get("type") == "Album" or ("browseId" in item and "artists" in item and "year" in item):
                    album_id = item.get("browseId") or item.get("playlistId") or ""
                    albums.append({
                        "id": album_id,
                        "browse_id": item.get("browseId") or "",
                        "browseId": item.get("browseId") or "",
                        "playlist_id": item.get("playlistId") or "",
                        "playlistId": item.get("playlistId") or "",
                        "title": item.get("title") or "Unknown Album",
                        "artist": _parse_artist(item),
                        "year": str(item.get("year") or ""),
                        "thumbnail_url": _parse_thumbnail(item),
                    })

        return {
            "songs": songs,
            "albums": albums,
            "artists": artists,
        }
