"""Unit tests for YTMusic OAuth 2.0 Device Code Manager & Token Persistence."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from bard.config import BardConfig
from bard.oauth import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEVICE_CODE_URL,
    TOKEN_URL,
    YTMusicOAuth,
)


def test_oauth_get_device_code():
    with patch("bard.oauth.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "device_code": "dev123",
            "user_code": "ABCD-WXYZ",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }
        oauth = YTMusicOAuth()
        res = oauth.get_device_code()
        assert res["user_code"] == "ABCD-WXYZ"
        assert res["verification_url"] == "https://www.google.com/device"
        assert res["device_code"] == "dev123"
        assert res["expires_in"] == 1800
        assert res["interval"] == 5

        mock_post.assert_called_once_with(
            DEVICE_CODE_URL,
            data={
                "client_id": DEFAULT_CLIENT_ID,
                "scope": "https://www.googleapis.com/auth/youtube",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )


def test_oauth_get_device_code_failure():
    with patch("bard.oauth.requests.post") as mock_post:
        mock_post.return_value.status_code = 400
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("Bad Request")
        oauth = YTMusicOAuth()
        with pytest.raises(requests.HTTPError):
            oauth.get_device_code()


def test_oauth_save_load_clear_tokens(tmp_path: Path):
    token_file = tmp_path / "oauth.json"
    oauth = YTMusicOAuth(token_path=token_file)

    assert not oauth.is_authenticated()
    assert oauth.load_tokens() is None

    tokens = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    oauth.save_tokens(tokens)

    assert token_file.exists()
    assert oauth.is_authenticated()

    loaded = oauth.load_tokens()
    assert loaded is not None
    assert loaded["access_token"] == "test_access_token"
    assert loaded["refresh_token"] == "test_refresh_token"
    assert loaded["client_id"] == DEFAULT_CLIENT_ID
    assert loaded["client_secret"] == DEFAULT_CLIENT_SECRET
    assert loaded["token_type"] == "Bearer"
    assert "expires_at" in loaded

    oauth.clear_tokens()
    assert not token_file.exists()
    assert not oauth.is_authenticated()
    assert oauth.load_tokens() is None


def test_oauth_load_invalid_tokens(tmp_path: Path):
    token_file = tmp_path / "oauth.json"
    oauth = YTMusicOAuth(token_path=token_file)

    # Corrupt JSON
    token_file.write_text("invalid json", encoding="utf-8")
    assert oauth.load_tokens() is None
    assert not oauth.is_authenticated()

    # JSON missing required tokens
    token_file.write_text(json.dumps({"some_key": "some_value"}), encoding="utf-8")
    assert oauth.load_tokens() is None
    assert not oauth.is_authenticated()


def test_oauth_poll_for_token_success(tmp_path: Path):
    token_file = tmp_path / "oauth.json"
    oauth = YTMusicOAuth(token_path=token_file)

    pending_resp = MagicMock()
    pending_resp.status_code = 428
    pending_resp.text = '{"error": "authorization_pending"}'
    pending_resp.json.return_value = {"error": "authorization_pending"}

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.text = '{"access_token": "acc_123"}'
    success_resp.json.return_value = {
        "access_token": "acc_123",
        "refresh_token": "ref_456",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("bard.oauth.requests.post", side_effect=[pending_resp, success_resp]) as mock_post:
        with patch("bard.oauth.time.sleep") as mock_sleep:
            result = oauth.poll_for_token("dev123", interval=2, timeout=60)
            assert result is not None
            assert result["access_token"] == "acc_123"
            assert result["refresh_token"] == "ref_456"
            assert oauth.is_authenticated()
            assert mock_sleep.called


def test_oauth_poll_for_token_terminal_error(tmp_path: Path):
    token_file = tmp_path / "oauth.json"
    oauth = YTMusicOAuth(token_path=token_file)

    denied_resp = MagicMock()
    denied_resp.status_code = 400
    denied_resp.text = '{"error": "access_denied"}'
    denied_resp.json.return_value = {"error": "access_denied"}

    with patch("bard.oauth.requests.post", return_value=denied_resp):
        result = oauth.poll_for_token("dev123", interval=1, timeout=10)
        assert result is None
        assert not oauth.is_authenticated()


def test_bard_config_oauth_integration(tmp_path: Path):
    config_file = tmp_path / "config.json"
    cfg = BardConfig(config_path=config_file)

    assert cfg.oauth_path == tmp_path / "oauth.json"
    assert not cfg.is_authenticated()

    # Test saving custom ytmusic client credentials
    cfg.ytmusic_client_id = "custom_id"
    cfg.ytmusic_client_secret = "custom_secret"
    cfg.save()

    reloaded = BardConfig(config_path=config_file)
    assert reloaded.ytmusic_client_id == "custom_id"
    assert reloaded.ytmusic_client_secret == "custom_secret"

    oauth = YTMusicOAuth(config=reloaded)
    assert oauth.client_id == "custom_id"
    assert oauth.client_secret == "custom_secret"
    assert oauth.token_path == tmp_path / "oauth.json"

    oauth.save_tokens({"access_token": "tok_xyz", "refresh_token": "ref_xyz"})
    assert reloaded.is_authenticated()
