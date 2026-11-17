from dataclasses import replace

from vscode_autoapprove.classifier import PermissionClassifier
from vscode_autoapprove.clicker import AutoClickEngine
from vscode_autoapprove.config import AppConfig
from vscode_autoapprove.logger import ActivityLogger
from vscode_autoapprove.models import Button, DialogSnapshot


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def snap(text):
    return DialogSnapshot(
        app_name="Code.exe",
        window_title="w",
        dialog_text=text,
        buttons=(Button("Allow"), Button("Cancel")),
        source="uia",
    )


def approve(classifier, snapshot):
    return classifier.classify(snapshot)


def make_engine(tmp_path, config, performer, clock):
    activity = ActivityLogger(tmp_path / "activity.jsonl")
    return AutoClickEngine(config, activity, performer=performer, clock=clock), activity


def test_dry_run_never_invokes_performer(tmp_path):
    clicks = []
    config = replace(AppConfig(), dry_run=True)
    engine, activity = make_engine(tmp_path, config, clicks.append, Clock())
    classifier = PermissionClassifier(config)
    snapshot = snap("Allow file access?")

    result = engine.handle(snapshot, approve(classifier, snapshot))

    assert result.outcome == "dry_run"
    assert clicks == []
    assert activity.recent()[0]["outcome"] == "dry_run"


def test_cooldown_suppresses_repeat_clicks_on_same_dialog(tmp_path):
    clicks = []
    clock = Clock()
    config = AppConfig(cooldown_seconds=10)
    engine, _ = make_engine(tmp_path, config, clicks.append, clock)
    classifier = PermissionClassifier(config)
    snapshot = snap("Allow file access?")

    first = engine.handle(snapshot, approve(classifier, snapshot))
    clock.now += 5
    second = engine.handle(snapshot, approve(classifier, snapshot))

    assert first.outcome == "clicked"
    assert second.outcome == "cooldown"
    assert len(clicks) == 1


def test_rate_limit_caps_clicks_per_minute(tmp_path):
    clicks = []
    clock = Clock()
    config = AppConfig(max_clicks_per_minute=2, cooldown_seconds=0)
    engine, _ = make_engine(tmp_path, config, clicks.append, clock)
    classifier = PermissionClassifier(config)

    outcomes = []
    for index in range(3):
        snapshot = snap(f"Allow request {index}?")
        outcomes.append(engine.handle(snapshot, approve(classifier, snapshot)).outcome)

    assert outcomes == ["clicked", "clicked", "rate_limited"]


def test_performer_failure_is_logged_not_raised(tmp_path):
    def broken(button):
        raise RuntimeError("element gone")

    config = AppConfig()
    engine, activity = make_engine(tmp_path, config, broken, Clock())
    classifier = PermissionClassifier(config)
    snapshot = snap("Allow?")

    result = engine.handle(snapshot, approve(classifier, snapshot))

    entry = activity.recent()[0]
    assert result.outcome == "error"
    assert entry["button"] == "Allow"
    assert "element gone" in entry["reason"]
    assert entry["dialog_text"] == "Allow?"
