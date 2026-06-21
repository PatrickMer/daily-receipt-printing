"""Tests for core.config — config loading and secret validation."""

from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest
import yaml

from core.config import load_receipt_config, load_system_config, validate_secrets
from widgets.widget import Widget

# ---------------------------------------------------------------------------
# load_system_config tests
# ---------------------------------------------------------------------------


class TestLoadSystemConfig:
    """Tests for load_system_config."""

    def test_valid_yaml(self, tmp_path: Any) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "printer:\n  host: '192.168.0.100'\n  port: 9100\nlogging:\n  level: DEBUG\n"
        )
        result = load_system_config(config_file)
        assert result["printer"]["host"] == "192.168.0.100"
        assert result["printer"]["port"] == 9100
        assert result["logging"]["level"] == "DEBUG"

    def test_missing_file(self, tmp_path: Any) -> None:
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="System config file not found"):
            load_system_config(missing)

    def test_malformed_yaml(self, tmp_path: Any) -> None:
        config_file = tmp_path / "bad.yaml"
        # Write content that parses to a non-dict value (edge case).
        # PyYAML doesn't typically raise on most content, but tabs in wrong
        # places or certain patterns will. Use a deliberately broken structure.
        config_file.write_text(":\n  - :\n    : [}")
        with pytest.raises(yaml.YAMLError):
            load_system_config(config_file)

    def test_returns_dict(self, tmp_path: Any) -> None:
        config_file = tmp_path / "simple.yaml"
        config_file.write_text("key: value\n")
        result = load_system_config(config_file)
        assert isinstance(result, dict)
        assert result["key"] == "value"


# ---------------------------------------------------------------------------
# load_receipt_config tests
# ---------------------------------------------------------------------------


class TestLoadReceiptConfig:
    """Tests for load_receipt_config."""

    def test_valid_json(self, tmp_path: Any) -> None:
        receipt_file = tmp_path / "morning.json"
        data = {
            "receipt": {
                "name": "morning",
                "layout": {"header": True},
                "widgets": [{"type": "weather", "params": {"location": "madrid"}}],
            }
        }
        receipt_file.write_text(json.dumps(data))
        result = load_receipt_config(receipt_file)
        assert result["receipt"]["name"] == "morning"
        assert len(result["receipt"]["widgets"]) == 1

    def test_missing_file(self, tmp_path: Any) -> None:
        missing = tmp_path / "missing.json"
        with pytest.raises(FileNotFoundError, match="Receipt config file not found"):
            load_receipt_config(missing)

    def test_invalid_json(self, tmp_path: Any) -> None:
        bad_file = tmp_path / "broken.json"
        bad_file.write_text("{not valid json at all")
        with pytest.raises(ValueError, match="Invalid JSON in receipt config"):
            load_receipt_config(bad_file)

    def test_empty_json_object(self, tmp_path: Any) -> None:
        receipt_file = tmp_path / "empty.json"
        receipt_file.write_text("{}")
        result = load_receipt_config(receipt_file)
        assert result == {}


# ---------------------------------------------------------------------------
# validate_secrets tests
# ---------------------------------------------------------------------------


class _FakeWidgetWithSecrets(Widget):
    """Test widget that requires secrets."""

    widget_type: ClassVar[str] = "__test_config_secrets__"
    required_secrets: ClassVar[list[str]] = ["SECRET_A", "SECRET_B"]

    def render(self, params: dict[str, Any], context: Any) -> list[Any]:
        return []


class _FakeWidgetNoSecrets(Widget):
    """Test widget with no required secrets."""

    widget_type: ClassVar[str] = "__test_config_no_secrets__"
    required_secrets: ClassVar[list[str]] = []

    def render(self, params: dict[str, Any], context: Any) -> list[Any]:
        return []


class TestValidateSecrets:
    """Tests for validate_secrets."""

    def test_all_secrets_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECRET_A", "value_a")
        monkeypatch.setenv("SECRET_B", "value_b")
        receipt_config = {
            "receipt": {"widgets": [{"type": "__test_config_secrets__", "params": {}}]}
        }
        # Should not raise.
        validate_secrets(receipt_config)

    def test_missing_secrets_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SECRET_A", raising=False)
        monkeypatch.delenv("SECRET_B", raising=False)
        receipt_config = {
            "receipt": {"widgets": [{"type": "__test_config_secrets__", "params": {}}]}
        }
        with pytest.raises(OSError, match="SECRET_A"):
            validate_secrets(receipt_config)
        with pytest.raises(OSError, match="SECRET_B"):
            validate_secrets(receipt_config)

    def test_partial_secrets_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECRET_A", "present")
        monkeypatch.delenv("SECRET_B", raising=False)
        receipt_config = {
            "receipt": {"widgets": [{"type": "__test_config_secrets__", "params": {}}]}
        }
        with pytest.raises(OSError, match="SECRET_B"):
            validate_secrets(receipt_config)

    def test_widget_not_in_registry(self) -> None:
        receipt_config = {
            "receipt": {
                "widgets": [{"type": "__nonexistent_widget_type__", "params": {}}]
            }
        }
        with pytest.raises(KeyError):
            validate_secrets(receipt_config)

    def test_widget_with_no_required_secrets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        receipt_config = {
            "receipt": {
                "widgets": [{"type": "__test_config_no_secrets__", "params": {}}]
            }
        }
        # Should not raise even without any secrets in env.
        validate_secrets(receipt_config)

    def test_empty_widgets_list(self) -> None:
        receipt_config: dict[str, Any] = {"receipt": {"widgets": []}}
        # Should not raise.
        validate_secrets(receipt_config)

    def test_missing_receipt_key(self) -> None:
        receipt_config: dict[str, Any] = {}
        # Should not raise — gracefully handles missing keys.
        validate_secrets(receipt_config)

    def test_duplicate_secrets_reported_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If two widgets need the same secret, it's reported only once."""
        monkeypatch.delenv("SECRET_A", raising=False)
        monkeypatch.delenv("SECRET_B", raising=False)
        receipt_config = {
            "receipt": {
                "widgets": [
                    {"type": "__test_config_secrets__", "params": {}},
                    {"type": "__test_config_secrets__", "params": {}},
                ]
            }
        }
        with pytest.raises(OSError, match="SECRET_A") as exc_info:
            validate_secrets(receipt_config)
        # Ensure SECRET_A appears only once in the message.
        msg = str(exc_info.value)
        assert msg.count("SECRET_A") == 1
