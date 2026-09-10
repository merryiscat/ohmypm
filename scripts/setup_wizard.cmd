@echo off
REM ohmyPM setup wizard launcher (run from PowerShell or Explorer).
REM Runs setup_wizard.sh under Git Bash.
set "GITBASH=C:\Program Files\Git\bin\bash.exe"
if not exist "%GITBASH%" set "GITBASH=bash"
"%GITBASH%" "%~dp0setup_wizard.sh"
