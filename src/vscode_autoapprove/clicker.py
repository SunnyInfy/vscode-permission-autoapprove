"""Auto Click Engine: applies safety gates (dry-run, cooldown, rate limit) before acting."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .config import AppConfig
from .logger import ActivityLogger
from .models import Button, Decision, DialogSnapshot

logger = logging.getLogger(__name__)

Performer = Callable[[Button], None]


@dataclass(frozen=True)
class ClickResult:
    outcome: str  # clicked | dry_run | cooldown | rate_limited | error
    button_label: str


def perform_click(button: Button) -> None:
    """Invoke via UI Automation when possible; otherwise fall back to a real mouse click."""
    if button.source == "uia" and button.ref is not None:
        try:
            button.ref.invoke()
            return
        except Exception:  # InvokePattern not supported by this control
            logger.debug("Invoke failed for '%s'; using mouse click", button.label)
        button.ref.click_input()
        return

    if button.center is None:
        raise RuntimeError(f"Button '{button.label}' has no screen position")
    import pyautogui

    pyautogui.click(*button.center)


class AutoClickEngine:
    def __init__(
        self,
        config: AppConfig,
        activity_logger: ActivityLogger,
        performer: Performer | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._log = activity_logger
        self._performer = performer or perform_click
        self._clock = clock
        self._recent: deque[float] = deque()
        self._last_action: dict[str, float] = {}

    def handle(self, snapshot: DialogSnapshot, decision: Decision) -> ClickResult:
        if decision.button is None:
            raise ValueError("An approving decision must carry a button")
        button = decision.button
        now = self._clock()
        self._prune(now)

        last = self._last_action.get(snapshot.fingerprint)
        if last is not None and now - last < self._config.cooldown_seconds:
            return ClickResult("cooldown", button.label)
        if len(self._recent) >= self._config.max_clicks_per_minute:
            return ClickResult("rate_limited", button.label)

        self._last_action[snapshot.fingerprint] = now
        reason = decision.reason
        if self._config.dry_run:
            outcome = "dry_run"
        else:
            try:
                self._performer(button)
                outcome = "clicked"
                self._recent.append(now)
                logger.info("Approved '%s' in %s", button.label, snapshot.app_name)
            except Exception as exc:
                outcome = "error"
                reason = f"{reason}; click failed: {exc}"
                logger.exception("Click on '%s' failed", button.label)

        self._log.record(
            outcome=outcome,
            app=snapshot.app_name,
            window_title=snapshot.window_title,
            dialog_text=snapshot.dialog_text,
            button=button.label,
            source=snapshot.source,
            reason=reason,
        )
        return ClickResult(outcome, button.label)

    def _prune(self, now: float) -> None:
        while self._recent and now - self._recent[0] >= 60:
            self._recent.popleft()
        expired = [key for key, ts in self._last_action.items() if now - ts >= self._config.cooldown_seconds]
        for key in expired:
            del self._last_action[key]
