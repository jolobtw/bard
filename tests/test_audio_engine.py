"""Test AudioEngine librespot manager."""

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
from bard.audio_engine import AudioEngine


def test_audio_engine_binary_name(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path)
    if platform.system() == "Windows":
        assert engine.binary_name == "librespot.exe"
    else:
        assert engine.binary_name == "librespot"
    assert engine.binary_path == tmp_path / engine.binary_name


def test_audio_engine_launch_args(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path, device_name="Bard")
    args = engine.build_launch_args()
    assert "--name" in args
    assert "Bard" in args
    assert "--enable-oauth" in args


def test_audio_engine_process_lifecycle(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path)
    (tmp_path / engine.binary_name).touch()
    
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # running
    
    with patch("subprocess.Popen", return_value=mock_proc):
        engine.start()
        assert engine.is_running() is True
        
        engine.stop()
        mock_proc.terminate.assert_called_once()


def test_audio_engine_go_librespot(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path, device_name="Bard")
    (tmp_path / "go-librespot").touch()
    assert engine.is_installed() is True
    args = engine.build_launch_args()
    assert any("device_name=Bard" in a for a in args)
    assert any("credentials.type=device_auth" in a for a in args)


def test_audio_engine_go_librespot_credentials(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path, device_name="Bard")
    (tmp_path / "go-librespot").touch()
    state_file = tmp_path / "state.json"
    
    with patch.object(engine, "get_state_file", return_value=state_file):
        # State file missing
        assert engine.has_credentials() is False

        # State file with empty credentials
        state_file.write_text('{"credentials": {"username": "", "data": null}}', encoding="utf-8")
        assert engine.has_credentials() is False

        # State file with valid credentials
        state_file.write_text('{"credentials": {"username": "tester", "data": "base64blob"}}', encoding="utf-8")
        assert engine.has_credentials() is True


def test_audio_engine_start_detects_immediate_crash(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path)
    (tmp_path / engine.binary_name).touch()
    
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Exited immediately with error
    
    with patch("subprocess.Popen", return_value=mock_proc):
        success = engine.start()
        assert success is False
        assert engine.is_running() is False


def test_audio_engine_authenticate_device_auth_captures_url(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path, device_name="Bard")
    (tmp_path / "go-librespot").touch()
    state_file = tmp_path / "state.json"
    
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, None, 0]
    mock_proc.stdout.readline.side_effect = [
        'time="2026-11-07T14:00:00" level=info msg="running go-librespot"\n',
        'time="2026-11-07T14:00:01" level=info msg="to complete authentication visit https://spotify.com/pair?code=ABC123 and, if prompted, enter code ABC123"\n',
        "",
    ]
    
    captured = []
    def callback(url: str, code: str):
        captured.append((url, code))
        # Simulate browser pairing writing credentials
        state_file.write_text('{"credentials": {"username": "user", "data": "authdata"}}', encoding="utf-8")

    with patch.object(engine, "get_state_file", return_value=state_file), \
         patch("subprocess.Popen", return_value=mock_proc):
        state_file.write_text('{"credentials": {"username": "", "data": null}}', encoding="utf-8")
        result = engine.authenticate(on_pair_url=callback)
        assert len(captured) == 1
        assert captured[0] == ("https://spotify.com/pair?code=ABC123", "ABC123")
        assert result is True


def test_audio_engine_mpv_discovery(tmp_path: Path):
    engine = AudioEngine(bin_dir=tmp_path)
    mpv_file = "mpv.com" if platform.system() == "Windows" else "mpv"
    (tmp_path / mpv_file).touch()

    # Re-initialize with mpv file present in bin_dir
    engine_with_mpv = AudioEngine(bin_dir=tmp_path)
    assert engine_with_mpv.binary_name == mpv_file
    assert engine_with_mpv.is_installed() is True
    assert engine_with_mpv.is_mpv() is True
    assert engine_with_mpv.get_mpv_path() == str(tmp_path / mpv_file)
    assert "--no-video" in engine_with_mpv.build_launch_args()


def test_audio_engine_find_mpv_system_path(tmp_path: Path):
    with patch("shutil.which", return_value="/mock/path/mpv"):
        found = AudioEngine.find_mpv(bin_dir=tmp_path)
        assert found == "/mock/path/mpv"


def test_audio_engine_find_mpv_local_priority_across_candidates(tmp_path: Path):
    """Verify local bin directory is checked for all candidates before system PATH."""
    local_target = tmp_path / ("mpv.exe" if platform.system() == "Windows" else "mpv")
    local_target.touch()

    def mock_which(name: str):
        if name == "mpv.com":
            return "/system/path/mpv.com"
        return None

    with patch("shutil.which", side_effect=mock_which):
        found = AudioEngine.find_mpv(bin_dir=tmp_path)
        # Must return the local file, not the system PATH match from earlier candidate
        assert found == str(local_target)


def test_audio_engine_prefers_mpv_exe_over_com(tmp_path: Path):
    """Verify mpv.exe is preferred over mpv.com on Windows."""
    if platform.system() != "Windows":
        return
    (tmp_path / "mpv.com").touch()
    (tmp_path / "mpv.exe").touch()

    engine = AudioEngine(bin_dir=tmp_path)
    assert engine.binary_name == "mpv.exe"
    assert AudioEngine.find_mpv(bin_dir=tmp_path) == str(tmp_path / "mpv.exe")




