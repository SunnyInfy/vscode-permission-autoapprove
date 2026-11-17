"""OCR fallback: finds approval buttons in a screenshot when accessibility cannot see them.

Only the pure parsing helpers are unit-tested; screen capture and Tesseract are imported lazily.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .classifier import PermissionClassifier
from .config import AppConfig
from .detector import TargetWindow
from .models import Button, DialogSnapshot

OCR_SCALE = 2
MAX_BUTTON_WORDS = 6
MAX_BUTTON_CHARS = 40
ROW_TOLERANCE_PX = 12  # buttons of one dialog sit on the same visual row
DIALOG_CONTEXT_PX = 300  # vertical distance used to collect the dialog body text


@dataclass(frozen=True)
class OcrWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    line_key: tuple[int, int, int]


@dataclass(frozen=True)
class _Line:
    text: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


def words_from_tesseract(data: dict[str, Any], scale: float = 1.0) -> list[OcrWord]:
    """Convert pytesseract's DICT output into OcrWords in original (unscaled) pixels."""
    words: list[OcrWord] = []
    for i, raw in enumerate(data.get("text", [])):
        text = str(raw).strip()
        confidence = float(data["conf"][i])
        if not text or confidence < 0:
            continue
        words.append(
            OcrWord(
                text=text,
                left=int(data["left"][i] / scale),
                top=int(data["top"][i] / scale),
                width=int(data["width"][i] / scale),
                height=int(data["height"][i] / scale),
                confidence=confidence,
                line_key=(data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            )
        )
    return words


def group_lines(words: Iterable[OcrWord]) -> list[list[OcrWord]]:
    lines: dict[tuple[int, int, int], list[OcrWord]] = {}
    for word in words:
        lines.setdefault(word.line_key, []).append(word)
    return list(lines.values())


def build_snapshots(
    words: Iterable[OcrWord],
    *,
    approve_matcher: Callable[[str], bool],
    min_confidence: float,
    origin: tuple[int, int],
    app_name: str,
    title: str,
    context_px: int = DIALOG_CONTEXT_PX,
) -> list[DialogSnapshot]:
    """Build one snapshot per approve-looking line.

    Buttons are the short lines on the same visual row as the candidate; dialog text is
    every line within ``context_px`` vertically, so distant editor text is excluded.
    """
    lines = _to_lines([w for w in words if w.confidence >= min_confidence])
    snapshots: list[DialogSnapshot] = []
    for candidate in lines:
        if not _is_button_like(candidate.text) or not approve_matcher(candidate.text):
            continue
        row = [line for line in lines if abs(line.center_y - candidate.center_y) <= ROW_TOLERANCE_PX]
        band = [line for line in lines if abs(line.center_y - candidate.center_y) <= context_px]
        buttons = tuple(
            Button(
                label=line.text,
                center=(origin[0] + (line.left + line.right) // 2, origin[1] + (line.top + line.bottom) // 2),
                source="ocr",
            )
            for line in row
            if _is_button_like(line.text)
        )
        snapshots.append(
            DialogSnapshot(
                app_name=app_name,
                window_title=title,
                dialog_text=" ".join(line.text for line in band),
                buttons=buttons,
                source="ocr",
                is_native_dialog=False,
            )
        )
    return snapshots


def _to_lines(words: list[OcrWord]) -> list[_Line]:
    lines: list[_Line] = []
    for group in group_lines(words):
        lines.append(
            _Line(
                text=" ".join(w.text for w in group),
                left=min(w.left for w in group),
                top=min(w.top for w in group),
                right=max(w.left + w.width for w in group),
                bottom=max(w.top + w.height for w in group),
            )
        )
    return lines


def _is_button_like(text: str) -> bool:
    return 0 < len(text) <= MAX_BUTTON_CHARS and len(text.split()) <= MAX_BUTTON_WORDS


class OcrDetector:
    def __init__(self, config: AppConfig, classifier: PermissionClassifier) -> None:
        self._config = config
        self._classifier = classifier

    def snapshots(self, targets: list[TargetWindow]) -> list[DialogSnapshot]:
        result: list[DialogSnapshot] = []
        for target in targets:
            result.extend(self._capture(target))
        return result

    def _capture(self, target: TargetWindow) -> list[DialogSnapshot]:
        import cv2
        import numpy as np
        import pyautogui
        import pytesseract

        if self._config.ocr.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._config.ocr.tesseract_cmd

        rect = target.wrapper.rectangle()
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return []

        shot = pyautogui.screenshot(region=(rect.left, rect.top, width, height))
        gray = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=OCR_SCALE, fy=OCR_SCALE, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        if binary.mean() < 127:  # dark theme: Tesseract wants dark text on a light background
            binary = cv2.bitwise_not(binary)

        data = pytesseract.image_to_data(binary, output_type=pytesseract.Output.DICT)
        return build_snapshots(
            words_from_tesseract(data, scale=OCR_SCALE),
            approve_matcher=self._classifier.is_approve_label,
            min_confidence=self._config.ocr.min_confidence,
            origin=(rect.left, rect.top),
            app_name=target.app_name,
            title=target.title,
        )
