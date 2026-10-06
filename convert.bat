@echo off
rem ---------------------------------------------------------------------------
rem  Command-line launcher for the converter.
rem
rem  This file is intentionally pure ASCII: cmd.exe reads .bat files using the
rem  system ANSI codepage, so non-ASCII characters would be mangled. The
rem  executable is located by wildcard search instead of by its Chinese name.
rem
rem  Usage:
rem      convert.bat "D:\photos" -o "D:\out" -q 80
rem      convert.bat "D:\photos" --keep --lossless
rem      convert.bat                      (no arguments = open the GUI)
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "EXE="
for %%F in ("%~dp0*.exe") do (
    if not defined EXE set "EXE=%%~fF"
)

if not defined EXE (
    echo [ERROR] No .exe found next to this script.
    echo         Keep this file in the same folder as the converter executable.
    pause
    exit /b 1
)

if "%~1"=="" (
    "%EXE%"
    exit /b %errorlevel%
)

"%EXE%" --cli -i %*
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
    echo Done. All images converted.
) else (
    echo Finished with exit code %RC%.  ^(3 = some files failed^)
)
pause
exit /b %RC%
