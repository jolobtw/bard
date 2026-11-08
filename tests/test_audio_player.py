"""Tests for AudioPlayer MPV JSON-IPC control."""

import io
import json
import platform
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

