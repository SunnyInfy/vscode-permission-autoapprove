"""Background watcher control: start it detached, find it, and stop it.

The running watcher is identified by the PID in the lock file, and that PID is only trusted
when its command line really belongs to this program.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import psutil

from .config import default_app_dir, default_lock_path

START_GRACE_SECONDS = 3


class WatcherError(RuntimeError):
    """The watcher could not be started."""


def is_watcher_cmdline(cmdline: list[str]) -> bool:
    """True for `<exe> run` and `python -m vscode_autoapprove run` command lines."""
    names_program = any("vscode_autoapprove" in arg or "vscode-autoapprove" in arg for arg in cmdline)
    return names_program and "run" in cmdline


def find_watcher() -> psutil.Process | None:
    try:
        pid = int(default_lock_path().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    try:
        process = psutil.Process(pid)
        cmdline = process.cmdline()
    except psutil.Error:
        return None
    return process if is_watcher_cmdline(cmdline) else None


def watcher_command(dry_run: bool, config_path: Path | None = None) -> list[str]:
    if getattr(sys, "frozen", False):  # packaged exe: the exe itself is the program
        command = [sys.executable]
    else:
        command = [sys.executable, "-m", "vscode_autoapprove"]
    if config_path is not None:  # top-level option: must precede `run`
        command += ["--config", str(config_path)]
    command.append("run")
    if dry_run:
        command.append("--dry-run")
    return command


def start_background(dry_run: bool, config_path: Path | None = None) -> psutil.Process:
    existing = find_watcher()
    if existing is not None:
        raise WatcherError(f"the watcher is already running (PID {existing.pid})")

    log_dir = default_app_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    with (log_dir / "watcher.out.log").open("ab") as out, (log_dir / "watcher.err.log").open("ab") as err:
        child = subprocess.Popen(
            watcher_command(dry_run, config_path),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            creationflags=creation_flags,
            close_fds=True,
        )
    time.sleep(START_GRACE_SECONDS)  # give the watcher time to take the lock
    if child.poll() is not None:
        raise WatcherError(f"the watcher exited right away; see {log_dir / 'watcher.err.log'}")
    return psutil.Process(child.pid)


def stop_watcher() -> int | None:
    """Stop the running watcher. Returns its PID, or None when nothing was running."""
    lock = default_lock_path()
    process = find_watcher()
    if process is None:
        lock.unlink(missing_ok=True)  # clear a stale lock left by a crashed watcher
        return None
    pid = process.pid
    process.kill()  # a background watcher has no console, so Ctrl+C is not available
    try:
        process.wait(timeout=5)
    except psutil.TimeoutExpired:
        pass
    lock.unlink(missing_ok=True)
    return pid
