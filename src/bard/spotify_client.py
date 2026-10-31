"""Spotify Web API REST & OAuth 2.0 PKCE client."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Any, Dict, List, Optional, Tuple
import requests

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
    """Handles Spotify API calls and token management."""

    def __init__(self, config: BardConfig):
        self.config = config

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
        resp = requests.post(SPOTIFY_TOKEN_URL, data=payload, timeout=10)
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
        resp = requests.post(SPOTIFY_TOKEN_URL, data=payload, timeout=10)
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
        try:
            resp = requests.get(f"{SPOTIFY_API_BASE}/me/player/devices", headers=self._headers(), timeout=5)
            if resp.status_code == 200:
                return resp.json().get("devices", [])
        except Exception:
            pass
        return []

    def get_playback(self) -> Optional[Dict[str, Any]]:
        """Fetch current playback state."""
        try:
            resp = requests.get(f"{SPOTIFY_API_BASE}/me/player", headers=self._headers(), timeout=5)
            if resp.status_code == 204 or resp.status_code != 200:
                return None
            data = resp.json()
            if not data or "item" not in data or not data["item"]:
                return None

            item = data["item"]
            artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
            images = item.get("album", {}).get("images", [])
            art_url = images[0]["url"] if images else ""

            return {
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
        except Exception:
            return None

    def get_playlists(self) -> List[Dict[str, Any]]:
        """Retrieve user's playlists."""
        try:
            resp = requests.get(f"{SPOTIFY_API_BASE}/me/playlists?limit=50", headers=self._headers(), timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                return [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "tracks_count": p.get("tracks", {}).get("total", 0),
                        "uri": p.get("uri"),
                    }
                    for p in items
                    if p
                ]
        except Exception:
            pass
        return []

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Retrieve tracks inside a specific playlist."""
        try:
            resp = requests.get(
                f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks?limit=100",
                headers=self._headers(),
                timeout=5,
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                tracks = []
                for item in items:
                    t = item.get("track")
                    if not t:
                        continue
                    artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
                    duration_s = t.get("duration_ms", 0) // 1000
                    mins, secs = divmod(duration_s, 60)
                    tracks.append({
                        "id": t.get("id"),
                        "name": t.get("name"),
                        "artist": artists,
                        "duration_str": f"{mins:02d}:{secs:02d}",
                        "uri": t.get("uri"),
                    })
                return tracks
        except Exception:
            pass
        return []

    def play(self, context_uri: Optional[str] = None, uris: Optional[List[str]] = None, device_id: Optional[str] = None) -> Tuple[bool, str]:
        """Resume playback or play a playlist/track. Returns (success, error_message)."""
        params = {"device_id": device_id} if device_id else {}
        body: Dict[str, Any] = {}
        if context_uri:
            body["context_uri"] = context_uri
        elif uris:
            body["uris"] = uris
        try:
            resp = requests.put(f"{SPOTIFY_API_BASE}/me/player/play", params=params, json=body or None, headers=self._headers(), timeout=5)
            if resp.status_code in (200, 204):
                return True, ""
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
        params = {"device_id": device_id} if device_id else {}
        resp = requests.put(f"{SPOTIFY_API_BASE}/me/player/pause", params=params, headers=self._headers(), timeout=5)
        return resp.status_code in (200, 204)

    def next_track(self, device_id: Optional[str] = None) -> bool:
        """Skip to next track."""
        params = {"device_id": device_id} if device_id else {}
        resp = requests.post(f"{SPOTIFY_API_BASE}/me/player/next", params=params, headers=self._headers(), timeout=5)
        return resp.status_code in (200, 204)

    def previous_track(self, device_id: Optional[str] = None) -> bool:
        """Skip to previous track."""
        params = {"device_id": device_id} if device_id else {}
        resp = requests.post(f"{SPOTIFY_API_BASE}/me/player/previous", params=params, headers=self._headers(), timeout=5)
        return resp.status_code in (200, 204)

    def set_volume(self, volume_percent: int, device_id: Optional[str] = None) -> bool:
        """Set volume percentage."""
        vol = max(0, min(100, volume_percent))
        params = {"volume_percent": vol}
        if device_id:
            params["device_id"] = device_id
        resp = requests.put(f"{SPOTIFY_API_BASE}/me/player/volume", params=params, headers=self._headers(), timeout=5)
        return resp.status_code in (200, 204)

    def transfer_playback(self, device_id: str, play: bool = True) -> bool:
        """Transfer active playback to designated device ID."""
        body = {"device_ids": [device_id], "play": play}
        resp = requests.put(f"{SPOTIFY_API_BASE}/me/player", json=body, headers=self._headers(), timeout=5)
        return resp.status_code in (200, 204)
