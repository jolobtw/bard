"""Tests for bard.__main__ entrypoint."""

import pytest
from unittest.mock import MagicMock, patch

from bard.__main__ import ensure_audio_engine, main, run_device_login, run_device_logout


def test_ensure_audio_engine_missing():
    with patch("bard.audio_engine.AudioEngine.find_mpv", return_value=None):
        assert ensure_audio_engine() is False


def test_ensure_audio_engine_found():
    with patch("bard.audio_engine.AudioEngine.find_mpv", return_value="/path/to/mpv"):
        assert ensure_audio_engine() is True


def test_main_exits_when_audio_engine_missing():
    """Verify main() exits with code 1 if mpv is not found."""
    with patch("sys.argv", ["bard"]), patch("bard.__main__.ensure_audio_engine", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_runs_app_when_audio_engine_present():
    """Verify main() instantiates and runs BardApp if mpv is found."""
    mock_app = MagicMock()
    with patch("sys.argv", ["bard"]), \
         patch("bard.__main__.ensure_audio_engine", return_value=True), \
         patch("bard.__main__.BardConfig"), \
         patch("bard.__main__.YTMusicClient"), \
         patch("bard.__main__.AudioPlayer"), \
         patch("bard.__main__.BardApp", return_value=mock_app):
        main()
        mock_app.run.assert_called_once()


def test_run_device_login_success():
    """Verify run_device_login requests code, opens browser, polls, and saves tokens."""
    mock_oauth = MagicMock()
    mock_oauth.get_device_code.return_value = {
        "device_code": "dev123",
        "user_code": "ABCD-1234",
        "verification_url": "https://www.google.com/device",
        "interval": 1,
    }
    mock_oauth.poll_for_token.return_value = {
        "access_token": "token123",
        "refresh_token": "ref123",
    }

    with patch("webbrowser.open") as mock_open:
        success = run_device_login(mock_oauth)
        assert success is True
        mock_oauth.get_device_code.assert_called_once()
        mock_open.assert_called_once_with("https://www.google.com/device")
        mock_oauth.poll_for_token.assert_called_once_with("dev123", interval=1)
        mock_oauth.save_tokens.assert_called_once_with({
            "access_token": "token123",
            "refresh_token": "ref123",
        })


def test_run_device_login_failure():
    """Verify run_device_login handles missing device code or poll timeout gracefully."""
    # Failure at get_device_code
    mock_oauth = MagicMock()
    mock_oauth.get_device_code.return_value = None
    assert run_device_login(mock_oauth) is False

    # Failure at poll_for_token
    mock_oauth2 = MagicMock()
    mock_oauth2.get_device_code.return_value = {
        "device_code": "dev123",
        "user_code": "ABCD-1234",
        "verification_url": "https://www.google.com/device",
        "interval": 5,
    }
    mock_oauth2.poll_for_token.return_value = None
    with patch("webbrowser.open"):
        assert run_device_login(mock_oauth2) is False
        mock_oauth2.save_tokens.assert_not_called()


def test_run_device_logout():
    """Verify run_device_logout clears tokens and returns True."""
    mock_oauth = MagicMock()
    success = run_device_logout(mock_oauth)
    assert success is True
    mock_oauth.clear_tokens.assert_called_once()


def test_main_cli_args_login_and_logout():
    """Verify CLI flags route to login and logout handlers with clean exit."""
    with patch("sys.argv", ["bard", "--login"]), \
         patch("bard.__main__.run_device_login", return_value=True) as mock_login, \
         pytest.raises(SystemExit) as exc_info:
        main()
    mock_login.assert_called_once()
    assert exc_info.value.code == 0

    with patch("sys.argv", ["bard", "--logout"]), \
         patch("bard.__main__.run_device_logout", return_value=True) as mock_logout, \
         pytest.raises(SystemExit) as exc_info:
        main()
    mock_logout.assert_called_once()
    assert exc_info.value.code == 0


def test_main_cli_arg_version(capsys):
    """Verify --version flag prints Bard version and exits cleanly."""
    with patch("sys.argv", ["bard", "--version"]), pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Bard v0.2.0" in captured.out or "Bard v0.2.0" in captured.err


def test_configure_cookies_zen_and_clear(tmp_path):
    from bard.__main__ import configure_cookies
    from bard.config import BardConfig

    cfg = BardConfig(config_path=tmp_path / "config.json")
    with patch("bard.ytmusic_client._resolve_zen_profiles_dir", return_value="C:/zen/Profiles"):
        assert configure_cookies("zen", config=cfg) is True

    reloaded = BardConfig(config_path=tmp_path / "config.json")
    assert reloaded.cookies_from_browser == "zen"
    assert reloaded.cookies_file == ""

    assert configure_cookies("clear", config=reloaded) is True
    cleared = BardConfig(config_path=tmp_path / "config.json")
    assert cleared.cookies_from_browser == ""
    assert cleared.cookies_profile == ""
    assert cleared.cookies_file == ""


def test_main_cli_arg_cookies():
    with patch("sys.argv", ["bard", "--cookies", "zen"]), \
         patch("bard.__main__.configure_cookies", return_value=True) as mock_cookies, \
         pytest.raises(SystemExit) as exc_info:
        main()
    mock_cookies.assert_called_once_with("zen", profile="")
    assert exc_info.value.code == 0

