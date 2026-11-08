"""Local MPV audio playback engine with cross-platform JSON-IPC control."""

from __future__ import annotations

import atexit
import json
import os
import platform
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, List, Optional

from bard.audio_engine import AudioEngine


class AudioPlayer:
    """Controls a headless local mpv instance over JSON-IPC."""

    def __init__(
        self,
        binary_path: Optional[str] = None,
        ipc_path: Optional[str] = None,
    ) -> None:
        self.is_win = platform.system() == "Windows"
        self.binary_path = binary_path or AudioEngine.find_mpv() or ("mpv.exe" if self.is_win else "mpv")

        if ipc_path:
            self.ipc_path = ipc_path
        elif self.is_win:
            self.ipc_path = rf"\\.\pipe\bard-mpv-{os.getpid()}"
        else:
            self.ipc_path = f"/tmp/bard-mpv-{os.getpid()}.sock"

        self._process: Optional[subprocess.Popen] = None
        self._ipc_conn: Any = None
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._request_id = 0

        self._start_process()
        atexit.register(self.close)

    def _start_process(self) -> bool:
        """Spawn the headless mpv process."""
        args = [
            self.binary_path,
            "--no-video",
            "--idle=yes",
            f"--input-ipc-server={self.ipc_path}",
            "--no-terminal",
            "--really-quiet",
        ]
        creationflags = 0
        if self.is_win and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
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

    def _connect(self) -> bool:
        """Connect to mpv's IPC server (named pipe or unix domain socket)."""
        if self.is_win:
            try:
                self._ipc_conn = open(self.ipc_path, "r+b", buffering=0)
                return True
            except (FileNotFoundError, OSError):
                return False
        else:
            try:
                af_unix = getattr(socket, "AF_UNIX", None)
                if af_unix is None:
                    return False
                s = socket.socket(af_unix, socket.SOCK_STREAM)
                s.connect(self.ipc_path)
                self._socket = s
                self._ipc_conn = s.makefile("rwb", buffering=0)
                return True
            except (FileNotFoundError, ConnectionRefusedError, OSError):
                return False

    def _ensure_connection(self, retries: int = 20, delay: float = 0.05) -> bool:
        """Ensure connection to the IPC server is active."""
        if self._ipc_conn is not None:
            return True
        if self._process and self._process.poll() is not None:
            return False

        for i in range(retries):
            if self._connect():
                return True
            if i < retries - 1:
                time.sleep(delay)
        return False

    def _disconnect(self) -> None:
        """Safely close and reset the IPC connection."""
        if self._ipc_conn:
            try:
                self._ipc_conn.close()
            except Exception:
                pass
            self._ipc_conn = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _send_command(self, cmd: List[Any], timeout: float = 2.0) -> Optional[dict]:
        """Send a JSON command to mpv and return parsed response."""
        with self._lock:
            if not self._ensure_connection():
                return None
            try:
                self._request_id += 1
                req_id = self._request_id
                payload = json.dumps({"command": cmd, "request_id": req_id}) + "\n"
                self._ipc_conn.write(payload.encode("utf-8"))

                start = time.time()
                while time.time() - start < timeout:
                    line = self._ipc_conn.readline()
                    if not line:
                        break
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if data.get("request_id") == req_id:
                        return data
                return None
            except Exception:
                self._disconnect()
                return None

    def play(self, stream_url: str) -> bool:
        """Load and start playback of a media stream URL."""
        if self._process is None or self._process.poll() is not None:
            self._start_process()

        resp = self._send_command(["loadfile", stream_url, "replace"])
        if resp and resp.get("error") == "success":
            self._send_command(["set_property", "pause", False])
            return True
        return False

    def pause(self) -> None:
        """Pause playback."""
        self._send_command(["set_property", "pause", True])

    def resume(self) -> None:
        """Resume playback."""
        self._send_command(["set_property", "pause", False])

    def toggle_pause(self) -> None:
        """Toggle play/pause state."""
        self._send_command(["cycle", "pause"])

    def stop(self) -> None:
        """Stop playback and unload file."""
        self._send_command(["stop"])

    def seek(self, offset_seconds: float) -> None:
        """Seek relative to current playback position by offset in seconds."""
        self._send_command(["seek", offset_seconds, "relative"])

    def set_volume(self, volume: int) -> None:
        """Set volume level (0-100)."""
        clamped = max(0, min(100, int(volume)))
        self._send_command(["set_property", "volume", clamped])

    def get_volume(self) -> int:
        """Get current volume level (0-100). Default 100 on error."""
        resp = self._send_command(["get_property", "volume"])
        if resp and resp.get("error") == "success" and resp.get("data") is not None:
            try:
                return int(round(float(resp["data"])))
            except (ValueError, TypeError):
                pass
        return 100

    def get_position(self) -> float:
        """Get current playback position in seconds. Default 0.0 on error or idle."""
        resp = self._send_command(["get_property", "time-pos"])
        if resp and resp.get("error") == "success" and resp.get("data") is not None:
            try:
                return float(resp["data"])
            except (ValueError, TypeError):
                pass
        return 0.0

    def get_duration(self) -> float:
        """Get total media duration in seconds. Default 0.0 on error or idle."""
        resp = self._send_command(["get_property", "duration"])
        if resp and resp.get("error") == "success" and resp.get("data") is not None:
            try:
                return float(resp["data"])
            except (ValueError, TypeError):
                pass
        return 0.0

    def is_playing(self) -> bool:
        """Check if audio is actively playing (not paused, not idle, process running)."""
        if self._process is None or self._process.poll() is not None:
            return False

        resp_pause = self._send_command(["get_property", "pause"])
        if not resp_pause or resp_pause.get("error") != "success":
            return False
        if resp_pause.get("data") is True:
            return False

        resp_idle = self._send_command(["get_property", "idle-active"])
        if resp_idle and resp_idle.get("error") == "success":
            if resp_idle.get("data") is True:
                return False

        return True

    def close(self) -> None:
        """Terminate the mpv subprocess cleanly and remove socket files if any."""
        with self._lock:
            if self._ipc_conn:
                try:
                    quit_msg = json.dumps({"command": ["quit"]}) + "\n"
                    self._ipc_conn.write(quit_msg.encode("utf-8"))
                except Exception:
                    pass
                try:
                    self._ipc_conn.close()
                except Exception:
                    pass
                self._ipc_conn = None

            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=1.5)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
            self._process = None

            if not self.is_win and self.ipc_path:
                try:
                    p = Path(self.ipc_path)
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
