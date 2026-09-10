@echo off
REM Register the ohmyPM dashboard server to start at Windows logon.
REM Stage 5 of setup_wizard calls this; can also be run directly.
REM Uses pythonw.exe (GUI subsystem) so no console window appears at logon.
REM schtasks needs an absolute path, so build it from this script location.
setlocal
set "ROOT=%~dp0.."
set "PYW=%ROOT%\.venv\Scripts\pythonw.exe"
set "APP=%ROOT%\scripts\run_ohmypm_hidden.py"
if not exist "%PYW%" (
  echo [FAILED] %PYW% not found - run "uv sync" in the repo first.
  pause
  exit /b 1
)
schtasks /create /tn "ohmyPM" /tr "\"%PYW%\" \"%APP%\"" /sc onlogon /f
if %errorlevel%==0 (
  echo.
  echo [OK] Registered - the server starts hidden at your next logon.
  echo      Start now : schtasks /run /tn ohmyPM
  echo      Stop      : scripts\stop_ohmypm.cmd
  echo      With a window and live log: scripts\run_ohmypm.cmd
) else (
  echo.
  echo [FAILED] Could not register - try again as Administrator.
)
endlocal
pause
