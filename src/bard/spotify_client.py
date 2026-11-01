"""Spotify Web API REST & OAuth 2.0 PKCE client."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Any, Dict, List, Optional, Tuple
import requests

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass

from bard.config import BardConfig

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
]


def generate_pkce_pair() -> Tuple[str, str]:
    """Generate high-entropy code_verifier and code_challenge for OAuth PKCE."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class SpotifyClient:
    """Handles Spotify API calls, token management, caching, and rate limit protection."""

    def __init__(self, config: BardConfig):
        self.config = config
        self._playlists_cache: Optional[List[Dict[str, Any]]] = None
        self._tracks_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._last_playback_data: Optional[Dict[str, Any]] = None
        self.rate_limited_until: float = 0.0
        self.rate_limit_reason: str = ""

    def is_rate_limited(self) -> bool:
        """Check if client is currently in rate-limit cooldown."""
        import time
        return time.time() < self.rate_limited_until

    def is_quota_exceeded(self) -> bool:
        """Check if rate limit is specifically due to 24-hour developer app QUOTA_EXCEEDED."""
        return self.is_rate_limited() and self.rate_limit_reason == "QUOTA_EXCEEDED"

    def get_cooldown_seconds(self) -> int:
        """Return remaining rate-limit cooldown seconds."""
        import time
        return max(0, int(self.rate_limited_until - time.time()))

    def get_cooldown_message(self) -> str:
        """Return human-friendly rate-limit or quota status message."""
        secs = self.get_cooldown_seconds()
        if secs <= 0:
            return ""
        hours, rem = divmod(secs, 3600)
        mins, s = divmod(rem, 60)
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m {s}s"
        if self.is_quota_exceeded():
            return f"Spotify daily developer quota exceeded (QUOTA_EXCEEDED). Cooldown resets in {time_str}."
        return f"Too many requests to Spotify (rate limited). Cooldown: {time_str}."

    def _safe_request(self, func, *args, **kwargs) -> requests.Response:
        """Execute HTTP request with automatic SSL certificate self-healing.
        
        Fixes macOS/Python SSL: CERTIFICATE_VERIFY_FAILED error by attempting:
        1. Standard request
        2. Explicit certifi CA bundle
        3. Fallback without SSL verification as a last resort if OS certificates are missing
        """
        try:
            return func(*args, **kwargs)
        except requests.exceptions.SSLError:
            try:
                import certifi
                kwargs["verify"] = certifi.where()
                return func(*args, **kwargs)
            except Exception:
                pass
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            kwargs["verify"] = False
            return func(*args, **kwargs)

    def _handle_response(self, resp: requests.Response) -> None:
        """Process response status and update rate limit flags on 429."""
        if resp.status_code == 429:
            import time
            retry_after = int(resp.headers.get("Retry-After", 60))
            self.rate_limited_until = time.time() + retry_after
            try:
                err = resp.json().get("error", {})
                self.rate_limit_reason = err.get("reason", "RATE_LIMIT")
            except Exception:
                self.rate_limit_reason = "RATE_LIMIT"

    def get_auth_url(self, challenge: str, state: str) -> str:
        """Construct OAuth authorization URL."""
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
            "scope": " ".join(SCOPES),
        }
        return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, code: str, verifier: str) -> bool:
        """Exchange authorization code for access & refresh tokens."""
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "code_verifier": verifier,
        }
        resp = self._safe_request(requests.post, SPOTIFY_TOKEN_URL, data=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            self.config.set_tokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", ""),
                expires_in=data.get("expires_in", 3600),
            )
            self.config.save()
            return True
        return False

    def refresh_access_token(self) -> bool:
        """Refresh expired access token using refresh_token."""
        if not self.config.refresh_token:
            return False
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.config.refresh_token,
            "client_id": self.config.client_id,
        }
        resp = self._safe_request(requests.post, SPOTIFY_TOKEN_URL, data=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            self.config.set_tokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", self.config.refresh_token),
                expires_in=data.get("expires_in", 3600),
            )
            self.config.save()
            return True
        return False

    def _headers(self) -> Dict[str, str]:
        """Return authorization headers, auto-refreshing if expired."""
        if self.config.is_token_expired():
            self.refresh_access_token()
        return {"Authorization": f"Bearer {self.config.access_token}"}

    def get_devices(self) -> List[Dict[str, Any]]:
        """Return available Spotify Connect devices."""
        if self.is_rate_limited():
            return []
        try:
            resp = self._safe_request(requests.get, f"{SPOTIFY_API_BASE}/me/player/devices", headers=self._headers(), timeout=5)
            self._handle_response(resp)
            if resp.status_code == 200:
                return resp.json().get("devices", [])
        except Exception:
            pass
        return []

    def get_playback(self) -> Optional[Dict[str, Any]]:
        """Fetch current playback state."""
        if self.is_rate_limited():
            return self._last_playback_data
        try:
            resp = self._safe_request(requests.get, f"{SPOTIFY_API_BASE}/me/player", headers=self._headers(), timeout=5)
            self._handle_response(resp)
            if resp.status_code == 429:
                return self._last_playback_data
            if resp.status_code == 204 or resp.status_code != 200:
                return None
            data = resp.json()
            if not data or "item" not in data or not data["item"]:
                return None

            item = data["item"]
            artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
            images = item.get("album", {}).get("images", [])
            art_url = images[0]["url"] if images else ""

            result = {
                "title": item.get("name", "Unknown Track"),
                "artist": artists,
                "album": item.get("album", {}).get("name", "Unknown Album"),
                "duration_ms": item.get("duration_ms", 0),
                "progress_ms": data.get("progress_ms", 0),
                "is_playing": data.get("is_playing", False),
                "volume": data.get("device", {}).get("volume_percent", 50),
                "device_name": data.get("device", {}).get("name", ""),
                "device_id": data.get("device", {}).get("id", ""),
                "album_art_url": art_url,
                "uri": item.get("uri", ""),
            }
            self._last_playback_data = result
            return result
        except Exception:
            return self._last_playback_data

    def get_playlists(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Retrieve user's playlists with local in-memory caching."""
        if not force_refresh and self._playlists_cache is not None:
            return self._playlists_cache
        if self.is_rate_limited():
            return self._playlists_cache or []
        try:
            resp = self._safe_request(requests.get, f"{SPOTIFY_API_BASE}/me/playlists?limit=50", headers=self._headers(), timeout=5)
            self._handle_response(resp)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results = []
                for p in items:
                    if not p:
                        continue
                    tracks_info = p.get("items") if isinstance(p.get("items"), dict) else p.get("tracks")
                    count = tracks_info.get("total", 0) if isinstance(tracks_info, dict) else 0
                    results.append({
                        "id": p.get("id"),
                        "name": p.get("name", "Untitled"),
                        "tracks_count": count,
                        "uri": p.get("uri"),
                    })
                self._playlists_cache = results
                return results
        except Exception:
            pass
        return self._playlists_cache or []

    def _fetch_fallback_embed_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Fetch tracklist for shared or third-party playlists via Spotify's public embed page.
        
        Spotify's Web API restricts /playlists/{id}/items and /playlists/{id}/tracks for
        development apps on playlists not owned by the developer (returning 403 Forbidden).
        The public embed page provides full tracklists and Spotify URIs without restriction.
        """
        try:
            url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
            resp = self._safe_request(requests.get, url, timeout=5)
            if resp.status_code != 200:
                return []
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text)
            if not m:
                return []
            data = json.loads(m.group(1))
            entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
            track_list = entity.get("trackList", [])
            tracks = []
            for t in track_list:
                dur_ms = t.get("duration", 0)
                duration_s = dur_ms // 1000
                mins, secs = divmod(duration_s, 60)
                uri = t.get("uri", "")
                track_id = uri.split(":")[-1] if uri else ""
                raw_title = t.get("title", "Unknown Track") or "Unknown Track"
                raw_artist = t.get("subtitle", "Unknown Artist") or "Unknown Artist"
                tracks.append({
                    "id": track_id,
                    "name": html.unescape(raw_title),
                    "artist": html.unescape(raw_artist).replace("\xa0", " "),
                    "duration_str": f"{mins:02d}:{secs:02d}",
                    "uri": uri,
                })
            return tracks
        except Exception:
            return []

    def get_playlist_tracks(self, playlist_id: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Retrieve tracks inside a specific playlist with per-playlist caching."""
        if not force_refresh and playlist_id in self._tracks_cache:
            return self._tracks_cache[playlist_id]
        if self.is_rate_limited():
            return self._tracks_cache.get(playlist_id, [])
        try:
            # Query /items endpoint (new Spotify API standard) with fallback to /tracks
            url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/items?limit=100"
            resp = self._safe_request(requests.get, url, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            if resp.status_code != 200 and not self.is_rate_limited():
                url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks?limit=100"
                resp = self._safe_request(requests.get, url, headers=self._headers(), timeout=5)
                self._handle_response(resp)

            if resp.status_code == 200:
                items = resp.json().get("items", [])
                tracks = []
                for item in items:
                    t = item.get("item") or item.get("track")
                    if not t or not isinstance(t, dict):
                        continue
                    artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
                    duration_s = t.get("duration_ms", 0) // 1000
                    mins, secs = divmod(duration_s, 60)
                    tracks.append({
                        "id": t.get("id"),
                        "name": t.get("name", "Unknown Track"),
                        "artist": artists or "Unknown Artist",
                        "duration_str": f"{mins:02d}:{secs:02d}",
                        "uri": t.get("uri", ""),
                    })
                if tracks:
                    self._tracks_cache[playlist_id] = tracks
                    return tracks

            # If Web API returned 403 Forbidden or empty tracks (common for shared/public playlists),
            # fall back to the public Spotify embed page.
            if resp.status_code == 403 or resp.status_code != 200:
                embed_tracks = self._fetch_fallback_embed_tracks(playlist_id)
                self._tracks_cache[playlist_id] = embed_tracks
                return embed_tracks

        except Exception:
            pass

        # Final fallback check if tracks empty
        fallback = self._fetch_fallback_embed_tracks(playlist_id)
        self._tracks_cache[playlist_id] = fallback
        return fallback

    def play(
        self,
        context_uri: Optional[str] = None,
        uris: Optional[List[str]] = None,
        offset: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Resume playback or play a playlist/track. Returns (success, error_message)."""
        if self.is_rate_limited():
            return False, self.get_cooldown_message()
        params = {"device_id": device_id} if device_id else {}
        body: Dict[str, Any] = {}
        if context_uri:
            body["context_uri"] = context_uri
            if offset:
                body["offset"] = offset
        elif uris:
            body["uris"] = uris
        try:
            resp = self._safe_request(requests.put, f"{SPOTIFY_API_BASE}/me/player/play", params=params, json=body or None, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            if resp.status_code in (200, 204):
                return True, ""
            if resp.status_code == 429:
                return False, self.get_cooldown_message()
            err_msg = ""
            try:
                err_msg = resp.json().get("error", {}).get("message", "")
            except Exception:
                pass
            return False, err_msg or f"Error {resp.status_code}"
        except Exception as e:
            return False, str(e)

    def pause(self, device_id: Optional[str] = None) -> bool:
        """Pause playback."""
        if self.is_rate_limited():
            return False
        params = {"device_id": device_id} if device_id else {}
        try:
            resp = self._safe_request(requests.put, f"{SPOTIFY_API_BASE}/me/player/pause", params=params, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def next_track(self, device_id: Optional[str] = None) -> bool:
        """Skip to next track."""
        if self.is_rate_limited():
            return False
        params = {"device_id": device_id} if device_id else {}
        try:
            resp = self._safe_request(requests.post, f"{SPOTIFY_API_BASE}/me/player/next", params=params, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def previous_track(self, device_id: Optional[str] = None) -> bool:
        """Skip to previous track."""
        if self.is_rate_limited():
            return False
        params = {"device_id": device_id} if device_id else {}
        try:
            resp = self._safe_request(requests.post, f"{SPOTIFY_API_BASE}/me/player/previous", params=params, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def set_volume(self, volume_percent: int, device_id: Optional[str] = None) -> bool:
        """Set volume percentage."""
        if self.is_rate_limited():
            return False
        vol = max(0, min(100, volume_percent))
        params = {"volume_percent": vol}
        if device_id:
            params["device_id"] = device_id
        try:
            resp = self._safe_request(requests.put, f"{SPOTIFY_API_BASE}/me/player/volume", params=params, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def transfer_playback(self, device_id: str, play: bool = True) -> bool:
        """Transfer active playback to designated device ID."""
        if self.is_rate_limited():
            return False
        body = {"device_ids": [device_id], "play": play}
        try:
            resp = self._safe_request(requests.put, f"{SPOTIFY_API_BASE}/me/player", json=body, headers=self._headers(), timeout=5)
            self._handle_response(resp)
            return resp.status_code in (200, 204)
        except Exception:
            return False
