"""Startup integration: a hidden launcher in the per-user Startup folder runs `run` at logon."""

from __future__ import annotations

import os
import sys
from pathlib import Path

STARTUP_SCRIPT_NAME = "vscode-autoapprove.vbs"


def startup_script_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not set; cannot locate the Startup folder")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / STARTUP_SCRIPT_NAME


def build_vbs(python_exe: str, config_path: Path | None = None) -> str:
    pythonw = Path(python_exe).with_name("pythonw.exe")
    interpreter = str(pythonw) if pythonw.exists() else python_exe
    command = f'"{interpreter}" -m vscode_autoapprove run'
    if config_path is not None:
        command += f' --config "{config_path}"'
    escaped = command.replace('"', '""')  # VBScript string literal escaping
    return f'CreateObject("WScript.Shell").Run "{escaped}", 0, False\r\n'


def install_startup(config_path: Path | None = None, python_exe: str = sys.executable) -> Path:
    path = startup_script_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "mbcs" if sys.platform == "win32" else "utf-8"  # WScript reads the ANSI code page
    path.write_text(build_vbs(python_exe, config_path), encoding=encoding)
    return path


def uninstall_startup() -> bool:
    path = startup_script_path()
    if path.exists():
        path.unlink()
        return True
    return False
