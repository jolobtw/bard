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

