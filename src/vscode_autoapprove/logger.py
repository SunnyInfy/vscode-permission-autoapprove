"""Activity Logger: append-only JSON Lines record of every approval action."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_DIALOG_TEXT = 500


class ActivityLogger:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        *,
        outcome: str,
        app: str,
        window_title: str,
        dialog_text: str,
        button: str,
        source: str,
        reason: str = "",
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "outcome": outcome,
            "app": app,
            "window_title": window_title,
            "dialog_text": " ".join(dialog_text.split())[:MAX_DIALOG_TEXT],
            "button": button,
            "source": source,
            "reason": reason,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def recent(self, count: int = 20) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-count:] if line.strip()]
