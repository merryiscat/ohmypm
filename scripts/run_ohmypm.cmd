@echo off
REM ohmyPM dashboard server. The logon scheduled task runs this.
REM Repo path comes from this script's own location - never hardcode it.
cd /d "%~dp0.."
uv run uvicorn src.web.server:app --host 127.0.0.1 --port 8123
