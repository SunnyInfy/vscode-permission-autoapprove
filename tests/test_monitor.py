from vscode_autoapprove.classifier import PermissionClassifier
from vscode_autoapprove.clicker import AutoClickEngine
from vscode_autoapprove.config import AppConfig
from vscode_autoapprove.logger import ActivityLogger
from vscode_autoapprove.models import Button, DialogSnapshot
from vscode_autoapprove.monitor import Monitor


class FakeDetector:
    def __init__(self, uia_snapshots):
        self.uia_snapshots = uia_snapshots
        self.uia_calls = 0

    def find_target_windows(self):
        return ["vscode-window"]

    def snapshots(self, targets):
        self.uia_calls += 1
        return list(self.uia_snapshots)


class FakeOcr:
    def __init__(self, snapshots):
        self.snaps = snapshots
        self.calls = 0

    def snapshots(self, targets):
        self.calls += 1
        return list(self.snaps)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def dialog(text="Trust the authors?", source="uia"):
    return DialogSnapshot(
        app_name="Code.exe",
        window_title="w",
        dialog_text=text,
        buttons=(Button("Yes, I trust the authors"), Button("Cancel")),
        source=source,
    )


def build(tmp_path, uia, ocr=None, enabled=True, clock=None):
    config = AppConfig()
    classifier = PermissionClassifier(config)
    clicks = []
    engine = AutoClickEngine(config, ActivityLogger(tmp_path / "a.jsonl"), performer=clicks.append, clock=Clock())
    monitor = Monitor(
        classifier=classifier,
        detector=FakeDetector(uia),
        engine=engine,
        is_enabled=lambda: enabled,
        ocr=ocr,
        ocr_interval_seconds=3.0,
        clock=clock or Clock(),
    )
    return monitor, clicks


def test_disabled_monitor_does_nothing(tmp_path):
    monitor, clicks = build(tmp_path, [dialog()], enabled=False)

    assert monitor.run_once() == []
    assert clicks == []


def test_uia_approval_clicks_and_skips_ocr(tmp_path):
    ocr = FakeOcr([dialog(source="ocr")])
    monitor, clicks = build(tmp_path, [dialog()], ocr=ocr)

    results = monitor.run_once()

    assert [r.outcome for r in results] == ["clicked"]
    assert len(clicks) == 1
    assert ocr.calls == 0


def test_ocr_runs_only_as_fallback_and_respects_interval(tmp_path):
    clock = Clock()
    ocr = FakeOcr([dialog(source="ocr")])
    monitor, clicks = build(tmp_path, [], ocr=ocr, clock=clock)

    monitor.run_once()  # t=0: OCR runs
    clock.now = 1.0
    monitor.run_once()  # within interval: skipped
    clock.now = 4.0
    monitor.run_once()  # interval elapsed: runs again

    assert ocr.calls == 2
    assert len(clicks) == 1  # second pass sees the same dialog inside the cooldown window
