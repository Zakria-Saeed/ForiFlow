@echo off
rem ForiFlow without Docker: everything runs from disk E and opens in Chrome.
rem Backend (FastAPI + SQLite) on :8000, dashboard (Vite) on http://localhost:3000
cd /d "%~dp0"
title ForiFlow
set npm_config_cache=E:\.cache\npm
set PIP_CACHE_DIR=E:\.cache\pip
set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"

rem Start each server only if it is not already running.
curl.exe -s -o nul http://127.0.0.1:8000/health || start "ForiFlow Backend" /min cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"
curl.exe -s -o nul http://localhost:3000/ || start "ForiFlow Frontend" /min cmd /k "cd /d %~dp0frontend && npm run dev"

echo Starting ForiFlow, please wait...
set /a tries=0
:wait
curl.exe -s -o nul http://127.0.0.1:8000/health && curl.exe -s -o nul http://localhost:3000/ && goto open
set /a tries+=1
if %tries% geq 90 goto open
timeout /t 2 /nobreak >nul
goto wait

:open
if exist "%CHROME%" (start "" "%CHROME%" http://localhost:3000) else (start "" http://localhost:3000)
