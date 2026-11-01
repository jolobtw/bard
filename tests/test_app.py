"""Test main BardApp creation and bindings."""

import asyncio
from unittest.mock import MagicMock
from bard.config import BardConfig
from bard.ui.app import BardApp


def test_bard_app_instantiation(tmp_path):
    cfg = BardConfig(config_path=tmp_path / "config.json")
    mock_client = MagicMock()
    app = BardApp(cfg, mock_client)
    
    # Verify binding keys exist
    keys = [b.key for b in app.BINDINGS]
    assert "space" in keys
    assert "tab" in keys
    assert "escape" in keys
    assert "n" in keys
    assert "p" in keys
    assert "q" in keys


def test_app_rate_limited_skips_sync(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.is_rate_limited.return_value = True
        app = BardApp(cfg, mock_client)
        async with app.run_test():
            app.sync_playback_state()
            await asyncio.sleep(0.05)
            mock_client.get_playback.assert_not_called()

            app.locate_bard_device()
            await asyncio.sleep(0.05)
            mock_client.get_devices.assert_not_called()

    asyncio.run(_run())


def test_locate_bard_device_strictly_excludes_tv(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.is_rate_limited.return_value = False
        mock_client.get_playback.return_value = None
        mock_client.get_devices.return_value = [
            {"id": "tv_1", "name": "Living Room TV", "type": "TV", "is_active": True},
            {"id": "cast_1", "name": "Bedroom Chromecast", "type": "CastVideo", "is_active": False},
        ]
        app = BardApp(cfg, mock_client)
        async with app.run_test():
            app.locate_bard_device()
            await asyncio.sleep(0.05)
            # Must be None - must NEVER bind to TV or Cast
            assert app.bard_device_id is None
            mock_client.transfer_playback.assert_not_called()

    asyncio.run(_run())


def test_locate_bard_device_selects_computer_over_tv(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.is_rate_limited.return_value = False
        mock_client.get_playback.return_value = None
        mock_client.get_devices.return_value = [
            {"id": "tv_1", "name": "Living Room TV", "type": "TV", "is_active": True},
            {"id": "comp_1", "name": "Joey's MacBook", "type": "Computer", "is_active": False},
        ]
        app = BardApp(cfg, mock_client)
        async with app.run_test():
            app.locate_bard_device()
            await asyncio.sleep(0.05)
            assert app.bard_device_id == "comp_1"
            mock_client.transfer_playback.assert_called_with("comp_1", play=False)

    asyncio.run(_run())


def test_action_toggle_playback_does_not_call_play_without_local_device(tmp_path):
    async def _run():
        cfg = BardConfig(config_path=tmp_path / "config.json")
        mock_client = MagicMock()
        mock_client.is_rate_limited.return_value = False
        mock_client.get_playback.return_value = None
        # Only TV available
        mock_client.get_devices.return_value = [
            {"id": "tv_1", "name": "Living Room TV", "type": "TV", "is_active": True},
        ]
        app = BardApp(cfg, mock_client)
        async with app.run_test():
            app.action_toggle_playback()
            await asyncio.sleep(0.05)
            # Must NOT call play on TV or play(device_id=None)
            mock_client.play.assert_not_called()

    asyncio.run(_run())




