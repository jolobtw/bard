"""Test main BardApp creation and bindings."""

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
