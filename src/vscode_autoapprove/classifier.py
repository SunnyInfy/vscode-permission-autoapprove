"""Permission Classifier: decides whether a dialog is a safe prompt and which button to press."""

from __future__ import annotations

import re

from .command_policy import is_read_only_command
from .config import AppConfig
from .models import Button, Decision, DialogSnapshot

_APOSTROPHES = str.maketrans({"\u2018": "'", "\u2019": "'"})


def normalize_label(text: str) -> str:
    """Strip accelerator marks, trailing ellipses and extra whitespace; unify apostrophes."""
    cleaned = text.translate(_APOSTROPHES).replace("&", "").replace("\u2026", "...")
    cleaned = re.sub(r"\.\.\.$", "", cleaned.strip())
    return " ".join(cleaned.split())


def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE) is not None


def _starts_with_phrase(text: str, phrase: str) -> bool:
    return re.match(rf"{re.escape(phrase)}(?!\w)", text, re.IGNORECASE) is not None


class PermissionClassifier:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def is_approve_label(self, label: str) -> bool:
        norm = normalize_label(label)
        return self._approve_rank(norm) is not None and not self._is_negated(norm)

    def classify(self, snapshot: DialogSnapshot) -> Decision:
        if not snapshot.buttons:
            return Decision(False, "no buttons")

        for text in (snapshot.dialog_text, *(b.label for b in snapshot.buttons)):
            keyword = self._destructive_hit(text)
            if keyword:
                return Decision(False, f"destructive keyword '{keyword}'")

        has_dismiss = any(self._is_dismiss(b.label) for b in snapshot.buttons)
        if self._config.require_dialog_context and not (snapshot.is_native_dialog or has_dismiss):
            return Decision(False, "no dialog context (no native dialog or dismiss button)")

        terminal_reason = self._terminal_rejection(snapshot)
        if terminal_reason:
            return Decision(False, terminal_reason)

        ranked: list[tuple[int, int, Button]] = []
        for index, button in enumerate(snapshot.buttons):
            norm = normalize_label(button.label)
            rank = self._approve_rank(norm)
            if rank is None or self._is_negated(norm):
                continue
            ranked.append((rank, index, button))

        if not ranked:
            return Decision(False, "no approved button label")

        _, _, best = min(ranked, key=lambda item: (item[0], item[1]))
        return Decision(True, f"approved label '{best.label}'", best)

    def _approve_rank(self, norm: str) -> int | None:
        for rank, phrase in enumerate(self._config.approve_labels):
            if _starts_with_phrase(norm, phrase):
                return rank
        return None

    def _is_negated(self, norm: str) -> bool:
        return any(_has_phrase(norm, marker) for marker in self._config.negation_markers)

    def _is_dismiss(self, label: str) -> bool:
        norm = normalize_label(label)
        return any(_has_phrase(norm, phrase) for phrase in self._config.dismiss_labels)

    def _destructive_hit(self, text: str) -> str | None:
        for keyword in self._config.destructive_keywords:
            if _has_phrase(text, keyword):
                return keyword
        return None

    def _terminal_rejection(self, snapshot: DialogSnapshot) -> str | None:
        """Terminal-command prompts are approved only when the command is read-only."""
        markers = self._config.terminal_markers
        if not any(_has_phrase(snapshot.context_label, m) or _has_phrase(snapshot.dialog_text, m) for m in markers):
            return None
        command = snapshot.dialog_text
        for marker in markers:
            command = re.sub(re.escape(marker), " ", command, flags=re.IGNORECASE)
        if not is_read_only_command(command, self._config.terminal_read_only_commands):
            return "terminal command is not on the read-only allowlist"
        return None
