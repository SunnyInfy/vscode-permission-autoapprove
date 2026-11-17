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


def build_monitor(
    config: AppConfig,
    activity_logger: ActivityLogger,
    is_enabled: Callable[[], bool],
    is_unrestricted: Callable[[], bool] | None = None,
) -> Monitor:
    classifier = PermissionClassifier(config, unrestricted=is_unrestricted or (lambda: False))
    return Monitor(
        classifier=classifier,
        detector=UiaDialogDetector(config, classifier),
        engine=AutoClickEngine(config, activity_logger),
        is_enabled=is_enabled,
        ocr=OcrDetector(config, classifier) if config.ocr.enabled else None,
        ocr_interval_seconds=config.ocr.interval_seconds,
    )


def flag_checker(manager: ConfigManager, key: str, initial: bool) -> Callable[[], bool]:
    """Re-reads one flag from the config file on every poll so changes apply without a restart."""
    state = {"value": initial}

    def check() -> bool:
        try:
            state["value"] = getattr(manager.load(), key)
        except (ConfigError, OSError) as exc:
            logger.warning("Keeping previous '%s' value; config unreadable: %s", key, exc)
        return state["value"]

    return check


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


def is_watcher_running(path: Path) -> bool:
    """True when the lock file names a live process other than this one."""
    try:
        owner = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return owner != os.getpid() and psutil.pid_exists(owner)


class SingleInstanceLock:
    """Exclusive lock file; a lock left behind by a dead process is replaced."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._held = False

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if is_watcher_running(self._path):
                    return False
                self._path.unlink(missing_ok=True)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            self._held = True
            return True
        return False

    def release(self) -> None:
        if self._held:
            self._path.unlink(missing_ok=True)
        self._held = False
