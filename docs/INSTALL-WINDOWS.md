# Install on Windows: step-by-step guide

This guide sets up VS Code Permission Auto-Approve on a Windows 10 or 11 PC, from a fresh
machine to a watcher that starts automatically at logon.

If you only need the short version, see the [README](../README.md).

## 1. What you need

| Requirement | Why | How to get it |
| --- | --- | --- |
| Windows 10 or 11 | UI Automation is required | Already installed |
| Python 3.10 or newer | Runs the tool | See step 2 |
| VS Code | The app being watched | Already installed |
| Git (optional) | Get and update the code | https://git-scm.com/download/win |
| Tesseract OCR (optional) | Only for the OCR fallback | See step 7 |

You do not need administrator rights. Everything installs into your user profile.

## 2. Install Python

1. Open https://www.python.org/downloads/windows/ and download the latest **Windows installer (64-bit)**.
2. Run it. **Tick "Add python.exe to PATH"** on the first screen, then choose **Install Now**.
3. Close the installer.
4. Open a new PowerShell window and check:

   ```powershell
   py --version
   ```

   Expected output: `Python 3.10.x` or newer. If `py` is not found, try `python --version`.
   If neither works, reinstall Python and make sure "Add python.exe to PATH" is ticked.

## 3. Get the code

**Option A: from Git**

```powershell
cd $env:USERPROFILE\source\repos
git clone <your-repository-URL> vscode-permission-autoapprove
cd vscode-permission-autoapprove
```

**Option B: copy the folder**

Copy the `vscode-permission-autoapprove` folder to `C:\Users\<you>\source\repos\`, then:

```powershell
cd $env:USERPROFILE\source\repos\vscode-permission-autoapprove
```

Check that you are in the right place. The folder must contain `pyproject.toml` and `src`:

```powershell
Get-ChildItem
```

## 4. Create a virtual environment

A virtual environment keeps the tool's packages separate from the rest of your system.

```powershell
py -m venv .venv
```

This creates a `.venv` folder inside the project. It takes about a minute.

## 5. Install the tool

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

`pip install .` copies the tool into the virtual environment. The downloads include
pywinauto, pyautogui, OpenCV, pytesseract, and psutil. The first install takes a few minutes.

If you plan to work on the code or run the tests, install the development extras instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### Using the command

You can run the tool in two ways:

- **Full path (always works):**
  ```powershell
  .\.venv\Scripts\vscode-autoapprove.exe --help
  ```
- **After activating the environment:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  vscode-autoapprove --help
  ```

If activation fails with "running scripts is disabled on this system", either use the full
path above, or allow scripts for your user account only (this does not need administrator rights):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

The examples below use the full path, so they work whether or not you activate the environment.
Shorten `.\.venv\Scripts\vscode-autoapprove.exe` to `vscode-autoapprove` if you have activated it.

## 6. Verify the install

```powershell
.\.venv\Scripts\vscode-autoapprove.exe --help
.\.venv\Scripts\vscode-autoapprove.exe status
```

**Expected:**
- `--help` lists the commands `run`, `scan`, `enable`, `disable`, `unrestricted`, `status`, `log`, `init-config`, `install-startup`, `uninstall-startup`.
- `status` shows `enabled: True`, `dry_run: False`, `unrestricted: False`, and `running: False`.

Optional, to check the code itself:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

## 7. Create your configuration file

```powershell
.\.venv\Scripts\vscode-autoapprove.exe init-config
notepad "$env:APPDATA\vscode-autoapprove\config.json"
```

The file is created at `C:\Users\<you>\AppData\Roaming\vscode-autoapprove\config.json`. It
starts with only two keys:

```json
{
  "enabled": true,
  "dry_run": false
}
```

Add only the settings you want to change. Any key you leave out uses the built-in default, so
future updates can change defaults without touching your file. The complete list of keys is in
[config/config.example.json](../config/config.example.json).

Common changes:

| Key | Example | Meaning |
| --- | --- | --- |
| `dry_run` | `true` | Log what would be approved without clicking. Recommended for your first days. |
| `cooldown_seconds` | `10` | Wait this long before clicking the same dialog again |
| `max_clicks_per_minute` | `6` | Upper limit on clicks per minute |
| `approve_labels` | `["Allow", "Yes", "OK"]` | Labels that may be clicked |
| `target_processes` | `["Code.exe"]` | Programs to watch |

Save the file and close Notepad. Changes to `dry_run` and most other keys apply after you
restart `run`. `enabled` and `unrestricted` apply on the next poll.

### Optional: OCR fallback

Only needed if `scan` cannot see a dialog that is visible on screen.

1. Install Tesseract for Windows from https://github.com/UB-Mannheim/tesseract/wiki.
   The default install location is `C:\Program Files\Tesseract-OCR\tesseract.exe`.
2. In `config.json`, add:
   ```json
   "ocr": {
     "enabled": true,
     "tesseract_cmd": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
   }
   ```
   Note the doubled backslashes; JSON requires them.

## 8. First run: check detection before clicking

Keep VS Code open. If a Copilot permission prompt is visible, leave it on screen.

**a. Check what the tool sees:**

```powershell
.\.venv\Scripts\vscode-autoapprove.exe scan
```

