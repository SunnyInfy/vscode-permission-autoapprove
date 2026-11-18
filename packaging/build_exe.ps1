# Builds dist\vscode-autoapprove.exe: one self-contained file that needs no Python on the target PC.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File .\packaging\build_exe.ps1
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Create the environment first: .\Setup-AutoApprove.ps1 install"
}

Write-Host "==> Installing PyInstaller into the build environment"
& $python -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }

Write-Host "==> Building dist\vscode-autoapprove.exe (a few minutes)"
Push-Location $projectRoot
try {
    & $python -m PyInstaller --noconfirm --clean --onefile --console `
        --name vscode-autoapprove `
        --paths src `
        --collect-submodules vscode_autoapprove `
        --specpath build `
        packaging\entry.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed. Read the messages above." }
} finally {
    Pop-Location
}

$exe = Join-Path $projectRoot 'dist\vscode-autoapprove.exe'
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Built $exe ($sizeMb MB)" -ForegroundColor Green
