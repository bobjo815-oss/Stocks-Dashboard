@echo off
setlocal

set "DASHBOARD=%~dp0portfolio_dashboard.html"

if not exist "%DASHBOARD%" (
  echo Cannot find portfolio_dashboard.html.
  echo Keep this .bat file in the same folder as portfolio_dashboard.html.
  pause
  exit /b 1
)

start "" "%DASHBOARD%"
exit /b 0
