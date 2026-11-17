# VS Code Permission Auto-Approve

A Windows tool that watches VS Code in the background and automatically clicks the
primary approval button of allowlisted permission and trust dialogs (for example
"Yes, I trust the authors", "Allow", "Grant Access", "OK"). It runs across VS Code
sessions: any open VS Code window is monitored, and the watcher can start at Windows logon.

Scope: Windows only, VS Code only. No ML classification and no statistics dashboard.

## Architecture

```
            +------------------+
            |  Configuration   |  config.json in %APPDATA%\vscode-autoapprove
            |     Manager      |  (defaults, validation, enable/disable)
            +--------+---------+
                     |
   +-----------------v------------------+
   |              Monitor               |  one poll: find windows -> classify -> act
   +--+--------------+-------------+----+
      |              |             |
+-----v-----+  +-----v------+  +---v---------------+
| Dialog    |  | Permission |  | Auto Click Engine |  dry-run, cooldown,
| Detector  |->| Classifier |->| (UIA invoke /     |  rate limit
| UIA       |  | allow/deny |  |  mouse fallback)  |
+-----+-----+  +------------+  +---------+---------+
      |                                    |
+-----v-----------+                 +------v--------+
| OCR fallback    |  (only when UIA |  Activity     |  activity.jsonl
| pyautogui +     |   finds no      |  Logger       |  (timestamp, dialog
| OpenCV +        |   approvable    +---------------+   text, button)
| Tesseract       |   dialog)
+-----------------+
```

| Module | Responsibility |
| --- | --- |
| `config.py` | Configuration Manager: defaults, partial overrides, validation, persistence |
| `detector.py` | Dialog Detector (accessibility): Windows UI Automation via pywinauto |
| `ocr_fallback.py` | OCR fallback: pyautogui screenshot, OpenCV preprocessing, pytesseract |
| `classifier.py` | Permission Classifier: approve-label allowlist, destructive/negation guards |
| `clicker.py` | Auto Click Engine: UIA `invoke()` with mouse fallback, safety gates |
| `logger.py` | Activity Logger: JSON Lines audit trail |
| `monitor.py` | Poll loop logic (accessibility first, OCR only as fallback) |
| `runtime.py` | Wiring, single-instance lock, DPI awareness, run loop |
| `startup.py` | Logon auto-start via a hidden launcher in the Startup folder |
| `cli.py` | Command-line interface |

## Safety model

A dialog is clicked only if **all** of these hold:

1. Its window belongs to an allowlisted process (`target_processes`, default `Code.exe`).
2. Its primary button label matches `approve_labels` at the start of the label
   (`Yes, I trust the authors` matches `Yes`). Labels with negation markers
   (`Don't Allow`, `No, I don't trust`, `Continue in Restricted Mode`) never match.
3. Neither the dialog text nor any button contains a destructive keyword
   (`Delete`, `Remove`, `Revoke`, `Reset`, `Uninstall`, `Reject`). Matching is whole-word.
4. The dialog has context: a native dialog, or a visible dismiss button such as `Cancel`.
   This keeps stray "OK" text in the editor from being clicked.
5. The engine's gates pass: not in dry-run, not inside the per-dialog cooldown, and under
   `max_clicks_per_minute`.

Every approval (and every dry-run "would click") is written to `activity.jsonl` with its
timestamp, app, dialog text, and button. The OCR path uses pyautogui, whose fail-safe
(moving the mouse to a screen corner) cancels a click by raising an error.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer (tested with 3.14)
- VS Code (the `code` command is not required)
- Tesseract OCR, **only** if you enable the OCR fallback. Install the Windows build from
  https://github.com/UB-Mannheim/tesseract/wiki and either add it to `PATH` or set
  `ocr.tesseract_cmd` in the config.

## Installation

