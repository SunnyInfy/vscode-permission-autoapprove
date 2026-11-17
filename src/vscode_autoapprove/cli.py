"""Command-line interface: run, scan, enable/disable, log, status and startup management."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .classifier import PermissionClassifier
from .config import ConfigError, ConfigManager, default_config_path, default_lock_path, default_log_path
from .detector import UiaDialogDetector
from .logger import ActivityLogger
from .ocr_fallback import OcrDetector
from .runtime import SingleInstanceLock, build_monitor, enable_dpi_awareness, enabled_checker, run_forever
from .startup import install_startup, startup_script_path, uninstall_startup

Handler = Callable[[argparse.Namespace, ConfigManager], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vscode-autoapprove", description="Auto-approve allowlisted VS Code dialogs.")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.json (default: %%APPDATA%%).")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Watch VS Code and auto-approve allowlisted dialogs.")
    run.add_argument("--dry-run", action="store_true", help="Log what would be clicked without clicking.")

    scan = sub.add_parser("scan", help="Show detected dialogs and decisions without clicking.")
    scan.add_argument("--ocr", action="store_true", help="Also run the OCR fallback.")

    sub.add_parser("enable", help="Enable auto-approval (takes effect on the next poll).")
    sub.add_parser("disable", help="Disable auto-approval (takes effect on the next poll).")
    sub.add_parser("status", help="Show configuration and runtime state.")
    sub.add_parser("init-config", help="Create the default config file if missing.")
    log = sub.add_parser("log", help="Show recent approval actions.")
    log.add_argument("-n", type=int, default=20, help="Number of entries (default 20).")
    sub.add_parser("install-startup", help="Start the watcher automatically at Windows logon.")
    sub.add_parser("uninstall-startup", help="Remove the logon startup entry.")
    return parser


def cmd_run(args: argparse.Namespace, manager: ConfigManager) -> int:
    config = manager.load()
    if args.dry_run:
        config = replace(config, dry_run=True)

    lock = SingleInstanceLock(default_lock_path())
    if not lock.acquire():
        print("Another vscode-autoapprove instance is already running.", file=sys.stderr)
        return 1
    try:
        enable_dpi_awareness()
        monitor = build_monitor(config, ActivityLogger(default_log_path()), enabled_checker(manager, config.enabled))
        print(f"Watching {', '.join(config.target_processes)} (dry_run={config.dry_run}). Ctrl+C to stop.")
        run_forever(monitor, config.poll_interval_seconds)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        lock.release()
    return 0


def cmd_scan(args: argparse.Namespace, manager: ConfigManager) -> int:
    config = manager.load()
    classifier = PermissionClassifier(config)
    detector = UiaDialogDetector(config, classifier)
    targets = detector.find_target_windows()
    if not targets:
        print(f"No windows found for {', '.join(config.target_processes)}.")
        return 1
    print("Windows: " + "; ".join(f"{t.app_name} '{t.title}'" for t in targets))

    snapshots = detector.snapshots(targets)
    if args.ocr:
        snapshots += OcrDetector(config, classifier).snapshots(targets)
    if not snapshots:
        print("No approve-labelled buttons found.")
        return 0

    for snap in snapshots:
        decision = classifier.classify(snap)
        excerpt = " ".join(snap.dialog_text.split())[:120]
        print(f"- [{snap.source}] native={snap.is_native_dialog} text: {excerpt}")
        print("  buttons: " + ", ".join(b.label for b in snap.buttons))
        verdict = "APPROVE" if decision.approve else "skip"
        print(f"  decision: {verdict} ({decision.reason})")
    return 0


def cmd_enable(args: argparse.Namespace, manager: ConfigManager) -> int:
    manager.set_enabled(True)
    print(f"Auto-approval enabled ({manager.path}).")
    return 0


def cmd_disable(args: argparse.Namespace, manager: ConfigManager) -> int:
    manager.set_enabled(False)
    print(f"Auto-approval disabled ({manager.path}).")
    return 0


def cmd_status(args: argparse.Namespace, manager: ConfigManager) -> int:
    config = manager.load()
    lock = SingleInstanceLock(default_lock_path())
    running = not lock.acquire()
    if not running:
        lock.release()
    print(f"config:       {manager.path} ({'exists' if manager.path.exists() else 'defaults in use'})")
    print(f"enabled:      {config.enabled}")
    print(f"dry_run:      {config.dry_run}")
    print(f"ocr fallback: {config.ocr.enabled}")
    print(f"running:      {running}")
    print(f"activity log: {default_log_path()}")
    return 0


def cmd_log(args: argparse.Namespace, manager: ConfigManager) -> int:
    entries = ActivityLogger(default_log_path()).recent(args.n)
    if not entries:
        print("No activity recorded yet.")
    for entry in entries:
        print(f"{entry['timestamp']}  {entry['outcome']:<9} {entry['app']}  button='{entry['button']}'")
        print(f"    {entry['dialog_text'][:160]}")
    return 0


def cmd_init_config(args: argparse.Namespace, manager: ConfigManager) -> int:
    created = manager.init()
    print(f"Created {manager.path}" if created else f"Config already exists: {manager.path}")
    return 0


def cmd_install_startup(args: argparse.Namespace, manager: ConfigManager) -> int:
    path = install_startup(config_path=args.config)
    print(f"Installed logon startup script: {path}")
    return 0


def cmd_uninstall_startup(args: argparse.Namespace, manager: ConfigManager) -> int:
    removed = uninstall_startup()
    print(f"Removed {startup_script_path()}" if removed else "No startup script was installed.")
    return 0


HANDLERS: dict[str, Handler] = {
    "run": cmd_run,
    "scan": cmd_scan,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "status": cmd_status,
    "log": cmd_log,
    "init-config": cmd_init_config,
    "install-startup": cmd_install_startup,
    "uninstall-startup": cmd_uninstall_startup,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    manager = ConfigManager(args.config or default_config_path())
    try:
        return HANDLERS[args.command](args, manager)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
