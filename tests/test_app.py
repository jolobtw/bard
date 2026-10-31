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



