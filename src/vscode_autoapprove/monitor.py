"""Monitor: one polling iteration = find VS Code windows, classify dialogs, act on approvals."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .classifier import PermissionClassifier
from .clicker import AutoClickEngine, ClickResult
from .models import DialogSnapshot


class Monitor:
    def __init__(
        self,
        *,
        classifier: PermissionClassifier,
        detector: Any,
        engine: AutoClickEngine,
        is_enabled: Callable[[], bool],
        ocr: Any | None = None,
        ocr_interval_seconds: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._classifier = classifier
        self._detector = detector
        self._engine = engine
        self._is_enabled = is_enabled
        self._ocr = ocr
        self._ocr_interval = ocr_interval_seconds
        self._clock = clock
        self._last_ocr: float | None = None

    def run_once(self) -> list[ClickResult]:
        if not self._is_enabled():
            return []
        targets = self._detector.find_target_windows()
        if not targets:
            return []

        approved, results = self._act_on(self._detector.snapshots(targets))

        # OCR is a fallback: only when accessibility produced no approvable dialog.
        if approved == 0 and self._ocr is not None and self._ocr_due():
            _, ocr_results = self._act_on(self._ocr.snapshots(targets))
            results.extend(ocr_results)
        return results

    def _act_on(self, snapshots: list[DialogSnapshot]) -> tuple[int, list[ClickResult]]:
        approved = 0
        results: list[ClickResult] = []
        for snapshot in snapshots:
            decision = self._classifier.classify(snapshot)
            if not decision.approve:
                continue
            approved += 1
            results.append(self._engine.handle(snapshot, decision))
        return approved, results

    def _ocr_due(self) -> bool:
        now = self._clock()
        if self._last_ocr is not None and now - self._last_ocr < self._ocr_interval:
            return False
        self._last_ocr = now
        return True
