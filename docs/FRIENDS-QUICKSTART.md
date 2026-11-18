# Quickstart for friends: VS Code Permission Auto-Approve

You only need one file: `vscode-autoapprove.exe`. You don't need Python, Git, or a virtual
environment. It runs on Windows 10 or 11 and approves VS Code permission prompts for you.

## 1. Put the file in a folder

1. Create a folder, for example `C:\Tools\vscode-autoapprove`.
2. Copy `vscode-autoapprove.exe` into it.
3. Open PowerShell in that folder:
   ```powershell
   cd C:\Tools\vscode-autoapprove
   ```

Every command below starts with `.\vscode-autoapprove.exe`.

**Windows may warn that the file is from an unknown publisher.** This happens with
self-built programs. Click **More info**, then **Run anyway**. If your antivirus quarantines
the file, add the folder as an exception.

## 2. Create the settings file

```powershell
.\vscode-autoapprove.exe init-config
```

This creates `%APPDATA%\vscode-autoapprove\config.json`. The default settings are safe, and you
don't need to change anything to start.

## 3. Check that it can see VS Code

Open VS Code. If a Copilot permission prompt is on screen, leave it visible, then run:

```powershell
.\vscode-autoapprove.exe scan
```

You should see your VS Code windows listed. A prompt shows its buttons and a decision,
`APPROVE` or `skip` with a reason.

## 4. Try it without clicking (dry run)

```powershell
.\vscode-autoapprove.exe start --dry-run
```

Ask Copilot to run something harmless, such as `Get-Date` in the terminal. Then:

```powershell
.\vscode-autoapprove.exe log -n 10
```

You should see a `dry_run` entry. Nothing was clicked.

## 5. Turn on real approvals

```powershell
.\vscode-autoapprove.exe restart
.\vscode-autoapprove.exe status
```

`status` should show `running: True`. The watcher runs in the background, so you can close the
PowerShell window.

## 6. Start automatically when you sign in (optional)

```powershell
.\vscode-autoapprove.exe install-startup
```

Keep the exe in the same folder afterwards. If you move it, run `install-startup` again from
the new location.

## Everyday commands

| What you want | Command |
| --- | --- |
| Start in the background | `.\vscode-autoapprove.exe start` |
| Stop it | `.\vscode-autoapprove.exe stop` |
| Restart after changing settings | `.\vscode-autoapprove.exe restart` |
| Pause approvals (keeps running) | `.\vscode-autoapprove.exe disable` |
| Resume approvals | `.\vscode-autoapprove.exe enable` |
| See what was approved | `.\vscode-autoapprove.exe log -n 20` |
| Check status | `.\vscode-autoapprove.exe status` |
| Stop starting at sign-in | `.\vscode-autoapprove.exe uninstall-startup` |

Pausing with `disable` takes effect within a second. Settings such as `dry_run` need a restart.

## Unrestricted mode: only if you understand the risk

By default the tool refuses prompts that delete files, reset things, force-push, or run
non-read-only shell commands. Unrestricted mode removes those checks, so the tool approves
them too, even when you're not looking.

```powershell
.\vscode-autoapprove.exe unrestricted on --confirm
.\vscode-autoapprove.exe unrestricted off
```

Turn it off as soon as the task is done. Every approval is recorded in `log`, tagged
`[unrestricted]`.

## Optional: OCR fallback

The exe does not include Tesseract. Only install it if `scan` can't see a dialog that you can
see on screen. See the OCR section of [INSTALL-WINDOWS.md](INSTALL-WINDOWS.md#optional-ocr-fallback).

## Uninstall

```powershell
.\vscode-autoapprove.exe stop
.\vscode-autoapprove.exe uninstall-startup
```

Then delete the folder with the exe, and optionally `%APPDATA%\vscode-autoapprove` (your
settings and activity log).

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `No windows found` in `scan` | Start VS Code first. |
| `already running` | Run `status`. If it's running, you don't need to start it again. |
| `Configuration error` | Open `%APPDATA%\vscode-autoapprove\config.json` and fix the line named in the message, or delete the file and run `init-config`. |
| A prompt is not approved | Run `scan` while it's visible. The `decision` line says why. |
| Temporary folders named `_MEI…` build up in `%TEMP%` | Harmless. The exe creates one per start. Delete them when the watcher is stopped. |
