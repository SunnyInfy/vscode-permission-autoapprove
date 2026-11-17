"""Data structures shared by the detectors, classifier and click engine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Button:
    """A clickable control. ``ref`` holds the UIA wrapper for UIA-sourced buttons."""

    label: str
    center: tuple[int, int] | None = None
    source: str = "uia"
    ref: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class DialogSnapshot:
    app_name: str
    window_title: str
    dialog_text: str
    buttons: tuple[Button, ...]
    source: str
    is_native_dialog: bool = False
    context_label: str = ""

    @property
    def fingerprint(self) -> str:
        key = "\n".join([self.app_name, self.dialog_text, *sorted(b.label for b in self.buttons)])
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Decision:
    approve: bool
    reason: str
    button: Button | None = None
