"""Configuration loading, validation and persistence (Configuration Manager)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

APP_DIR_NAME = "vscode-autoapprove"
CONFIG_FILE_NAME = "config.json"
LOG_FILE_NAME = "activity.jsonl"
LOCK_FILE_NAME = "run.lock"

DEFAULT_APPROVE_LABELS = (
    "Allow", "Approve", "Continue", "Trust", "Yes", "Grant Access", "Accept", "Confirm", "OK",
)
DEFAULT_DESTRUCTIVE_KEYWORDS = ("Delete", "Remove", "Revoke", "Reset", "Uninstall", "Reject")
DEFAULT_NEGATION_MARKERS = ("No", "Not", "Don't", "Do not", "Cancel", "Deny", "Denied", "Restricted")
DEFAULT_DISMISS_LABELS = (
    "Cancel", "Deny", "Don't Allow", "Do Not Allow", "Not Now", "No", "Skip", "Close", "Dismiss", "Later",
    "Restricted Mode",
)
DEFAULT_TERMINAL_MARKERS = ("Run in terminal",)
DEFAULT_READ_ONLY_COMMANDS = (
    "cd", "Set-Location", "Get-Location", "Get-ChildItem", "dir", "ls", "Get-Content", "cat", "type",
    "Get-Item", "Test-Path", "Import-Csv", "Select-Object", "Where-Object", "Sort-Object", "Group-Object",
    "Measure-Object", "Format-Table", "Format-List", "Out-String", "Write-Output", "echo", "Get-Date",
)
_LIST_FIELDS = frozenset(
    {
        "target_processes", "approve_labels", "destructive_keywords", "negation_markers", "dismiss_labels",
        "terminal_markers", "terminal_read_only_commands",
    }
)


class ConfigError(ValueError):
    """The configuration file is malformed or holds an invalid value."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _string_tuple(name: str, value: Any) -> tuple[str, ...]:
    _check(
        isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
        f"'{name}' must be a list of non-empty strings",
    )
    return tuple(value)


def _reject_unknown(data: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = sorted(set(data) - allowed)
    _check(not unknown, f"Unknown {section} key(s): {', '.join(unknown)}")


@dataclass(frozen=True)
class OcrConfig:
    enabled: bool = False
    interval_seconds: float = 3.0
    min_confidence: float = 60.0
    tesseract_cmd: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> OcrConfig:
        _check(isinstance(data, dict), "'ocr' must be an object")
        _reject_unknown(data, {f.name for f in fields(cls)}, "ocr")
        config = cls(**data)
        config.validate()
        return config

    def validate(self) -> None:
        _check(isinstance(self.enabled, bool), "'ocr.enabled' must be true or false")
        _check(
            _is_number(self.interval_seconds) and self.interval_seconds > 0,
            "'ocr.interval_seconds' must be a positive number",
        )
        _check(
            _is_number(self.min_confidence) and 0 <= self.min_confidence <= 100,
            "'ocr.min_confidence' must be between 0 and 100",
        )
        _check(isinstance(self.tesseract_cmd, str), "'ocr.tesseract_cmd' must be a string")


@dataclass(frozen=True)
class AppConfig:
    enabled: bool = True
    dry_run: bool = False
    target_processes: tuple[str, ...] = ("Code.exe",)
    poll_interval_seconds: float = 1.0
    approve_labels: tuple[str, ...] = DEFAULT_APPROVE_LABELS
    destructive_keywords: tuple[str, ...] = DEFAULT_DESTRUCTIVE_KEYWORDS
    negation_markers: tuple[str, ...] = DEFAULT_NEGATION_MARKERS
    dismiss_labels: tuple[str, ...] = DEFAULT_DISMISS_LABELS
    terminal_markers: tuple[str, ...] = DEFAULT_TERMINAL_MARKERS
    terminal_read_only_commands: tuple[str, ...] = DEFAULT_READ_ONLY_COMMANDS
    require_dialog_context: bool = True
    context_depth: int = 3
    max_clicks_per_minute: int = 6
    cooldown_seconds: float = 10.0
    ocr: OcrConfig = field(default_factory=OcrConfig)

    @classmethod
    def from_dict(cls, data: Any) -> AppConfig:
        """Build a config from a (possibly partial) mapping; omitted keys take defaults."""
        _check(isinstance(data, dict), "Configuration must be a JSON object")
        _reject_unknown(data, {f.name for f in fields(cls)}, "config")
        values: dict[str, Any] = {}
        for key, value in data.items():
            if key == "ocr":
                values[key] = OcrConfig.from_dict(value)
            elif key in _LIST_FIELDS:
                values[key] = _string_tuple(key, value)
            else:
                values[key] = value
        config = cls(**values)
        config.validate()
        return config

    def validate(self) -> None:
        for name in ("enabled", "dry_run", "require_dialog_context"):
            _check(isinstance(getattr(self, name), bool), f"'{name}' must be true or false")
        _check(
            _is_number(self.poll_interval_seconds) and self.poll_interval_seconds > 0,
            "'poll_interval_seconds' must be a positive number",
        )
        _check(_is_int(self.context_depth) and self.context_depth >= 1, "'context_depth' must be an integer >= 1")
        _check(
            _is_int(self.max_clicks_per_minute) and self.max_clicks_per_minute >= 1,
            "'max_clicks_per_minute' must be an integer >= 1",
        )
        _check(
            _is_number(self.cooldown_seconds) and self.cooldown_seconds >= 0,
            "'cooldown_seconds' must be a number >= 0",
        )
        _check(bool(self.target_processes), "'target_processes' must not be empty")
        _check(bool(self.approve_labels), "'approve_labels' must not be empty")
        _check(bool(self.terminal_markers), "'terminal_markers' must not be empty")
        self.ocr.validate()


def default_app_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / APP_DIR_NAME


def default_config_path() -> Path:
    return default_app_dir() / CONFIG_FILE_NAME


def default_log_path() -> Path:
    return default_app_dir() / LOG_FILE_NAME


def default_lock_path() -> Path:
    return default_app_dir() / LOCK_FILE_NAME


class ConfigManager:
    """Reads and writes the JSON config file under %APPDATA%\\vscode-autoapprove by default."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        return AppConfig.from_dict(self._read_raw())

    def init(self) -> bool:
        """Write a minimal config if no file exists. Returns True when a file was created."""
        if self.path.exists():
            return False
        self._write({"enabled": True, "dry_run": False})
        return True

    def set_enabled(self, enabled: bool) -> None:
        raw = self._read_raw() if self.path.exists() else {}
        raw["enabled"] = enabled
        AppConfig.from_dict(raw)  # validate before touching the file
        self._write(raw)

    def _read_raw(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))  # tolerate BOM from Windows editors
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{self.path} is not valid JSON: {exc}") from exc
        _check(isinstance(raw, dict), f"{self.path} must contain a JSON object")
        return raw

    def _write(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
