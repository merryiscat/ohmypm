@echo off
REM Stop the ohmyPM dashboard server.
REM The hidden launcher leaves no window to close, so kill by listening port.
setlocal
set FOUND=
for /f "tokens=5" %%p in (
'netstat -ano ^| findstr /r /c:"TCP.*127.0.0.1:8123.*LISTENING"'
) do (
  taskkill /F /PID %%p >nul 2>&1
  set FOUND=1
)
if defined FOUND (echo [OK] ohmyPM server stopped.) else (echo [..] Nothing listening on 127.0.0.1:8123.)
endlocal
