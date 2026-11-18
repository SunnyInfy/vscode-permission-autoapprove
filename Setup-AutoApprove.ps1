<#
.SYNOPSIS
    One script to install, run, control and remove VS Code Permission Auto-Approve on Windows.

.DESCRIPTION
    Run from the project folder (no execution-policy change needed):

        powershell -ExecutionPolicy Bypass -File .\Setup-AutoApprove.ps1 <command> [options]

    Commands
        install        Create .venv, install the tool, create config.json.
                       Add -Startup to start the watcher at Windows logon.
        update         Pull the latest code (if this is a Git clone) and reinstall the tool.
        start          Start the watcher in the background. Add -DryRun to log without clicking.
        stop           Stop the background watcher.
        restart        Stop, then start (same options as start).
        status         Show configuration and whether the watcher is running.
        scan           Show the VS Code dialogs the tool can see, without clicking.
        log            Show the 20 most recent approval actions.
        unrestricted   on|off. "on" approves destructive and terminal prompts; you are asked to type YES.
        uninstall      Stop the watcher, remove logon startup and .venv.
                       Add -RemoveData to also delete config and logs.

    Options
        -Startup       With install: start at logon.
        -DryRun        With start/restart: log decisions without clicking.
        -Yes           Skip confirmation prompts (uninstall, unrestricted on).
        -RemoveData    With uninstall: delete %APPDATA%\vscode-autoapprove.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('install', 'update', 'start', 'stop', 'restart', 'status', 'scan', 'log', 'unrestricted', 'uninstall')]
    [string]$Command,

    [Parameter(Position = 1)]
    [ValidateSet('on', 'off')]
    [string]$State,

    [switch]$Startup,
    [switch]$DryRun,
    [switch]$Yes,
    [switch]$RemoveData
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = $PSScriptRoot
$VenvDir     = Join-Path $ProjectRoot '.venv'
$VenvPython  = Join-Path $VenvDir 'Scripts\python.exe'
$DataDir     = Join-Path $env:APPDATA 'vscode-autoapprove'
$LockFile    = Join-Path $DataDir 'run.lock'
$WatcherOut  = Join-Path $DataDir 'watcher.out.log'
$WatcherErr  = Join-Path $DataDir 'watcher.err.log'

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Tool([string[]]$Arguments) {
    & $VenvPython -m vscode_autoapprove @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "vscode-autoapprove $($Arguments -join ' ') failed (exit code $LASTEXITCODE)."
    }
}

function Get-BasePython {
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python'; Args = @() }
    )
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $candidate.Exe @($candidate.Args) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        $ok = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $previous
        if ($ok) { return $candidate }
    }
    throw "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/windows/ and tick 'Add python.exe to PATH'."
}

function Assert-Installed {
    if (-not (Test-Path $VenvPython)) {
        throw "The tool is not installed yet. Run: .\Setup-AutoApprove.ps1 install"
    }
}

function Get-WatcherProcess {
    # The lock file holds the watcher's PID. Confirm the process is really ours before acting on it.
    if (-not (Test-Path $LockFile)) { return $null }
    $pidText = (Get-Content $LockFile -Raw).Trim()
    $pidValue = 0
    if (-not [int]::TryParse($pidText, [ref]$pidValue)) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -match 'vscode[-_]autoapprove') { return $process }
    return $null
}

function Install-Tool {
    $base = Get-BasePython
    if (-not (Test-Path $VenvPython)) {
        Write-Step "Creating virtual environment in $VenvDir"
        & $base.Exe @($base.Args) -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
    }

    Write-Step "Installing the tool (the first run takes a few minutes)"
    & $VenvPython -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }
    & $VenvPython -m pip install --upgrade $ProjectRoot
    if ($LASTEXITCODE -ne 0) { throw "Installing the tool failed. Read the messages above." }

    Write-Step "Creating configuration (existing settings are kept)"
    Invoke-Tool @('init-config')

    if ($Startup) {
        Write-Step "Enabling start at logon"
        Invoke-Tool @('install-startup')
    }

    Invoke-Tool @('status')
    Write-Host ""
    Write-Host "Install complete. Next steps:" -ForegroundColor Green
    Write-Host "  .\Setup-AutoApprove.ps1 scan"
    Write-Host "  .\Setup-AutoApprove.ps1 start -DryRun"
    Write-Host "  .\Setup-AutoApprove.ps1 log"
}

