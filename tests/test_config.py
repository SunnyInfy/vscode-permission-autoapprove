import json

import pytest

from vscode_autoapprove.config import AppConfig, ConfigError, ConfigManager


def test_missing_file_uses_defaults(tmp_path):
    manager = ConfigManager(tmp_path / "config.json")

    config = manager.load()

    assert config == AppConfig()
    assert "Allow" in config.approve_labels


def test_partial_file_overrides_only_given_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"cooldown_seconds": 30, "approve_labels": ["Allow"]}), encoding="utf-8")

    config = ConfigManager(path).load()

    assert config.cooldown_seconds == 30
    assert config.approve_labels == ("Allow",)
    assert config.max_clicks_per_minute == AppConfig().max_clicks_per_minute


@pytest.mark.parametrize(
    "payload",
    [
        {"max_clicks_per_minute": 0},
        {"enabled": "yes"},
        {"approve_labels": []},
        {"not_a_real_key": 1},
        {"ocr": {"min_confidence": 150}},
    ],
)
def test_invalid_values_are_rejected(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigError):
        ConfigManager(path).load()


def test_file_saved_with_utf8_bom_is_accepted(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'{"cooldown_seconds": 7}')

    assert ConfigManager(path).load().cooldown_seconds == 7


def test_set_enabled_preserves_user_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"cooldown_seconds": 42}), encoding="utf-8")
    manager = ConfigManager(path)

    manager.set_enabled(False)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw == {"cooldown_seconds": 42, "enabled": False}
    assert manager.load().enabled is False
