@echo off
setlocal
cd /d "%~dp0"

set "CA=%~dp0.formfit_https\formfit-local-ca.crt"

if not exist "%CA%" (
  echo [ERROR] FormFit CA certificate not found:
  echo %CA%
  pause
  exit /b 1
)

echo Installing FORMFIT Local CA into the current Windows user's Trusted Root store...
certutil -user -addstore -f Root "%CA%"
if errorlevel 1 (
  echo.
  echo [ERROR] Windows could not install the trusted CA.
  echo Try running this file again, or open it with Windows permission if prompted.
  pause
  exit /b 1
)

echo.
echo [OK] FORMFIT Local CA is trusted by Windows.
echo Chrome/Edge may need a full restart once after the first installation.
echo.
pause
