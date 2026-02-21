@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: OWASP Dependency Scanner — Windows Setup Launcher
:: Runs setup-windows.ps1 with the correct execution policy bypass.
:: Right-click → Run as Administrator for first-time setup.
:: ─────────────────────────────────────────────────────────────────────────────

:: Check for admin — required to write to C:\ (OWASP DC install) and winget
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Administrator privileges required.
    echo      Right-click this file and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
if errorlevel 1 (
    echo.
    echo  Setup encountered errors. See messages above.
    pause
    exit /b 1
)
pause
