@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Si el instructivo ya está encendido, solo abre el modo edición; si no, lo enciende.
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/me -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  start "" "http://127.0.0.1:8000/editar"
  exit /b
)
start "" "http://127.0.0.1:8000/editar"
python server.py
pause
