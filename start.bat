@echo off
chcp 65001 >nul
rem ===== Awqaf letters: one-click local launcher =====
cd /d "%~dp0"
set "URL=http://127.0.0.1:5000"
set "PY=.venv\Scripts\python.exe"

rem 1) Python venv + requirements (first run only)
if not exist "%PY%" (
  py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\.installed" (
  "%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt && echo ok> ".venv\.installed"
)

rem 2) Server already running: just open the window
netstat -ano | findstr /r /c:"127.0.0.1:5000 .*LISTENING" >nul && goto open

rem 3) Claude Code not logged in: show the login window (once)
for /f "delims=" %%L in ('call "%PY%" -c "import app;print(app.claude_status())" 2^>nul') do set "CLOK=%%L"
if /i "%CLOK%"=="True" goto server
for /f "delims=" %%E in ('call "%PY%" -c "import app;print(app.claude_exe())" 2^>nul') do set "CLEXE=%%E"
if defined CLEXE start "Claude - login" cmd /c ""%CLEXE%" auth login & echo. & echo Done. You can close this window. & pause"

:server

rem 4) Server (127.0.0.1 only, auto-reload on edits)
start "awqaf-server" /b "%PY%" app.py > server.log 2>&1

rem Wait for the server (up to 30 s)
for /l %%i in (1,1,60) do (
  curl -s -o nul "%URL%/health" && goto open
  ping -n 1 -w 500 127.0.0.1 >nul
)

:open
rem 5) App window (Edge, else Chrome)
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe" >nul 2>&1 && (start "" msedge --app=%URL% & goto :eof)
start "" chrome --app=%URL%
