"""Cross-platform configuration and credential management for Bard."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


def get_default_config_dir() -> Path:
    """Return ~/.config/bard cross-platform path."""
    return Path.home() / ".config" / "bard"


class BardConfig:
    """Handles loading, saving, and updating Bard application state and tokens."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            self.config_dir = get_default_config_dir()
            self.config_path = self.config_dir / "config.json"
        else:
            self.config_path = config_path
            self.config_dir = config_path.parent

        self.client_id: str = ""
        self.redirect_uri: str = "http://127.0.0.1:8888/callback"
        self.device_name: str = "Bard"
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.token_expiry: float = 0.0

        self.load()

    def load(self) -> None:
        """Load settings from config file if present."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            self.client_id = data.get("client_id", self.client_id)
            self.redirect_uri = data.get("redirect_uri", self.redirect_uri)
            self.device_name = data.get("device_name", self.device_name)
            self.access_token = data.get("access_token", self.access_token)
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.token_expiry = data.get("token_expiry", self.token_expiry)
        except Exception:
            pass

    def save(self) -> None:
        """Persist settings to config file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "device_name": self.device_name,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def set_tokens(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        """Store OAuth tokens and calculate expiration timestamp."""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        self.token_expiry = time.time() + expires_in - 60  # 60s safety buffer

    def is_token_expired(self) -> bool:
        """Check if current access token is missing or expired."""
        if not self.access_token:
            return True
        return time.time() >= self.token_expiry
