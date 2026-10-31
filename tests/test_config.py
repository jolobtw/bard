"""Test configuration and credential storage."""

import json
from pathlib import Path
from bard.config import BardConfig


def test_config_load_and_save(tmp_path: Path):
    config_file = tmp_path / "config.json"
    cfg = BardConfig(config_path=config_file)
    
    assert cfg.client_id == ""
    assert cfg.redirect_uri == "http://127.0.0.1:8888/callback"
    assert cfg.device_name == "Bard"
    
    cfg.client_id = "test_client_id_123"
    cfg.set_tokens(access_token="acc_123", refresh_token="ref_456", expires_in=3600)
    cfg.save()
    
    # Reload from disk
    loaded = BardConfig(config_path=config_file)
    assert loaded.client_id == "test_client_id_123"
    assert loaded.access_token == "acc_123"
    assert loaded.refresh_token == "ref_456"
