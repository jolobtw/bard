"""Tests for bard.__main__ entrypoint."""

import pytest
from unittest.mock import MagicMock, patch

from bard.__main__ import ensure_audio_engine, main


def test_ensure_audio_engine_missing():
    with patch("bard.audio_engine.AudioEngine.find_mpv", return_value=None):
        assert ensure_audio_engine() is False


def test_ensure_audio_engine_found():
    with patch("bard.audio_engine.AudioEngine.find_mpv", return_value="/path/to/mpv"):
        assert ensure_audio_engine() is True


def test_main_exits_when_audio_engine_missing():
    """Verify main() exits with code 1 if mpv is not found."""
    with patch("bard.__main__.ensure_audio_engine", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_runs_app_when_audio_engine_present():
    """Verify main() instantiates and runs BardApp if mpv is found."""
    mock_app = MagicMock()
    with patch("bard.__main__.ensure_audio_engine", return_value=True), \
         patch("bard.__main__.BardConfig"), \
         patch("bard.__main__.YTMusicClient"), \
         patch("bard.__main__.AudioPlayer"), \
         patch("bard.__main__.BardApp", return_value=mock_app):
        main()
        mock_app.run.assert_called_once()
