@echo off
setlocal
cd /d "%~dp0"
set "APP_HOST=0.0.0.0"
set "APP_PORT=8765"
set "APP_URL=http://127.0.0.1:%APP_PORT%"
set "PYTHON_KIND="

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_KIND=venv"
)

if not defined PYTHON_KIND (
  py -3 -V >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_KIND=py"
  )
)

if not defined PYTHON_KIND (
  python -V >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_KIND=python"
  )
)

if not defined PYTHON_KIND (
  echo Python 3 is required to run this app.
  echo.
  echo Install Python for Windows, then run:
  echo   py -3 -m pip install -r requirements.txt
  echo.
  echo If the installer does not add Python to PATH, reopen the terminal after installation.
  pause
  exit /b 1
)

start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='%APP_URL%'; $healthUrl=$url + '/api/health'; for ($i=0; $i -lt 40; $i++) { try { Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 1 | Out-Null; Start-Process $url; exit 0 } catch { Start-Sleep -Milliseconds 500 } }"

if /I "%PYTHON_KIND%"=="venv" (
  ".venv\Scripts\python.exe" server.py
) else if /I "%PYTHON_KIND%"=="py" (
  py -3 server.py
) else (
  python server.py
)