You should see your open VS Code windows listed. If a prompt is visible, the output shows its
buttons and a decision: `APPROVE` or `skip` with a reason.

**b. Watch in dry-run mode (no clicks):**

```powershell
.\.venv\Scripts\vscode-autoapprove.exe run --dry-run
```

Trigger a harmless prompt in Copilot Chat (for example, ask it to run `Get-Date` in the
terminal). Then press Ctrl+C in this window and check the log in a second window:

```powershell
.\.venv\Scripts\vscode-autoapprove.exe log -n 10
```

You should see an entry with `outcome: dry_run`.

**c. Start real auto-approval:**

```powershell
.\.venv\Scripts\vscode-autoapprove.exe run
```

Leave this window open while you work. Press Ctrl+C to stop.

## 9. Start automatically at logon (optional)

```powershell
.\.venv\Scripts\vscode-autoapprove.exe install-startup
```

This creates `vscode-autoapprove.vbs` in your Startup folder:
`C:\Users\<you>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`.
The watcher then starts hidden each time you sign in.

**Check it works:**
1. Sign out of Windows and sign back in (or restart).
2. Open Task Manager, Details tab. You should see `pythonw.exe` running.
3. Run `.\.venv\Scripts\vscode-autoapprove.exe status`. Expected: `running: True`.

**Remove it:**

```powershell
.\.venv\Scripts\vscode-autoapprove.exe uninstall-startup
```

## 10. Everyday commands

| Task | Command |
| --- | --- |
| Pause auto-approval | `vscode-autoapprove disable` |
| Resume auto-approval | `vscode-autoapprove enable` |
| See recent approvals | `vscode-autoapprove log -n 20` |
| Check state | `vscode-autoapprove status` |
| Preview without clicking | `vscode-autoapprove scan` |
| Turn on unrestricted mode (dangerous) | `vscode-autoapprove unrestricted on --confirm` |
| Turn unrestricted mode off | `vscode-autoapprove unrestricted off` |

Enable, disable, and unrestricted changes take effect on the running watcher within about a
second, without a restart.

### Unrestricted mode: read before using

`unrestricted on` approves prompts for destructive actions and for any terminal command,
including deleting files, resetting repositories, force-pushing, and running arbitrary shell
commands. It applies even when you are not watching. It is off by default. Turn it off as soon
as the task is done:

```powershell
.\.venv\Scripts\vscode-autoapprove.exe unrestricted off
```

## 11. Updating

```powershell
cd $env:USERPROFILE\source\repos\vscode-permission-autoapprove
git pull
.\.venv\Scripts\python.exe -m pip install .
```

Then restart the watcher. If it runs at logon, sign out and back in, or stop it and start `run` again. A running watcher keeps the code it started with.

## 12. Uninstall

```powershell
.\.venv\Scripts\vscode-autoapprove.exe uninstall-startup
```

Stop any running `run` window with Ctrl+C. Then remove the project and its data:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\source\repos\vscode-permission-autoapprove"
Remove-Item -Recurse -Force "$env:APPDATA\vscode-autoapprove"
```

The second command deletes your config and activity history. Skip it if you want to keep them.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `py` or `python` not found | Python not on PATH | Reinstall Python with "Add python.exe to PATH" ticked |
| `running scripts is disabled` | PowerShell execution policy | Use the full `.\.venv\Scripts\...` path, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `No windows found` in `scan` | VS Code is not running, or the process name differs | Start VS Code. Check `Get-Process Code` and adjust `target_processes` if needed |
| `already running` when starting `run` | Another watcher is running (possibly from logon) | Run `status`. If it says `running: True`, you don't need a second one |
| `status` says `running: True` but nothing is running | Stale lock after a crash | Run `status` again; a stale lock is cleared automatically |
| `Configuration error` on start | Invalid value in `config.json` | Fix the key named in the message |
| Prompt visible but not approved | Label not in `approve_labels`, or refused by a safety rule | Check the `decision` line in `scan` |
| Clicks don't register | VS Code window minimized or hidden | Bring VS Code to the front once |
| `pip install` fails building a package | Old pip, or no network access | Run `python -m pip install --upgrade pip` and retry |

## Build and share the exe (for the person sharing)

Build a self-contained `dist\vscode-autoapprove.exe` (about 78 MB, no Python needed on the
target PC). Run this from the project folder, after `Setup-AutoApprove.ps1 install`:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_exe.ps1
```

Share only `dist\vscode-autoapprove.exe` and point friends to
[FRIENDS-QUICKSTART.md](FRIENDS-QUICKSTART.md). Do not share your `config.json` or
`activity.jsonl`; they are personal to your machine. Unsigned exes can trigger SmartScreen or
antivirus warnings, so mention that when you share it.

## Where files live

| Item | Location |
| --- | --- |
| Program and virtual environment | Your project folder, including `.venv` |
| Configuration | `%APPDATA%\vscode-autoapprove\config.json` |
| Activity log | `%APPDATA%\vscode-autoapprove\activity.jsonl` |
| Single-instance lock | `%APPDATA%\vscode-autoapprove\run.lock` |
| Logon launcher | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\vscode-autoapprove.vbs` |

The activity log records dialog text, which can include file paths and command text. Treat it
as private.
