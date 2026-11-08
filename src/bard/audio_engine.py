"""Audio Engine supervisor for standalone Spotify streaming daemon (librespot / go-librespot)."""

from __future__ import annotations

import atexit
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

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

        # Look for mpv, librespot, or go-librespot
        if is_win:
            if (self.bin_dir / "mpv.com").exists():
                self.binary_name = "mpv.com"
            elif (self.bin_dir / "mpv.exe").exists():
                self.binary_name = "mpv.exe"
            elif (self.bin_dir / "librespot.exe").exists():
                self.binary_name = "librespot.exe"
            elif (self.bin_dir / "go-librespot.exe").exists():
                self.binary_name = "go-librespot.exe"
            else:
                self.binary_name = "librespot.exe"
        else:
            if (self.bin_dir / "mpv").exists():
                self.binary_name = "mpv"
            elif (self.bin_dir / "librespot").exists():
                self.binary_name = "librespot"
            elif (self.bin_dir / "go-librespot").exists():
                self.binary_name = "go-librespot"
            else:
                self.binary_name = "librespot"

        self.binary_path = self.bin_dir / self.binary_name
        self._process: Optional[subprocess.Popen] = None
        atexit.register(self.stop)

    @classmethod
    def find_mpv(cls, bin_dir: Optional[Path] = None) -> Optional[str]:
        """Find mpv binary in bin_dir (~/.config/bard/bin) or system PATH."""
        base_dir = bin_dir or (get_default_config_dir() / "bin")
        candidates = ["mpv.com", "mpv.exe", "mpv"] if platform.system() == "Windows" else ["mpv"]
        for name in candidates:
            local = base_dir / name
            if local.exists():
                return str(local)
            sys_path = shutil.which(name)
            if sys_path:
                return sys_path
        return None

    def get_mpv_path(self) -> Optional[str]:
        """Return path to mpv executable."""
        return self.find_mpv(self.bin_dir)

    def is_installed(self) -> bool:
        """Check if streaming engine binary exists."""
        if self.binary_path.exists():
            return True
        for name in ("mpv.com", "mpv.exe", "mpv", "librespot", "go-librespot", "librespot.exe", "go-librespot.exe"):
            if (self.bin_dir / name).exists() or shutil.which(name) is not None:
                return True
        return False

    def get_executable_path(self) -> str:
        """Return path to executable (local bin or system PATH)."""
        if self.binary_path.exists():
            return str(self.binary_path)
        for name in ("mpv.com", "mpv.exe", "mpv", "librespot", "go-librespot", "librespot.exe", "go-librespot.exe"):
            p_local = self.bin_dir / name
            if p_local.exists():
                return str(p_local)
            p_sys = shutil.which(name)
            if p_sys:
                return p_sys
        return str(self.binary_path)

    def is_mpv(self) -> bool:
        """Check if the resolved streaming engine is mpv."""
        exe = self.get_executable_path()
        return "mpv" in os.path.basename(exe).lower()

    def is_go_librespot(self) -> bool:
        """Check if the resolved streaming engine is go-librespot."""
        exe = self.get_executable_path()
        return "go-librespot" in os.path.basename(exe).lower()

    def is_spotify_player(self) -> bool:
        return "spotify_player" in self.binary_name.lower()

    def get_state_file(self) -> Path:
        """Return path to go-librespot state.json."""
        if self.is_win:
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
            return base / "go-librespot" / "state.json"
        elif platform.system() == "Darwin":
            return Path.home() / "Library" / "Application Support" / "go-librespot" / "state.json"
        else:
            return Path.home() / ".config" / "go-librespot" / "state.json"

    def ensure_windows_dependencies(self) -> bool:
        """Verify and restore MinGW runtime DLLs required by go-librespot on Windows."""
        if not self.is_win or not self.is_go_librespot():
            return True

        required_dlls = [
            "libFLAC.dll",
            "libmpg123-0.dll",
            "libogg-0.dll",
            "libvorbis-0.dll",
            "libvorbisenc-2.dll",
            "libwinpthread-1.dll",
        ]
        missing = [dll for dll in required_dlls if not (self.bin_dir / dll).exists()]
        if not missing:
            return True

        # Attempt to copy missing runtime DLLs from Git for Windows if available
        git_mingw = Path(r"C:\Program Files\Git\mingw64\bin")
        if git_mingw.exists():
            for dll_name in ["libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll"]:
                src = git_mingw / dll_name
                dst = self.bin_dir / dll_name
                if src.exists() and not dst.exists():
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass

        # Check again
        still_missing = [dll for dll in required_dlls if not (self.bin_dir / dll).exists()]
        return len(still_missing) == 0

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

        if self.is_go_librespot():
            state_file = self.get_state_file()
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    creds = data.get("credentials") or {}
                    if creds.get("username") and creds.get("data"):
                        return True
                except Exception:
                    pass
            return False

        # Native Rust librespot manages tokens in cache or via OAuth flags
        return True

    def authenticate(self, on_pair_url: Optional[Callable[[str, str], None]] = None) -> bool:
        """Run interactive authentication for the streaming engine."""
        if self.is_spotify_player():
            exe = self.get_executable_path()
            try:
                proc = subprocess.run([exe, "authenticate"])
                return proc.returncode == 0
            except Exception:
                return False

        if self.is_go_librespot():
            self.ensure_windows_dependencies()
            exe = self.get_executable_path()
            state_file = self.get_state_file()
            lockfile = state_file.parent / "lockfile"
            if lockfile.exists():
                try:
                    lockfile.unlink()
                except Exception:
                    pass

            args = [
                exe,
                "-c",
                f"device_name={self.device_name}",
                "-c",
                "credentials.type=device_auth",
                "-c",
                "log_level=info",
            ]

            creationflags = 0
            if self.is_win:
                creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=creationflags,
                )
            except Exception:
                return False

            url_found = False
            start_time = time.time()

            try:
                while time.time() - start_time < 90:
                    if proc.poll() is not None:
                        break
                    line = proc.stdout.readline() if proc.stdout else ""
                    if line:
                        match = re.search(r"(https://spotify\.com/pair\?code=([A-Z0-9]+))", line)
                        if match and not url_found:
                            pair_url = match.group(1)
                            code = match.group(2)
                            url_found = True
                            if on_pair_url:
                                on_pair_url(pair_url, code)
                            else:
                                import webbrowser
                                webbrowser.open(pair_url)

                    if self.has_credentials():
                        time.sleep(1)
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                        except Exception:
                            pass
                        if lockfile.exists():
                            try:
                                lockfile.unlink()
                            except Exception:
                                pass
                        return True
                    time.sleep(0.2)
            finally:
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=2)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                if lockfile.exists():
                    try:
                        lockfile.unlink()
                    except Exception:
                        pass

            return self.has_credentials()

        return True

    def build_launch_args(self) -> List[str]:
        """Construct command arguments for the daemon."""
        exe = self.get_executable_path()
        basename = os.path.basename(exe).lower()
        if "mpv" in basename:
            return [exe, "--no-video", "--idle=yes"]
        if "go-librespot" in basename:
            return [
                exe,
                "-c",
                f"device_name={self.device_name}",
                "-c",
                f"bitrate={self.bitrate}",
                "-c",
                "credentials.type=device_auth",
            ]
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

        if self.is_go_librespot():
            self.ensure_windows_dependencies()
            state_file = self.get_state_file()
            lockfile = state_file.parent / "lockfile"
            if lockfile.exists():
                try:
                    lockfile.unlink()
                except Exception:
                    pass

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
            # Give daemon a moment to initialize and ensure it didn't exit on launch
            time.sleep(0.4)
            if self._process.poll() is not None:
                self._process = None
                return False
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
