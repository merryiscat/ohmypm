# -*- coding: utf-8 -*-
"""오늘자 일간보고 + 게시판 글을 HTML 한 장으로 묶는다 — 메일·공유용.

    uv run python scripts/make_report_html.py reports/보고서.html

서버(127.0.0.1:8123)가 떠 있어야 한다 — API로 읽고, 총괄 종합만 DB에서 직접 읽는다.
메일 클라이언트는 <style> 태그를 지우기도 해서 색·여백은 전부 인라인 style로 넣는다.
외부 파일(css·이미지·폰트)은 쓰지 않는다 — 오프라인에서도 그대로 열려야 한다.

공개된 곳에 둘 거라면 scripts/encrypt_html.mjs로 암호를 걸어서 올린다.
"""
import html
import io
import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8123"
OUT = sys.argv[1] if len(sys.argv) > 1 else "ohmypm_report.html"

def api(path):
    return json.load(urllib.request.urlopen(BASE + path))

def md(text):
    """대시보드 화면과 같은 수준의 아주 얇은 마크다운 — 굵게·코드·목록·문단."""
    # 총괄 종합은 줄바꿈 없이 "## 제목"이 문장 중간에 박혀 오는 일이 잦다(모델 출력).
    # 그대로 두면 제목이 본문에 섞여 읽히므로 제목 앞에서 줄을 끊어 준다.
    text = re.sub(r"(?<!\n)(#{1,4}\s)", r"\n\1", text or "")
    out = []
    for raw in text.split("\n"):
        line = html.escape(raw.rstrip())
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"`([^`]+?)`",
                      r'<code style="background:#eceef1;border-radius:3px;padding:0 3px;font-size:92%">\1</code>',
                      line)
        if not line.strip():
            out.append('<div style="height:9px"></div>')
        elif line.lstrip().startswith(("- ", "* ")):
            out.append(f'<div style="margin:3px 0 3px 14px">- {line.lstrip()[2:]}</div>')
        elif line.startswith("#"):
            out.append(f'<div style="font-weight:700;margin:12px 0 3px">{line.lstrip("# ")}</div>')
        else:
            out.append(f'<div style="margin:3px 0">{line}</div>')
    return "".join(out)

daily = api("/api/daily")
today = daily[0]
date = today["date"]
posts = [p for p in api("/api/posts") if p["day"] == date]

con = sqlite3.connect("data/ohmypm.db")
row = con.execute("SELECT value FROM alerts WHERE key = ?", (f"daily_summary:{date}",)).fetchone()
summary = row[0] if row else ""

CARD = ("background:#ffffff;border:1px solid #e4e6ea;border-radius:10px;"
        "padding:16px 18px;margin:0 0 14px")
MUTED = "color:#8b8f96;font-size:12px"

parts = [
    '<div style="background:#f5f6f8;padding:18px 0;font-family:-apple-system,\'Segoe UI\',\'맑은 고딕\',sans-serif;color:#20242b">',
    '<div style="max-width:720px;margin:0 auto;padding:0 14px">',
    f'<div style="{CARD}">',
    f'<div style="font-size:19px;font-weight:700">ohmyPM 일간보고 · {date}</div>',
    f'<div style="{MUTED};margin-top:6px">프로젝트 {len(today["projects"])}개 중 보고 '
    f'{sum(1 for p in today["projects"] if p["active"])}개 · 게시판 글 {len(posts)}편 · '
    f'댓글 {sum(len(p["comments"]) for p in posts)}개</div>',
    "</div>",
]

if summary:
    parts += [f'<div style="{CARD}">',
              '<div style="font-size:15px;font-weight:700;margin-bottom:8px">총괄 종합</div>',
              f'<div style="font-size:13.5px;line-height:1.75">{md(summary)}</div>', "</div>"]

parts.append('<div style="font-size:13px;font-weight:700;color:#8b8f96;margin:22px 2px 10px">일간보고 (PM ↔ 담당)</div>')
for p in today["projects"]:
    if not p["active"]:
        continue
    msgs = api("/api/messages?room=" + urllib.parse.quote(p["room"], safe=""))
    parts += [f'<div style="{CARD}">',
              f'<div style="font-size:15px;font-weight:700;margin-bottom:10px">{html.escape(p["name"])}</div>']
    for m in msgs:
        who = "PM" if m["author"] == "pm" else (html.escape(p["name"]) + " 담당")
        tone = "#3a52a8" if m["author"] == "pm" else "#1a8a5a"
        parts.append(
            f'<div style="border-left:3px solid {tone};padding:2px 0 2px 12px;margin:0 0 14px">'
            f'<div style="font-size:12px;font-weight:700;color:{tone};margin-bottom:4px">{who}'
            f'<span style="{MUTED};font-weight:400;margin-left:8px">{html.escape((m["created_at"] or "")[5:16])}</span></div>'
            f'<div style="font-size:13.5px;line-height:1.72">{md(m["body"])}</div></div>')
    parts.append("</div>")

parts.append('<div style="font-size:13px;font-weight:700;color:#8b8f96;margin:22px 2px 10px">게시판</div>')
for post in posts:
    parts += [f'<div style="{CARD}">',
              f'<div style="font-size:15px;font-weight:700;line-height:1.45">{html.escape(post["title"] or "")}</div>',
              f'<div style="{MUTED};margin:5px 0 10px">{html.escape(post["author"] or "")}'
              f' · 조회 {post["views"]} · 좋아요 {post["likes"]} · 싫어요 {post["dislikes"]}</div>',
              f'<div style="font-size:13.5px;line-height:1.75">{md(post["body"])}</div>']
    for c in post["comments"]:
        parts.append(
            f'<div style="background:#f7f8fa;border-radius:8px;padding:9px 12px;margin-top:9px;font-size:13px;line-height:1.65">'
            f'<div style="font-weight:700;color:#1a8a5a;margin-bottom:2px">{html.escape(c.get("author") or "")}</div>'
            f'{md(c.get("body") or "")}</div>')
    parts.append("</div>")

parts += [f'<div style="{MUTED};text-align:center;padding:8px 0 20px">ohmyPM · 127.0.0.1:8123</div>', "</div></div>"]

body = "".join(parts)
doc = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1">'
       f'<title>ohmyPM 일간보고 {date}</title></head><body style="margin:0">{body}</body></html>')
io.open(OUT, "w", encoding="utf-8").write(doc)
print(f"{OUT} · {len(doc):,}자 · 보고 {sum(1 for p in today['projects'] if p['active'])}개 · 글 {len(posts)}편")
