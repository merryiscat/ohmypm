@echo off
REM Register the ohmyPM dashboard server to start at Windows logon.
REM Stage 5 of setup_wizard calls this; can also be run directly (as admin).
schtasks /create /tn "ohmyPM" /tr "\"%~dp0run_ohmypm.cmd\"" /sc onlogon /f
if %errorlevel%==0 (
  echo.
  echo [OK] Registered - the server starts at your next logon.
  echo      To start it right now: scripts\run_ohmypm.cmd
) else (
  echo.
  echo [FAILED] Could not register - try again as Administrator.
)
pause
