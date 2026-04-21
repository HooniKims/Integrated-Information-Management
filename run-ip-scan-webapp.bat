@echo off
setlocal
cd /d "%~dp0"
set "APP_HOST=0.0.0.0"
set "APP_PORT=8765"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is required but was not found in PATH.
  pause
  exit /b 1
)

start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:%APP_PORT%'"
python server.py
