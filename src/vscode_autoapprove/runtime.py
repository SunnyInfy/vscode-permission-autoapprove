"""Runtime wiring: builds the monitor, enforces a single instance, and runs the poll loop."""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import psutil

from .classifier import PermissionClassifier
from .clicker import AutoClickEngine
from .config import AppConfig, ConfigError, ConfigManager
from .detector import UiaDialogDetector
from .logger import ActivityLogger
from .monitor import Monitor
from .ocr_fallback import OcrDetector

logger = logging.getLogger(__name__)


def build_monitor(config: AppConfig, activity_logger: ActivityLogger, is_enabled: Callable[[], bool]) -> Monitor:
    classifier = PermissionClassifier(config)
    return Monitor(
        classifier=classifier,
        detector=UiaDialogDetector(config, classifier),
        engine=AutoClickEngine(config, activity_logger),
        is_enabled=is_enabled,
        ocr=OcrDetector(config, classifier) if config.ocr.enabled else None,
        ocr_interval_seconds=config.ocr.interval_seconds,
    )


def enabled_checker(manager: ConfigManager, initial: bool) -> Callable[[], bool]:
    """Re-reads the config file on every poll so `disable` takes effect without a restart."""
    state = {"enabled": initial}

    def is_enabled() -> bool:
        try:
            state["enabled"] = manager.load().enabled
        except (ConfigError, OSError) as exc:
            logger.warning("Keeping previous enabled state; config unreadable: %s", exc)
        return state["enabled"]

    return is_enabled


def run_forever(monitor: Monitor, poll_seconds: float) -> None:
    while True:
        try:
            monitor.run_once()
        except Exception:  # keep the watcher alive through transient UIA errors
            logger.exception("Monitor iteration failed; continuing")
        time.sleep(poll_seconds)


def enable_dpi_awareness() -> None:
    """Use physical pixels so UIA rectangles and pyautogui coordinates agree on scaled displays."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        pass


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._held = False

    def acquire(self) -> bool:
        if self._path.exists():
            try:
                owner = int(self._path.read_text(encoding="utf-8").strip())
            except ValueError:
                owner = 0
            if owner and owner != os.getpid() and psutil.pid_exists(owner):
                return False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(str(os.getpid()), encoding="utf-8")
        self._held = True
        return True

    def release(self) -> None:
        if self._held and self._path.exists():
            self._path.unlink()
        self._held = False
