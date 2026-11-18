import sys

from vscode_autoapprove.watcher import is_watcher_cmdline, watcher_command


def test_recognises_watcher_command_lines_only():
    assert is_watcher_cmdline(["C:\\app\\vscode-autoapprove.exe", "run"])
    assert is_watcher_cmdline(["python.exe", "-m", "vscode_autoapprove", "run", "--dry-run"])
    assert not is_watcher_cmdline(["vscode-autoapprove.exe", "status"])
    assert not is_watcher_cmdline(["notepad.exe", "run.txt"])


def test_config_option_comes_before_the_run_subcommand(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    command = watcher_command(dry_run=True, config_path=tmp_path / "c.json")

    assert command[command.index("--config") + 1] == str(tmp_path / "c.json")
    assert command.index("--config") < command.index("run") < command.index("--dry-run")


def test_frozen_build_runs_the_exe_directly(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    command = watcher_command(dry_run=False)

    assert command == [sys.executable, "run"]
