"""Dialog Detector (accessibility path): Windows UI Automation via pywinauto.

pywinauto and psutil are imported lazily so the module can be imported (and tested) anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .classifier import PermissionClassifier
from .config import AppConfig
from .models import Button, DialogSnapshot

MAX_CONTAINER_BUTTONS = 8
MAX_CONTAINER_TEXTS = 20


@dataclass(frozen=True)
class TargetWindow:
    app_name: str
    title: str
    wrapper: Any


class UiaDialogDetector:
    def __init__(self, config: AppConfig, classifier: PermissionClassifier) -> None:
        self._config = config
        self._classifier = classifier
        self._targets = {name.lower() for name in config.target_processes}

    def find_target_windows(self) -> list[TargetWindow]:
        import psutil
        from pywinauto import Desktop

        targets: list[TargetWindow] = []
        for window in Desktop(backend="uia").windows():
            try:
                app_name = psutil.Process(window.process_id()).name()
                title = window.window_text()
            except Exception:  # window closed mid-enumeration or inaccessible
                continue
            if app_name.lower() in self._targets:
                targets.append(TargetWindow(app_name, title, window))
        return targets

    def snapshots(self, targets: list[TargetWindow]) -> list[DialogSnapshot]:
        result: list[DialogSnapshot] = []
        for target in targets:
            result.extend(self._scan_window(target))
        return result

    def _scan_window(self, target: TargetWindow) -> list[DialogSnapshot]:
        window = target.wrapper
        candidates = [b for b in window.descendants(control_type="Button") if self._is_approve_candidate(b)]

        snapshots: list[DialogSnapshot] = []
        seen: set[tuple[int, int, int, int]] = set()
        for button in candidates:
            container, is_dialog = self._find_container(button, window)
            if container is None:
                continue
            key = _rect_key(container)
            if key in seen:
                continue
            seen.add(key)
            snapshots.append(self._snapshot(container, is_dialog, target))
        return snapshots

    def _is_approve_candidate(self, button: Any) -> bool:
        label = _safe_text(button)
        return bool(label) and self._classifier.is_approve_label(label) and _is_actionable(button)

    def _find_container(self, button: Any, window: Any) -> tuple[Any | None, bool]:
        """Nearest small group (or Dialog) around the button; None if no bounded group exists."""
        node = button
        for _ in range(self._config.context_depth):
            parent = node.parent()
            if parent is None:
                break
            if _control_type(parent) == "Window":
                # Only a button placed directly in its top-level window may use that window as scope.
                return (window, False) if node is button else (None, False)
            node = parent
            if _control_type(node) == "Dialog":
                return node, True
            if _is_compact(node):
                return node, False
        return None, False

    def _snapshot(self, container: Any, is_dialog: bool, target: TargetWindow) -> DialogSnapshot:
        buttons: list[Button] = []
        for child in container.descendants(control_type="Button"):
            label = _safe_text(child)
            if label and _is_actionable(child):
                buttons.append(Button(label=label, center=_center(child), source="uia", ref=child))

        texts = [_safe_text(child) for child in container.descendants(control_type="Text")]
        return DialogSnapshot(
            app_name=target.app_name,
            window_title=target.title,
            dialog_text=" ".join(t for t in texts if t),
            buttons=tuple(buttons),
            source="uia",
            is_native_dialog=is_dialog,
            context_label=_safe_text(container),
        )


def _is_compact(element: Any) -> bool:
    """A small group holding the approve button plus at least one sibling control."""
    buttons = element.descendants(control_type="Button")
    texts = element.descendants(control_type="Text")
    return 2 <= len(buttons) <= MAX_CONTAINER_BUTTONS and len(texts) <= MAX_CONTAINER_TEXTS


def _safe_text(element: Any) -> str:
    try:
        return element.window_text().strip()
    except Exception:
        return ""


def _control_type(element: Any) -> str:
    try:
        return element.element_info.control_type
    except Exception:
        return ""


def _is_actionable(element: Any) -> bool:
    try:
        return bool(element.is_visible() and element.is_enabled())
    except Exception:
        return False


def _rect_key(element: Any) -> tuple[int, int, int, int]:
    rect = element.rectangle()
    return (rect.left, rect.top, rect.right, rect.bottom)


def _center(element: Any) -> tuple[int, int]:
    rect = element.rectangle()
    return ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
