"""Data models for Bard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Track:
    """Represents a playable music track."""

    id: str
    title: str
    artist: str
    album: str
    duration_seconds: int
    thumbnail_url: str
    stream_url: Optional[str] = None

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return self.duration_seconds * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert track to dictionary compatible with ZenStage UI."""
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_seconds": self.duration_seconds,
            "duration_ms": self.duration_ms,
            "thumbnail_url": self.thumbnail_url,
            "album_art_url": self.thumbnail_url,
            "stream_url": self.stream_url,
        }
