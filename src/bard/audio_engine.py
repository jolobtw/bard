"""Audio Engine supervisor for standalone Spotify streaming daemon (librespot / spotify_player)."""

from __future__ import annotations

import atexit
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from bard.config import get_default_config_dir


class AudioEngine:
    """Manages the lifecycle of the headless Spotify Connect streaming engine."""

    def __init__(
        self,
        bin_dir: Optional[Path] = None,
        device_name: str = "Bard",
        bitrate: int = 320,
        client_id: str = "",
    ):
        self.device_name = device_name
        self.bitrate = bitrate
        self.client_id = client_id

        base_dir = bin_dir or (get_default_config_dir() / "bin")
        self.bin_dir = base_dir
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = get_default_config_dir() / "librespot_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        is_win = platform.system() == "Windows"
        self.is_win = is_win

        # Look for spotify_player.exe or librespot.exe
        if is_win:
            if (self.bin_dir / "spotify_player.exe").exists():
                self.binary_name = "spotify_player.exe"
            else:
                self.binary_name = "librespot.exe"
        else:
            if (self.bin_dir / "spotify_player").exists():
                self.binary_name = "spotify_player"
            else:
                self.binary_name = "librespot"

        self.binary_path = self.bin_dir / self.binary_name
        self._process: Optional[subprocess.Popen] = None
        atexit.register(self.stop)

    def is_installed(self) -> bool:
        """Check if streaming engine binary exists."""
        if self.binary_path.exists():
            return True
        return shutil.which("spotify_player") is not None or shutil.which("librespot") is not None

    def get_executable_path(self) -> str:
        """Return path to executable."""
        if self.binary_path.exists():
            return str(self.binary_path)
        for name in ("spotify_player", "librespot"):
            p = shutil.which(name)
            if p:
                return p
        return str(self.binary_path)

    def is_spotify_player(self) -> bool:
        return "spotify_player" in self.binary_name

    def configure_spotify_player(self, client_id: str = "") -> None:
        """Ensure ~/.config/spotify-player/app.toml is configured for Bard."""
        if not self.is_spotify_player():
            return
        conf_dir = Path.home() / ".config" / "spotify-player"
        conf_dir.mkdir(parents=True, exist_ok=True)
        app_toml = conf_dir / "app.toml"

        content = f"""[device]
name = "{self.device_name}"
device_type = "speaker"
volume = 80
bitrate = {self.bitrate}
audio_cache = false
normalization = false
autoplay = false
"""
        with open(app_toml, "w", encoding="utf-8") as f:
            f.write(content)

    def has_credentials(self) -> bool:
        """Check if engine credentials already exist."""
        if self.is_spotify_player():
            cred = Path.home() / ".cache" / "spotify-player" / "credentials.json"
            return cred.exists()
        return False

    def authenticate(self) -> bool:
        """Run interactive authentication for the streaming engine."""
        if not self.is_spotify_player():
            return True
        exe = self.get_executable_path()
        try:
            # Run authenticate in foreground so user sees browser prompt
            proc = subprocess.run([exe, "authenticate"])
            return proc.returncode == 0
        except Exception:
            return False

    def build_launch_args(self) -> List[str]:
        """Construct command arguments for the daemon."""
        exe = self.get_executable_path()
        if self.is_spotify_player():
            return [exe, "-d"]
        return [
            exe,
            "--name",
            self.device_name,
            "--bitrate",
            str(self.bitrate),
            "--cache",
            str(self.cache_dir),
            "--enable-oauth",
            "--volume-ctrl",
            "linear",
        ]

    def start(self) -> bool:
        """Start streaming engine background daemon."""
        if self.is_running():
            return True

        if not self.is_installed():
            return False

        if self.is_spotify_player() and not self.has_credentials():
            return False

        args = self.build_launch_args()
        try:
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            self._process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            return True
        except Exception:
            self._process = None
            return False

    def is_running(self) -> bool:
        """Check if daemon is currently active."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def stop(self) -> None:
        """Terminate streaming engine cleanly."""
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None
