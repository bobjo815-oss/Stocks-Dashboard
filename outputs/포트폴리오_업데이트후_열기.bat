@echo off
setlocal

set "ROOT=%~dp0.."
set "DASHBOARD=%~dp0portfolio_dashboard.html"
set "PYTHON=C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON%" (
  set "PYTHON=python"
)

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python or use the basic open launcher.
  pause
  exit /b 1
)

"%PYTHON%" "%ROOT%\work\update_portfolio_from_xlsx.py"
"%PYTHON%" "%ROOT%\work\update_kis_prices.py"
"%PYTHON%" "%ROOT%\work\update_dart_data.py"

if not exist "%DASHBOARD%" (
  echo Cannot find portfolio_dashboard.html.
  pause
  exit /b 1
)

start "" "%DASHBOARD%"
exit /b 0
