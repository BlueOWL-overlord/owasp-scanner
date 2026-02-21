@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: OWASP Dependency Scanner — Start (Windows)
:: Opens backend and frontend in separate console windows.
:: Run setup-windows.bat first if this is a fresh install.
:: ─────────────────────────────────────────────────────────────────────────────

set ROOT=%~dp0

:: Guard: venv must exist
if not exist "%ROOT%backend\.venv\Scripts\uvicorn.exe" (
    echo.
    echo  [!] Backend not set up yet. Run setup-windows.bat first.
    echo.
    pause
    exit /b 1
)

:: Guard: node_modules must exist
if not exist "%ROOT%frontend\node_modules" (
    echo.
    echo  [!] Frontend not set up yet. Run setup-windows.bat first.
    echo.
    pause
    exit /b 1
)

echo.
echo  Starting OWASP Dependency Scanner...
echo.

:: Launch backend in a new window
start "OWASP Scanner — Backend :8000" cmd /k "cd /d %ROOT%backend && .venv\Scripts\activate && echo Backend starting on http://localhost:8000 && uvicorn app.main:app --reload --port 8000"

:: Short delay so backend starts first
timeout /t 2 /nobreak >nul

:: Launch frontend in a new window
start "OWASP Scanner — Frontend :3000" cmd /k "cd /d %ROOT%frontend && echo Frontend starting on http://localhost:3000 && npm run dev"

:: Wait then open browser
timeout /t 4 /nobreak >nul
start http://localhost:3000

echo  Backend  → http://localhost:8000
echo  Frontend → http://localhost:3000
echo  API docs → http://localhost:8000/docs
echo.
echo  Both services are running in separate windows.
echo  Close those windows to stop the application.
echo.
