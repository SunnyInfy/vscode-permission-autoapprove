"""Entry point used by PyInstaller to build vscode-autoapprove.exe."""

from vscode_autoapprove.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
