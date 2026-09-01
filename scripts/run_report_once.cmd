@echo off
REM ohmyPM one-time daily report (PM<->owner conversation + board + telegram).
REM Registered to run today at 15:00 by schtasks (fresh usage window after reset).
REM deadline None so nothing is skipped; low concurrency to avoid burst rate-limit.
cd /d C:\Users\minhy\project\ohmyPM
uv run python -c "from src.cc.daily_report import run_daily_report; r=run_daily_report(concurrency=3, notify=True); print('completed', r.get('completed'), 'failed', r.get('failed'))"
