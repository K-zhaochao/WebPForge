# ---------------------------------------------------------------------------
# Build WebPForge on Windows.
#
# NOTE: This file is deliberately pure ASCII. Windows PowerShell 5.1 (which is
# what most users have) reads .ps1 files as ANSI unless they carry a UTF-8 BOM,
# so non-ASCII characters here would corrupt parsing. Keep all messages English.
#
# Usage (in the project folder, from PowerShell):
#     powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
#
# Output:
#     dist\WebPForge.exe              single-file executable, double-click to run
#     release\WebPForge-Windows.zip   distributable zip
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [switch]$SkipZip,        # do not produce the zip
    [switch]$KeepBuildDir    # keep the intermediate build directory
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$AppName = "WebPForge"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Building: $AppName (Windows)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ---------- 1. locate Python ----------
$Py = $null
foreach ($cand in @("python", "python3", "py")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $v = & $cand -c "import sys; print(sys.version_info[0]*100+sys.version_info[1])" 2>$null
            if ([int]$v -ge 308) { $Py = $cand; break }
        } catch { }
    }
}
if (-not $Py) {
    Write-Host "[X] Python 3.8+ not found. Install from https://www.python.org/downloads/windows/" -ForegroundColor Red
    exit 1
}
Write-Host ("[.] Python: " + (& $Py --version 2>&1))

# ---------- 2. tkinter ----------
& $Py -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] This Python has no tkinter, so the GUI cannot be built." -ForegroundColor Red
    Write-Host "    Please install the official python.org build (tkinter included)." -ForegroundColor Red
    exit 1
}
Write-Host "[.] tkinter: OK"

# ---------- 3. venv + dependencies ----------
$Venv = Join-Path $PSScriptRoot ".venv"
$Vpy  = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Vpy)) {
    Write-Host "[.] Creating virtual environment .venv ..."
    & $Py -m venv $Venv
}
Write-Host "[.] Installing Pillow and PyInstaller ..."
& $Vpy -m pip install --quiet --disable-pip-version-check --upgrade pip
& $Vpy -m pip install --quiet --disable-pip-version-check --upgrade pillow pyinstaller
if ($LASTEXITCODE -ne 0) { Write-Host "[X] Dependency install failed" -ForegroundColor Red; exit 1 }

# ---------- 4. icon ----------
Write-Host "[.] Generating icon ..."
& $Vpy tools\make_icon.py assets | Out-Null

# ---------- 5. build ----------
Write-Host "[.] Building (first run takes about 1-3 minutes) ..."
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }
& $Vpy -m PyInstaller --clean --noconfirm --distpath "$PSScriptRoot\dist" --workpath "$PSScriptRoot\build" "$PSScriptRoot\build.spec"
if ($LASTEXITCODE -ne 0) { Write-Host "[X] PyInstaller failed" -ForegroundColor Red; exit 1 }

$Exe = Join-Path $PSScriptRoot "dist\$AppName.exe"
if (-not (Test-Path $Exe)) { Write-Host "[X] $Exe was not produced" -ForegroundColor Red; exit 1 }
$sizeMB = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host "[.] Executable: dist\$AppName.exe  ($sizeMB MB)" -ForegroundColor Green

# ---------- 6. self-test the produced binary ----------
Write-Host "[.] Running self-test on the packaged executable ..."
$p = Start-Process -FilePath $Exe -ArgumentList "--selftest" -WindowStyle Hidden -PassThru -Wait
if ($p.ExitCode -eq 0) {
    Write-Host "[.] Self-test passed" -ForegroundColor Green
} else {
    Write-Host "[X] Self-test returned $($p.ExitCode) - see WebPForge_selftest.txt next to the exe" -ForegroundColor Red
    exit 1
}

# ---------- 7. release zip ----------
if (-not $SkipZip) {
    Write-Host "[.] Creating release archive ..."
    $Rel = Join-Path $PSScriptRoot "release"
    if (Test-Path $Rel) { Remove-Item $Rel -Recurse -Force }
    $Stage = Join-Path $Rel "$AppName-Windows"
    New-Item -ItemType Directory -Path $Stage -Force | Out-Null

    Copy-Item $Exe $Stage
    foreach ($extra in @("README.md", "README.en.md", "LICENSE", "convert.bat", "webp_converter.py")) {
        $src = Join-Path $PSScriptRoot $extra
        if (Test-Path $src) { Copy-Item $src $Stage }
    }

    $zip = Join-Path $Rel "$AppName-Windows.zip"
    Compress-Archive -Path "$Stage\*" -DestinationPath $zip -Force
    Write-Host "[.] Archive: release\$AppName-Windows.zip" -ForegroundColor Green
}

if (-not $KeepBuildDir -and (Test-Path build)) {
    Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Build finished" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Program : dist\$AppName.exe   (double-click to run)"
if (-not $SkipZip) { Write-Host "  Release : release\$AppName-Windows.zip" }
Write-Host ""
