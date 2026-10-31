"""Audio Engine supervisor for librespot streaming daemon."""

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
    """Manages the lifecycle of the headless librespot Spotify Connect engine."""

    def __init__(
        self,
        bin_dir: Optional[Path] = None,
        device_name: str = "Bard",
        bitrate: int = 320,
    ):
        self.device_name = device_name
        self.bitrate = bitrate

        base_dir = bin_dir or (get_default_config_dir() / "bin")
        self.bin_dir = base_dir
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = get_default_config_dir() / "librespot_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        is_win = platform.system() == "Windows"
        self.binary_name = "librespot.exe" if is_win else "librespot"
        self.binary_path = self.bin_dir / self.binary_name

        self._process: Optional[subprocess.Popen] = None
        atexit.register(self.stop)

    def is_installed(self) -> bool:
        """Check if librespot exists locally or in system PATH."""
        if self.binary_path.exists():
            return True
        return shutil.which("librespot") is not None

    def get_executable_path(self) -> str:
        """Return path to executable (local bin or system PATH)."""
        if self.binary_path.exists():
            return str(self.binary_path)
        path_bin = shutil.which("librespot")
        if path_bin:
            return path_bin
        return str(self.binary_path)

    def build_launch_args(self) -> List[str]:
        """Construct command arguments for librespot."""
        args = [
            self.get_executable_path(),
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
        return args

    def start(self) -> bool:
        """Start librespot background process."""
        if self.is_running():
            return True

        args = self.build_launch_args()
        try:
            # Hide console window on Windows
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            self._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )
            return True
        except Exception:
            self._process = None
            return False

    def is_running(self) -> bool:
        """Check if process is active."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def stop(self) -> None:
        """Terminate librespot process cleanly."""
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