```powershell
cd C:\Users\sunny\source\repos\vscode-permission-autoapprove
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create your configuration file (it is not overwritten if it already exists):

```powershell
vscode-autoapprove init-config
```

This creates `%APPDATA%\vscode-autoapprove\config.json`. The full reference is in
[config/config.example.json](config/config.example.json).

## Usage

| Command | What it does |
| --- | --- |
| `vscode-autoapprove scan` | Show detected dialogs and the decision for each, without clicking |
| `vscode-autoapprove scan --ocr` | Same, also running the OCR fallback |
| `vscode-autoapprove run --dry-run` | Watch and log what would be approved, without clicking |
| `vscode-autoapprove run` | Watch VS Code and auto-approve allowlisted dialogs (Ctrl+C to stop) |
| `vscode-autoapprove enable` / `disable` | Toggle auto-approval; a running watcher picks it up on its next poll |
| `vscode-autoapprove log -n 20` | Show the most recent approval actions |
| `vscode-autoapprove status` | Show config path, enabled/dry-run state, and whether a watcher is running |
| `vscode-autoapprove install-startup` | Start the watcher automatically at Windows logon |
| `vscode-autoapprove uninstall-startup` | Remove the logon entry |

Recommended first run: `scan` while a VS Code prompt is visible, then `run --dry-run`
and check `log`, then `run`.

`python -m vscode_autoapprove <command>` works the same way.

## Configuration reference

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Master switch; read on every poll |
| `dry_run` | `false` | Log decisions without clicking (`run --dry-run` overrides) |
| `target_processes` | `["Code.exe"]` | Process names whose windows are monitored |
| `poll_interval_seconds` | `1.0` | Delay between polls |
| `approve_labels` | Allow, Approve, Continue, Trust, Yes, Grant Access, Accept, Confirm, OK | Allowlist, in priority order |
| `destructive_keywords` | Delete, Remove, Revoke, Reset, Uninstall, Reject | Any whole-word hit blocks the dialog |
| `negation_markers` | No, Not, Don't, Do not, Cancel, Deny, Denied, Restricted | Labels containing these are never approved |
| `dismiss_labels` | Cancel, Deny, Don't Allow, Not Now, No, Close, Dismiss, Later, Restricted Mode | Used to confirm dialog context |
| `require_dialog_context` | `true` | Require a native dialog or a dismiss button |
| `context_depth` | `3` | How many ancestors above a button are searched for its dialog container |
| `max_clicks_per_minute` | `6` | Rate limit across all dialogs |
| `cooldown_seconds` | `10` | Minimum time before clicking the same dialog again |
| `ocr.enabled` | `false` | Enable the OCR fallback |
| `ocr.interval_seconds` | `3.0` | Minimum time between OCR captures |
| `ocr.min_confidence` | `60` | Discard OCR words below this confidence |
| `ocr.tesseract_cmd` | `""` | Path to `tesseract.exe` if it is not on `PATH` |

Changes to everything except `enabled` take effect after restarting `run`.

## Accessibility notes

- The primary path reads VS Code's UI Automation tree. In a test run against the running
  VS Code, the tree exposed every button with its name and a full scan took about 0.1 s
  per window.
- Run `vscode-autoapprove scan` while a dialog is visible. It lists each candidate, its
  buttons, and the decision. If a dialog you expect is missing, its buttons are probably
  not in the accessibility tree, which is the case the OCR fallback (`scan --ocr`) is for.
- The OCR fallback heuristics (row and context bands) are less precise than UIA. Keep it
  disabled unless you need it, and check `log` after enabling it.

## Running at logon and across sessions

The watcher is independent of any single VS Code window. It attaches to every open
window of the target processes on each poll, so it keeps working as you open and close
VS Code windows. A lock file in `%APPDATA%\vscode-autoapprove` prevents two watchers from
running at once. `install-startup` launches the watcher hidden at logon.

## Tests

```powershell
python -m pytest
```

The unit tests cover the classifier, configuration, click engine safety gates, monitor
orchestration, the OCR parsing logic, the activity log, the UIA container logic (with
fake elements), and the startup launcher. Live UIA and screen-capture paths were checked
manually against a running VS Code instance and a test window; they are not in the suite.

## Limitations

- Windows only (by design). No macOS or Linux support.
- No ML classifier, no statistics dashboard, and no system tray icon, per the current scope.
  To pause, use `vscode-autoapprove disable`.
- Auto-approval is only as safe as the allowlist. Do not add labels you would not click
  yourself.
