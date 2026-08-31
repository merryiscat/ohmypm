@echo off
REM ohmyPM ?€?œë³´???œë²„ ê¸°ë™ ???‘ì—… ?¤ì?ì¤„ëŸ¬ê°€ ë¶€?????´ê±¸ ?¤í–‰?œë‹¤.
cd /d C:\Users\minhy\project\ohmyPM
uv run uvicorn src.web.server:app --host 127.0.0.1 --port 8123
