@echo off
setlocal
cd /d "%~dp0"

set "PY=%~dp0venv_train\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Starting FORMFIT web server...
start "FORMFIT WEB" powershell -NoExit -ExecutionPolicy Bypass -Command "& '%PY%' '%~dp0app.py'"

timeout /t 2 /nobreak >nul

echo Starting FORMFIT AI pose engine...
start "FORMFIT AI API" powershell -NoExit -ExecutionPolicy Bypass -Command "& '%PY%' '%~dp0formfit_api.py'"

echo.
echo FORMFIT services started in two windows.
echo Web app and AI pose API are both required for live tracking.
pause