function Update-Tool {
    Assert-Installed
    if (Test-Path (Join-Path $ProjectRoot '.git')) {
        Write-Step "Pulling the latest code"
        git -C $ProjectRoot pull --ff-only
        if ($LASTEXITCODE -ne 0) { throw "git pull failed. Resolve it manually, then run update again." }
    }
    Write-Step "Reinstalling the tool"
    & $VenvPython -m pip install --upgrade $ProjectRoot
    if ($LASTEXITCODE -ne 0) { throw "Reinstalling the tool failed." }
    if (Get-WatcherProcess) {
        Write-Host "The watcher is still running the old code. Run: .\Setup-AutoApprove.ps1 restart" -ForegroundColor Yellow
    } else {
        Write-Host "Update complete." -ForegroundColor Green
    }
}

function Start-Watcher {
    Assert-Installed
    $existing = Get-WatcherProcess
    if ($existing) {
        Write-Host "The watcher is already running (PID $($existing.ProcessId))."
        return
    }
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    $runArgs = @('-m', 'vscode_autoapprove', 'run')
    if ($DryRun) { $runArgs += '--dry-run' }

    $process = Start-Process -FilePath $VenvPython -ArgumentList $runArgs -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $WatcherOut -RedirectStandardError $WatcherErr
    Start-Sleep -Seconds 3
    if ($process.HasExited) {
        throw "The watcher stopped right away. See $WatcherErr"
    }
    $mode = if ($DryRun) { 'dry-run mode (no clicks)' } else { 'live mode' }
    Write-Host "Watcher started in the background (PID $($process.Id)), $mode." -ForegroundColor Green
}

function Stop-Watcher {
    $existing = Get-WatcherProcess
    if (-not $existing) {
        Write-Host "The watcher is not running."
        if (Test-Path $LockFile) { Remove-Item -Force $LockFile }
        return
    }
    Stop-Process -Id $existing.ProcessId -Force
    if (Test-Path $LockFile) { Remove-Item -Force $LockFile }
    Write-Host "Watcher stopped (PID $($existing.ProcessId))." -ForegroundColor Green
}

function Show-Status {
    Assert-Installed
    Invoke-Tool @('status')
}

function Set-Unrestricted {
    Assert-Installed
    if ($State -eq 'on') {
        if (-not $Yes) {
            Write-Host "Unrestricted mode lets the watcher approve destructive and terminal prompts without checks." -ForegroundColor Yellow
            $answer = Read-Host "Type YES to turn it on"
            if ($answer -ne 'YES') {
                Write-Host "Not changed."
                return
            }
        }
        Invoke-Tool @('unrestricted', 'on', '--confirm')
    } else {
        Invoke-Tool @('unrestricted', 'off')
    }
}

function Uninstall-Tool {
    if (-not $Yes) {
        $answer = Read-Host "This stops the watcher and deletes $VenvDir. Type YES to continue"
        if ($answer -ne 'YES') {
            Write-Host "Cancelled."
            return
        }
    }
    Stop-Watcher
    if (Test-Path $VenvPython) {
        Invoke-Tool @('uninstall-startup')
    }
    if (Test-Path $VenvDir) {
        Remove-Item -Recurse -Force $VenvDir
        Write-Host "Removed $VenvDir"
    }
    if ($RemoveData -and (Test-Path $DataDir)) {
        Remove-Item -Recurse -Force $DataDir
        Write-Host "Removed $DataDir"
    }
    Write-Host "Uninstall complete. This project folder was left in place." -ForegroundColor Green
}

try {
    switch ($Command) {
        'install'      { Install-Tool }
        'update'       { Update-Tool }
        'start'        { Start-Watcher }
        'stop'         { Stop-Watcher }
        'restart'      { Stop-Watcher; Start-Watcher }
        'status'       { Show-Status }
        'scan'         { Assert-Installed; Invoke-Tool @('scan') }
        'log'          { Assert-Installed; Invoke-Tool @('log', '-n', '20') }
        'unrestricted' {
            if (-not $State) { throw "Give a state: .\Setup-AutoApprove.ps1 unrestricted on|off" }
            Set-Unrestricted
        }
        'uninstall'    { Uninstall-Tool }
    }
    exit 0
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
