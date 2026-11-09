"""Tests for AudioPlayer MPV JSON-IPC control."""

import io
import json
import platform
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from bard.audio_player import AudioPlayer


def test_player_command_generation():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        with patch.object(player, "_send_command") as mock_cmd:
            player.pause()
            mock_cmd.assert_called_with(["set_property", "pause", True])

            player.resume()
            mock_cmd.assert_called_with(["set_property", "pause", False])

            player.toggle_pause()
            mock_cmd.assert_called_with(["cycle", "pause"])

            player.set_volume(85)
            mock_cmd.assert_called_with(["set_property", "volume", 85])


def test_player_play_and_stop():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        with patch.object(player, "_send_command") as mock_cmd:
            mock_cmd.return_value = {"error": "success"}
            success = player.play("https://example.com/stream.webm")
            assert success is True
            mock_cmd.assert_any_call(["loadfile", "https://example.com/stream.webm", "replace"])
            mock_cmd.assert_any_call(["set_property", "pause", False])

            player.stop()
            mock_cmd.assert_called_with(["stop"])


def test_player_seek():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        with patch.object(player, "_send_command") as mock_cmd:
            player.seek(10.0)
            mock_cmd.assert_called_with(["seek", 10.0, "relative"])


def test_player_getters():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        with patch.object(player, "_send_command") as mock_cmd:
            # Volume
            mock_cmd.return_value = {"data": 75.0, "error": "success"}
            assert player.get_volume() == 75

            # Position
            mock_cmd.return_value = {"data": 42.5, "error": "success"}
            assert player.get_position() == 42.5

            # Duration
            mock_cmd.return_value = {"data": 180.0, "error": "success"}
            assert player.get_duration() == 180.0


def test_player_is_playing_states():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        # 1. Playing: pause=False, idle-active=False
        def mock_send(cmd):
            prop = cmd[1]
            if prop == "pause":
                return {"data": False, "error": "success"}
            if prop == "idle-active":
                return {"data": False, "error": "success"}
            return None

        with patch.object(player, "_send_command", side_effect=mock_send):
            assert player.is_playing() is True

        # 2. Paused: pause=True, idle-active=False
        def mock_send_paused(cmd):
            prop = cmd[1]
            if prop == "pause":
                return {"data": True, "error": "success"}
            if prop == "idle-active":
                return {"data": False, "error": "success"}
            return None

        with patch.object(player, "_send_command", side_effect=mock_send_paused):
            assert player.is_playing() is False

        # 3. Idle: pause=False, idle-active=True
        def mock_send_idle(cmd):
            prop = cmd[1]
            if prop == "pause":
                return {"data": False, "error": "success"}
            if prop == "idle-active":
                return {"data": True, "error": "success"}
            return None

        with patch.object(player, "_send_command", side_effect=mock_send_idle):
            assert player.is_playing() is False


def test_player_safe_defaults_when_dead():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # dead process
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        assert player.is_playing() is False
        assert player.get_position() == 0.0
        assert player.get_duration() == 0.0
        assert player.get_volume() == 100


def test_player_close():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        mock_conn = MagicMock()
        player._ipc_conn = mock_conn

        player.close()
        mock_conn.close.assert_called_once()
        mock_proc.terminate.assert_called_once()
        assert player._process is None
        assert player._ipc_conn is None


def test_player_send_command_filters_events():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        # Mock an IPC connection that outputs an event line followed by the response line
        mock_conn = MagicMock()
        event_line = json.dumps({"event": "start-file"}).encode("utf-8") + b"\n"
        resp_line = json.dumps({"request_id": 1, "data": True, "error": "success"}).encode("utf-8") + b"\n"
        mock_conn.readline.side_effect = [event_line, resp_line]

        player._ipc_conn = mock_conn
        res = player._send_command(["get_property", "idle-active"])
        assert res == {"request_id": 1, "data": True, "error": "success"}


def test_player_send_command_handles_io_error():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")

        mock_conn = MagicMock()
        mock_conn.write.side_effect = OSError("Pipe broken")
        player._ipc_conn = mock_conn

        res = player._send_command(["get_property", "volume"])
        assert res is None
        assert player._ipc_conn is None


def test_player_unix_socket_connect_and_cleanup(tmp_path):
    with patch("bard.audio_player.subprocess.Popen") as mock_popen, \
         patch("bard.audio_player.socket.socket") as mock_socket_cls, \
         patch("bard.audio_player.socket.AF_UNIX", 1, create=True):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        mock_sock_inst = MagicMock()
        mock_file = MagicMock()
        mock_sock_inst.makefile.return_value = mock_file
        mock_socket_cls.return_value = mock_sock_inst

        fake_sock_path = tmp_path / "test.sock"
        fake_sock_path.touch()

        player = AudioPlayer(binary_path="dummy_mpv", ipc_path=str(fake_sock_path))
        player.is_win = False  # simulate Unix

        assert player._connect() is True
        assert player._socket == mock_sock_inst
        assert player._ipc_conn == mock_file

        player.close()
        mock_sock_inst.close.assert_called_once()
        assert not fake_sock_path.exists()


def test_player_restart_process_disconnects_stale_ipc():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc1 = MagicMock()
        mock_proc1.poll.return_value = None
        mock_popen.return_value = mock_proc1
        player = AudioPlayer(binary_path="dummy_mpv")

        # Simulate active stale IPC connection on dead process
        stale_conn = MagicMock()
        player._ipc_conn = stale_conn
        mock_proc1.poll.return_value = 1  # dead process

        # _ensure_connection must detect dead process, disconnect stale conn, and return False
        assert player._ensure_connection() is False
        stale_conn.close.assert_called_once()
        assert player._ipc_conn is None

        # Re-assign another stale connection and invoke _start_process()
        stale_conn2 = MagicMock()
        player._ipc_conn = stale_conn2
        mock_proc2 = MagicMock()
        mock_proc2.poll.return_value = None
        mock_popen.return_value = mock_proc2

        player._start_process()
        stale_conn2.close.assert_called_once()
        assert player._ipc_conn is None
        assert player._process == mock_proc2


def test_player_close_taskkill_fallback_on_windows():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen, \
         patch("bard.audio_player.subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        # poll always returns None to simulate stubborn process
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        player = AudioPlayer(binary_path="dummy_mpv")
        player.is_win = True
        player.close()

        mock_proc.terminate.assert_called_once()
        mock_run.assert_called_once_with(
            ["taskkill", "/F", "/T", "/PID", "9999"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
        )
        mock_proc.kill.assert_called_once()
        assert player._process is None


def test_player_assign_to_job_safe_on_mock_or_invalid_pid():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = "not-an-int"
        mock_popen.return_value = mock_proc

        player = AudioPlayer(binary_path="dummy_mpv")
        # Should return without exception
        player._assign_to_job()



