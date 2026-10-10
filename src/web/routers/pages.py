"""대시보드 화면 (HTML). 왼쪽 사이드바(탭 + 프로젝트 룸) + 오른쪽 뷰.

단일 HTML SPA — location.hash 로 뷰를 전환한다:
  #/dashboard   요약 + 프로젝트 카드 (헤더 '스캔(설치)')
  #/board       게시판 — 토론 시작/중지, 글 목록      #/post/<id> 글 상세
  #/weekly      주간보고 — 실행, 날짜별 보고, 프로젝트별 몫
  #/lab         랩실 — 연구원 3명의 위키·제안서·자문
  #/agents      담당 에이전트 — 점수·배운 것·모델
  #/ports       포트 — 등록·감지·시작/중지
  #/room/<path> 프로젝트 룸 — 설치 상태·칸반·주간보고 몫·제안서·점수 이력 + 담당 채팅

2026-10-09 2차 리뉴얼: 이슈·칸반·달력·일간보고 화면 제거. 데이터는 /api/* 를 fetch해 그린다.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.config.settings import settings

router = APIRouter()

_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ohmyPM</title>
<style>
  :root{--bg:#f5f6f8;--card:#fff;--line:#e4e6ea;--muted:#626975;--ink:#20242b;--red:#c23838;--amber:#95580b;--green:#167a4c;--sb:#1f232b}
  *{box-sizing:border-box}
  body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:var(--bg);color:var(--ink);font-size:14px}
  a{color:inherit;text-decoration:none}
  .app{display:flex;height:100vh;overflow:hidden}
  aside{width:230px;flex:0 0 230px;background:var(--sb);color:#cfd3da;position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column}
  aside .brand{font-size:16px;font-weight:700;color:#fff;padding:16px 18px;border-bottom:1px solid #2c313b}
  aside nav{padding:8px 0}
  aside .nav-item{display:flex;align-items:center;gap:9px;padding:9px 18px;cursor:pointer;font-size:13.5px;color:#cfd3da;border-left:3px solid transparent}
  aside .nav-item:hover{background:#272c35;color:#fff}
  aside .nav-item.active{background:#2d333e;color:#fff;border-left-color:var(--green)}
  aside .sec-label{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#9aa0aa;padding:14px 18px 5px;font-weight:700}
  aside .rooms{flex:1;overflow-y:auto}
  aside .room-item{display:flex;align-items:center;gap:8px;padding:7px 18px 7px 16px;cursor:pointer;font-size:12.5px;color:#b8bdc6;border-left:3px solid transparent}
  aside .room-item:hover{background:#272c35;color:#fff}
  aside .room-item.active{background:#2d333e;color:#fff;border-left-color:var(--green)}
  aside .room-item .dot{width:6px;height:6px;border-radius:50%;background:#4a515d;flex:0 0 6px}
  aside .room-item .dot.on{background:var(--green)}
  aside .room-item .rname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  aside .room-item .rx{margin-left:auto;font-size:11px;color:#9aa0aa;display:none;padding:0 3px;line-height:1}
  aside .room-item:hover .rx{display:block}
  aside .room-item .rx:hover{color:#fff}
  .etabs{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
  .etab{padding:3px 11px;border:1px solid var(--line);border-radius:14px;cursor:pointer;font-size:12px;color:var(--muted);background:#fff}
  .etab:hover{color:var(--ink)}
  .etab.on{background:var(--sb);color:#fff;border-color:var(--sb)}
  .modal-bg{position:fixed;inset:0;background:rgba(15,18,24,.45);display:flex;align-items:center;justify-content:center;z-index:100}
  .modal{background:var(--card);border:1px solid var(--line);border-radius:10px;min-width:320px;max-width:440px;padding:18px 20px;box-shadow:0 12px 40px rgba(0,0,0,.18)}
  .modal .m-title{font-size:14.5px;font-weight:700;margin-bottom:10px}
  .modal .m-body{font-size:13px;line-height:1.6;white-space:pre-line;color:var(--ink);margin-bottom:16px}
  .modal .m-btns{display:flex;justify-content:flex-end;gap:8px}
  .modal button{font:inherit;font-size:12.5px;padding:6px 14px;border-radius:8px;border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer}
  .modal button:hover{background:var(--bg)}
  .modal button.danger{background:var(--red);border-color:var(--red);color:#fff}
  .body{flex:1;min-width:0;display:flex;flex-direction:column}
  header{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);padding:12px 22px;display:flex;align-items:center;gap:18px;z-index:10;min-height:58px}
  header h1{font-size:17px;margin:0;white-space:nowrap}
  .summary{display:flex;gap:16px;color:var(--muted);font-size:13px;flex-wrap:wrap}
  .summary b{color:var(--ink);font-size:15px}
  .hstatus{color:var(--muted);font-size:12.5px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .hstatus b{color:var(--ink)}
  .hstatus .live{color:var(--green);font-weight:700}
  .actions{margin-left:auto;display:flex;gap:8px;align-items:center}
  .actions select{padding:6px 8px;border:1px solid var(--line);border-radius:6px;font-size:13px;font-family:inherit;background:#fff}
  .summary[hidden],.actions[hidden],.hstatus[hidden]{display:none!important}
  button{padding:7px 14px;border:none;background:var(--green);color:#fff;border-radius:6px;cursor:pointer;font-size:13px;font-family:inherit}
  button.ghost{background:#fff;color:var(--ink);border:1px solid var(--line)}
  button.danger{background:var(--red)}
  button:disabled{opacity:.55;cursor:default}
  main{padding:20px 22px;max-width:1500px;margin:0 auto;width:100%;flex:1;min-height:0;display:flex;flex-direction:column;overflow-y:auto}
  section{margin-bottom:26px}
  section>h2{font-size:13px;letter-spacing:.02em;color:var(--muted);text-transform:uppercase;margin:0 0 10px;font-weight:700}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card h3{margin:0 0 9px;font-size:14.5px;display:flex;align-items:center;gap:8px}
  .card h3 .open{margin-left:auto;font-size:11.5px;color:var(--green);cursor:pointer;white-space:nowrap}
  .card .line{font-size:12.5px;color:#3a3f47;padding:3px 0;line-height:1.45}
  .badge{font-size:11px;padding:1px 7px;border-radius:20px;font-weight:700}
  .badge.on{background:#e7f3ec;color:#1f7a44} .badge.off{background:#f1f3f6;color:var(--muted)}
  .badge.red{background:#fdeceb;color:var(--red)}
  .more{color:var(--muted);font-size:12px;padding-top:4px}
  .note-line{color:var(--muted);font-size:12px;padding:8px 2px 0;line-height:1.55}
  .empty{color:var(--muted);text-align:center;padding:40px}
  .chat{display:flex;flex-direction:column;flex:1;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;min-height:0}
  .chat .stream{flex:1;overflow-y:auto;padding:16px 18px;display:flex;flex-direction:column;gap:10px;min-height:240px}
  .msg{max-width:74%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
  .msg .who{font-size:11px;color:var(--muted);margin-bottom:2px;font-weight:700}
  .msg .ts{font-size:10.5px;color:var(--muted);margin-top:3px}
  .msg.user{align-self:flex-end;background:#e7f3ec;border:1px solid #cfe6da}
  .msg.agent{align-self:flex-start;background:#f1f3f6;border:1px solid var(--line)}
  .chat .composer{display:flex;gap:8px;padding:12px;border-top:1px solid var(--line);background:#fafbfc}
  .chat .composer textarea{flex:1;padding:9px 12px;border:1px solid var(--line);border-radius:8px;font-size:13.5px;font-family:inherit;resize:none;line-height:1.45;max-height:140px;overflow-y:auto}
  .chat-empty{color:var(--muted);text-align:center;margin:auto;padding:30px}
  .msg.pending{align-self:flex-start;background:#f7f8fa;border:1px dashed var(--line);color:var(--muted);font-style:italic}
  .msg.pending.stuck{color:var(--amber);border-color:#e7cfa6;background:#fdf7ee;font-style:normal;display:flex;align-items:center;gap:10px}
  .msg.pending.stuck .retry{padding:3px 10px;font-size:12px;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:6px;white-space:nowrap}
  .room-layout{display:flex;gap:16px;flex:1;min-height:0}
  .room-main{flex:1;min-width:0;min-height:0;overflow-y:auto}
  .room-main>section{margin-bottom:18px}
  .room-side{width:420px;flex:0 0 420px;display:flex;flex-direction:column;min-height:0}
  .room-side .side-h{font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.02em;margin:0 2px 8px;display:flex;align-items:center;justify-content:space-between;gap:8px}
  .mini-btn{font-size:11px;font-weight:700;padding:4px 10px;border:1px solid var(--line);border-radius:14px;background:var(--card);color:#3a52a8;cursor:pointer;text-transform:none;letter-spacing:0}
  .mini-btn:hover:not(:disabled){background:#eef1fb}
  .mini-btn.red{color:var(--red)}
  .mini-btn:disabled{opacity:.55;cursor:default}
  @media(max-width:1000px){.room-layout{flex-direction:column}.room-side{width:auto;flex:none}}
  .post{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:12px;max-width:920px}
  .post-h{display:flex;align-items:center;gap:10px;margin-bottom:6px}
  .post-title{font-weight:700;font-size:16px;line-height:1.4}
  .post-day{color:var(--muted);font-size:12px;margin-left:auto;white-space:nowrap}
  .post-body{font-size:14.5px;color:#2b2f36;line-height:1.78;margin:4px 0 14px}
  .post-body>div{margin:3px 0}
  .post-body .mh{font-size:15px;margin:16px 0 5px}
  .post-body .mgap{height:11px}
  .post-body ul{margin:9px 0} .post-body li{margin:4px 0}
  .cmts{border-top:1px solid #f2f3f5;padding-top:12px;display:flex;flex-direction:column;gap:9px}
  .cmt{font-size:13px;color:#33383f;line-height:1.62;background:#f7f8fa;border-radius:8px;padding:9px 12px}
  .cmt-who{font-weight:700;color:var(--green);margin-right:5px;display:block;margin-bottom:2px}
  .cmt.none{color:var(--muted);background:none;padding:2px 0;font-style:italic}
  .md .mh{font-weight:700;margin:6px 0 2px}
  .md ul{margin:4px 0;padding-left:18px} .md li{margin:1px 0}
  .md code{background:#eceef1;border-radius:4px;padding:0 3px;font-size:.9em;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
  .md>div{margin:0 0 6px} .md>div:last-child{margin-bottom:0}
  .md .mgap{height:6px} .md>div:first-child,.md>ul:first-child{margin-top:0}
  /* 마크다운 표 — 칸이 많으면 표만 옆으로 밀어 볼 수 있게 */
  .md .md-table{overflow-x:auto;margin:8px 0}
  .md table{border-collapse:collapse;width:100%;font-size:.93em;line-height:1.6}
  .md th,.md td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
  .md th{color:var(--muted);font-weight:700;white-space:nowrap;border-bottom-color:#cfd3d9}
  .md tbody tr:last-child td{border-bottom:none}
  .prow{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:11px 14px;margin-bottom:8px;cursor:pointer;max-width:920px}
  .prow:hover{border-color:var(--green)}
  .prow-t{font-weight:600;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .prow-meta{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}
  .prow-meta .c{color:var(--green);font-weight:700}
  .prow-body{background:#fafbfc;border:1px solid var(--line);border-top:none;border-radius:0 0 8px 8px;padding:12px 14px;margin:-8px 0 10px;max-width:920px;font-size:13.5px;line-height:1.7}
  .back{color:var(--green);cursor:pointer;font-size:13px;margin-bottom:12px;display:inline-block}
  .cmt-form{display:flex;gap:8px;margin-top:12px}
  .cmt-form textarea{flex:1;padding:8px 11px;border:1px solid var(--line);border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;min-height:38px}
  .cmt.user{background:#e7f3ec;border:1px solid #cfe6da}
  .cmt.reply{margin-left:22px;background:#fbfcfd;border-left:2px solid var(--line)}
  .cmt-act{display:flex;gap:12px;margin-top:6px}
  .cmt-act span{font-size:11.5px;color:var(--muted);cursor:pointer}
  .cmt-act span:hover{color:var(--green)}
  .reply-box{margin-top:6px;display:flex;gap:6px}
  .reply-box textarea{flex:1;padding:6px 9px;border:1px solid var(--line);border-radius:6px;font-family:inherit;font-size:12.5px;resize:vertical;min-height:32px}
  .post-stat{font-size:12.5px;color:var(--muted);margin:2px 0 12px;display:flex;align-items:center;gap:8px}
  .post-stat .likebtn{cursor:pointer;color:var(--green);font-weight:700;border:1px solid #cfe6da;background:#e7f3ec;border-radius:6px;padding:2px 10px}
  .pconf{background:#fdeceb;color:var(--red);border-radius:8px;padding:9px 12px;margin-bottom:10px;font-size:13px;font-weight:600;max-width:920px}
  .ptable{border-collapse:collapse;width:100%;max-width:1100px;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  .ptable th{text-align:left;font-size:11.5px;color:var(--muted);text-transform:uppercase;padding:9px 12px;border-bottom:1px solid var(--line);font-weight:700}
  .ptable td{padding:9px 12px;border-top:1px solid #f2f3f5;font-size:13px;vertical-align:top}
  .ptable td.port{font-weight:700}
  .ptable td.muted{color:var(--muted)}
  .ptable tr.clickable{cursor:pointer} .ptable tr.clickable:hover td{background:#fafbfc}
  .ptable tr.sel td{background:#f1f7f3}
  .ptable .up{color:var(--green);font-weight:700} .ptable .down{color:var(--muted)}
  .ptable .pid{color:var(--muted);font-size:11.5px}
  .ptable .cmd{color:var(--muted);font-size:11.5px;font-family:ui-monospace,Consolas,monospace;max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block}
  .ptable .del{color:var(--red);cursor:pointer;font-size:12px}
  .pbtn{font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:12px;border:1px solid var(--line);cursor:pointer;margin-right:4px;font-family:inherit}
  .pbtn.start{background:#e7f3ec;color:#1f7a44;border-color:#bcdcc7}
  .pbtn.stop{background:#fdecec;color:#b23b3b;border-color:#f0cdcd}
  .pbtn:disabled{opacity:.55;cursor:default}
  .pform{display:flex;gap:8px;align-items:center;margin-top:16px;flex-wrap:wrap;max-width:1100px}
  .pform-h{font-size:12px;color:var(--muted);font-weight:700;width:100%}
  .pform select,.pform input{padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;font-family:inherit}
  .pform input.grow{flex:1;min-width:120px}
  .pdet-h{font-size:11.5px;color:var(--muted);font-weight:700;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.02em}
  .ptable .reg{color:var(--green);cursor:pointer;font-size:12px;font-weight:700;white-space:nowrap}
  .tbadge{display:inline-block;background:#eef1fb;color:#3a52a8;border-radius:20px;padding:1px 8px;font-size:11px;margin-right:4px;font-weight:700}
  .tbadge.gold{background:#fdf3d6;color:#7a5f12} .tbadge.green{background:#e7f3ec;color:#1f7a44} .tbadge.gray{background:#f1f3f6;color:var(--muted)} .tbadge.red{background:#fdecec;color:#b33a3a}
  .ptable .reg-cell select,.ptable .reg-cell input,.ptable .reg-cell button{font-size:12px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;font-family:inherit;margin-right:5px}
  .ptable .reg-cell .ireg-label{width:120px}
  .ptable .reg-cell button{background:var(--green);color:#fff;border:none;cursor:pointer}
  .datebar{display:flex;gap:8px;overflow-x:auto;padding:2px;flex:0 0 auto;margin-bottom:12px}
  .datechip{flex:0 0 auto;padding:7px 14px;border:1px solid var(--line);border-radius:20px;background:var(--card);cursor:pointer;font-size:12.5px;font-weight:600;white-space:nowrap}
  .datechip:hover{background:#f1f3f6}
  .datechip.active{background:#e7f3ec;border-color:#bcdcc7}
  .datechip .cnt{margin-left:6px;color:var(--muted);font-weight:700;font-size:11px}
  .wk-wrap{display:flex;flex-direction:column;flex:1;min-height:0}
  .wk-body{flex:1;min-height:0;display:flex;gap:12px}
  .wk-nav{width:190px;flex:0 0 190px;min-height:0;overflow-y:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:6px}
  .wk-item{padding:8px 10px;border-radius:7px;cursor:pointer;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .wk-item:hover{background:#f1f3f6}
  .wk-item.active{background:#e7f3ec;font-weight:700}
  .wk-main{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  .wk-h{padding:12px 16px;border-bottom:1px solid var(--line);font-weight:700;font-size:13.5px;display:flex;align-items:center;gap:8px}
  .wk-meta{margin-left:auto;font-weight:400}
  .wk-scroll{flex:1;overflow-y:auto;padding:16px 18px;font-size:14px;line-height:1.75}
  .wk-scroll .mh{font-size:15px;margin:14px 0 5px}
  .stream-col{display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.5}
  .msg.pm{align-self:flex-end;background:#eef2fb;border:1px solid #d6def0}
  .msg.final{align-self:stretch;max-width:none;background:#f6faf7;border:1px solid #cfe6da}
  .wk-side{width:400px;flex:0 0 400px;display:flex;flex-direction:column;min-height:0}
  .wk-side .side-h{font-size:12px;color:var(--muted);font-weight:700;margin:0 2px 8px}
  @media(max-width:1200px){.wk-side{width:320px;flex-basis:320px}.wk-nav{width:150px;flex-basis:150px}}
  .kadd{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
  .kadd input,.kadd select{padding:6px 9px;border:1px solid var(--line);border-radius:6px;font:inherit;font-size:13px;background:#fff}
  .kadd #kadd-title{flex:1;min-width:180px}
  .kanban{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;align-items:start;margin-bottom:6px}
  .kcol{background:#f1f3f6;border:1px solid var(--line);border-radius:10px;padding:8px}
  .kcol.late{background:#fdf1f1;border-color:#f0caca}
  .kcol h3{margin:2px 4px 8px;font-size:12.5px;display:flex;align-items:center;gap:6px}
  .kcol h3 .n{color:var(--muted);font-weight:700;font-size:11px}
  .kcol.late h3{color:var(--red)}
  .kcard{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:7px;font-size:12.5px;line-height:1.45}
  .kcard.late{border-color:#f0caca}
  .kcard .kt{font-weight:600}
  .kcard .kn{color:#555b64;margin-top:3px;font-size:12px}
  .kcard .kf{display:flex;align-items:center;gap:6px;margin-top:6px;font-size:11px;color:var(--muted);flex-wrap:wrap}
  .kcard .kdue{color:var(--ink)}
  .kcard.late .kdue{color:var(--red);font-weight:700}
  .kcard .kmv{margin-left:auto;display:flex;gap:4px}
  .kcard .kmv span{cursor:pointer;padding:1px 6px;border:1px solid var(--line);border-radius:5px;background:#fff}
  .kcard .kmv span:hover{border-color:var(--green);color:var(--ink)}
  .col-empty{color:var(--muted);font-size:12px;text-align:center;padding:8px 0}
  .report{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;max-width:920px;margin-bottom:18px;font-size:14px;line-height:1.75}
  .report .mh{font-size:15px;margin:14px 0 5px}
  .wiki{flex:1;min-width:0;min-height:0;overflow-y:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .wiki-body{font-size:13.5px;line-height:1.7;color:#2b2f36}
  .wiki-body .mh{font-size:15px;margin:14px 0 5px}
  .wiki-body .mgap{height:9px}
  .lab-intro{margin-bottom:18px;color:#626975;font-size:13px;line-height:1.6}
  .lab-researchers{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
  .lab-researchers button{background:#fff;color:#424955;border:1px solid var(--line);padding:10px 18px}
  .lab-researchers button[aria-pressed="true"]{background:#e7f3ec;border-color:#9ccbb0;color:#17633e;font-weight:700}
  .lab-meta{font-size:12px;color:#626975;line-height:1.6;margin-bottom:16px}
  .lab-tabs{display:flex;gap:22px;border-bottom:1px solid var(--line);margin-bottom:20px;flex-wrap:wrap}
  .lab-tabs a{padding:0 2px 11px;color:#626975;font-size:14px;border-bottom:2px solid transparent}
  .lab-tabs a[aria-current="page"]{border-color:var(--green);color:#17633e;font-weight:700}
  .lab-content{flex:1;min-height:0;overflow-y:auto}
  .lab-req{max-width:760px;display:flex;flex-direction:column;gap:8px}
  .lab-req input,.lab-req textarea{padding:9px 12px;border:1px solid var(--line);border-radius:8px;font:inherit;font-size:13.5px;background:#fff;resize:vertical}
  .lab-req-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
  .lab-req-item{max-width:760px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;line-height:1.6}
  .lab-req-item .tbadge{margin-right:8px}
  .lab-req-meta{color:var(--muted);font-size:11.5px}
  .lab-req-detail{color:#555b64;font-size:12.5px;white-space:pre-wrap;margin-top:4px}
  .lab-req-err{color:var(--red);font-size:12px;margin-top:4px}
  .lab-reading{display:grid;grid-template-columns:200px minmax(0,1fr);gap:28px;align-items:start}
  .lab-index{position:sticky;top:0;padding:8px 0;max-height:100%;overflow-y:auto}
  .lab-label{font-size:11px;letter-spacing:.06em;color:#626975;font-weight:700;margin:0 0 12px}
  .lab-index a{display:block;padding:10px 12px;border-radius:7px;font-size:13px;line-height:1.5;color:#505864}
  .lab-index a[aria-current="page"]{background:#e7f3ec;color:#17633e;font-weight:700}
  .lab-toc{margin-top:28px;border-top:1px solid var(--line);padding-top:18px}
  .lab-toc button{display:block;text-align:left;width:100%;background:none;color:#626975;padding:7px 12px;font-size:12px;line-height:1.5}
  .lab-toc button:hover,.lab-toc button:focus-visible{background:#e7f3ec;color:#17633e}
  .lab-toc button.read{color:#17633e}
  .lab-toc button.on{background:#e7f3ec;color:#17633e;font-weight:700;box-shadow:inset 3px 0 0 var(--green)}
  .lab-article{background:#fff;border:1px solid var(--line);border-radius:14px;padding:32px 40px;min-width:0;max-width:920px}
  .lab-article h1{font-size:28px;line-height:1.4;letter-spacing:-.04em;margin:8px 0 16px;word-break:keep-all;overflow-wrap:anywhere}
  .lab-article h2{font-size:19px;line-height:1.5;margin:0 0 16px;letter-spacing:-.02em;color:var(--ink)}
  .lab-article .md{font-size:15px;line-height:1.9;overflow-wrap:anywhere;color:#373f48}
  .lab-article .md li{margin:7px 0;padding-left:4px}
  .lab-article .md a{color:#176b49;text-decoration:underline;text-underline-offset:3px}
  .lab-article .md .mh{font-size:16px;margin:18px 0 8px}
  .lab-section{padding-top:28px;margin:28px 0 0;border-top:1px solid var(--line);scroll-margin-top:20px}
  .lab-section.summary-section{background:#f0f7f3;border:1px solid #d4e8dc;border-radius:10px;padding:22px;margin-top:24px}
  .lab-media{margin:28px 0 0}
  .lab-media video,.lab-media img{display:block;width:100%;max-height:380px;object-fit:contain;background:#171d26;border-radius:10px}
  .lab-media figcaption{font-size:12px;color:#626975;margin-top:9px}
  .lab-content>.wiki{max-width:980px;padding:28px 32px;overflow:visible}
  .lab-content .wiki-body{font-size:15px;line-height:1.9}
  .lab-content .wiki-body .mh{font-size:18px;margin-top:24px}
  .lab-content .wiki-body li{margin:14px 0}
  .lab-content>.props{max-height:none;max-width:980px}
  .lab-content .prop{padding:20px;font-size:14px;line-height:1.8}
  .lab-content>.chat{height:100%;max-width:980px;min-height:350px}
  .lab-content .empty{background:#fff;border:1px dashed var(--line);border-radius:12px;line-height:1.8}
  @media(max-width:1100px){.lab-reading{grid-template-columns:165px minmax(0,1fr);gap:16px}.lab-article{padding:26px}}
  @media(max-width:760px){
    .app:has(#lab-top){flex-direction:column}
    .app:has(#lab-top)>aside{width:100%;height:auto;flex:none;position:static}
    .app:has(#lab-top)>aside .brand,.app:has(#lab-top)>aside .sec-label,.app:has(#lab-top)>aside .rooms{display:none}
    .app:has(#lab-top)>aside nav{display:flex;flex-wrap:wrap;padding:4px}
    .app:has(#lab-top)>aside .nav-item{padding:7px 10px;font-size:12px}
    .body:has(#lab-top){min-height:0}
    .body:has(#lab-top) main{padding:16px 12px}
    .lab-reading{display:block}.lab-index{position:static;margin-bottom:16px;max-height:none}.lab-toc{display:none}
    .lab-article{padding:22px 18px}.lab-article h1{font-size:23px}.lab-tabs{gap:14px}.lab-tabs a{font-size:13px}
    .lab-researchers{gap:6px}.lab-researchers button{padding:8px 10px;font-size:12px}
  }
  .props{display:flex;flex-direction:column;gap:8px;max-height:46%;overflow-y:auto;margin-bottom:10px;flex:0 0 auto}
  .prop{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:9px 12px;font-size:12.5px;line-height:1.55}
  .prop .pt{font-weight:700;margin-bottom:3px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .prop .pb{color:#3a3f47}
  .prop .pa{display:flex;gap:10px;margin-top:5px}
  .prop .pa span{font-size:11.5px;color:var(--muted);cursor:pointer}
  .prop .pa span:hover{color:var(--green)}
  .prop.done{opacity:.55}
  .kv{font-size:13px;line-height:1.7;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .kv b{display:inline-block;min-width:92px;color:var(--muted);font-weight:600}
  /* ── 화면 다듬기 점검표(2026-10-10, 랩실 Taste 검토) ── */
  /* 키보드 Tab으로 옮겨 다닐 때 지금 어디에 있는지 테두리로 보인다(마우스 클릭 때는 안 보임) */
  :focus-visible{outline:2px solid var(--green);outline-offset:2px}
  aside :focus-visible{outline-color:#3fb37f;outline-offset:-2px}
  /* 프로젝트 옆 '관리 제외(x)'는 마우스를 올릴 때만 보였다 — 키보드로 그 줄에 와도 보이게 */
  aside .room-item:focus-within .rx{display:block}
  /* 마우스를 올리면 버튼이 살짝 어두워진다(눌러지는 것임을 알림) */
  button:hover:not(:disabled){filter:brightness(.92)}
  button.ghost:hover:not(:disabled){filter:none;background:var(--bg)}
  /* 숫자 폭을 고르게 — 개수·비용·날짜가 바뀌어도 글자가 흔들리지 않고 표에서 줄이 맞는다.
     긴 글(게시글·보고서·랩실 문서)은 원래 숫자 모양이 읽기 편해 되돌린다 */
  body{font-variant-numeric:tabular-nums}
  .post-body,.report,.wk-scroll,.lab-article .md,.wiki-body,.cmt,.msg{font-variant-numeric:normal}
  /* 불러오는 중 — 글자 앞에 작은 회전 표시 */
  .loading{color:var(--muted);display:flex;align-items:center;justify-content:center;gap:8px}
  .loading::before{content:"";width:12px;height:12px;border:2px solid var(--line);border-top-color:var(--muted);border-radius:50%;animation:spin .8s linear infinite;flex:0 0 12px}
  @keyframes spin{to{transform:rotate(360deg)}}
  /* 컴퓨터에서 '움직임 줄이기'를 켜 두면 돌지 않는다 */
  @media (prefers-reduced-motion: reduce){.loading::before{animation:none}}
  /* 화면에는 안 보이고 화면 읽기 프로그램만 읽는 글자 */
  .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
  /* 환경 세팅 — 제안 비교·승인 */
  .env-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .env-run{margin:10px 0}
  .env-err,.env-reason{color:var(--amber);margin-top:4px}
  #envset h3{font-size:.95em;margin:14px 0 4px}
  .env-item{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0}
  .env-item input[type=checkbox]{width:16px;height:16px;vertical-align:-2px;margin-right:4px}
  .env-meta{color:var(--muted);font-size:.9em;margin:2px 0}
  .env-why{margin:4px 0}
  .env-diff .dh{color:var(--muted);font-size:.85em;margin-top:6px}
  .env-diff pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;margin:2px 0;font-size:.88em;max-height:240px;overflow:auto}
  .env-actions{margin-top:10px;display:flex;gap:8px}
</style></head><body>
<div class="app">
  <aside>
    <div class="brand">ohmyPM</div>
    <nav>
      <div class="nav-item" data-nav="dashboard" onclick="go('#/dashboard')">대시보드</div>
      <div class="nav-item" data-nav="board" onclick="go('#/board')">게시판</div>
      <div class="nav-item" data-nav="weekly" onclick="go('#/weekly')">주간보고</div>
      <div class="nav-item" data-nav="lab" onclick="go('#/lab')">랩실</div>
      <div class="nav-item" data-nav="agents" onclick="go('#/agents')">에이전트</div>
      <div class="nav-item" data-nav="ports" onclick="go('#/ports')">포트</div>
    </nav>
    <div class="sec-label">프로젝트 룸</div>
    <div class="rooms" id="rooms"></div>
  </aside>

  <div class="body">
    <header>
      <h1 id="hdr-title">대시보드</h1>
      <div class="summary" id="hdr-summary"></div>
      <div class="hstatus" id="hdr-status" hidden></div>
      <div class="actions" id="hdr-actions"></div>
    </header>
    <main id="view"><div class="empty loading">불러오는 중…</div></main>
  </div>
</div>
<script>
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const escAttr = s => esc(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
// 가벼운 마크다운 렌더 — 에이전트 답에 ## 제목·**굵게**·- 목록·`코드`가 섞여 온다(외부 lib 없이)
function md(src){
  const e = s => s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const inl = s => {
    const links = [];
    let t = (s||'').replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, href) => {
      const safe = /^https:\/\//.test(href) || /^#\/(lab|weekly|room)(\/|$)/.test(href);
      if (!safe) return text;
      const ext = href.startsWith('https://');
      const rel = ext ? ' target="_blank" rel="noopener noreferrer"' : '';
      links.push(`<a href="${href.replace(/"/g,'%22')}"${rel}>${e(text)}</a>`);
      return `\u0000${links.length - 1}\u0000`;
    });
    t = e(t).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+?)\*\*/g,'<strong>$1</strong>');
    return t.replace(/\u0000(\d+)\u0000/g, (m, i) => links[Number(i)]);
  };
  const out=[]; let list=false; let rows=[];
  // 표 — '| 가 | 나 |' 줄이 이어지면 모았다가 한 번에 <table>로. 둘째 줄이 '|---|'면 첫 줄이 머리글.
  // 칸 안의 '\|'와 `코드` 속 '|'는 칸 나눔이 아니다 — 잠시 \u0001로 숨겼다가 나눈 뒤 되돌린다.
  const cells = r => r.trim().replace(/^\|/,'').replace(/\|$/,'')
    .replace(/\\\|/g,'\u0001').replace(/`[^`]*`/g, c=>c.replace(/\|/g,'\u0001'))
    .split('|').map(c=>inl(c.trim().replace(/\u0001/g,'|')));
  const flushTable = ()=>{
    if(!rows.length) return;
    let head = null;
    if(rows.length > 1 && /^\s*\|?\s*:?-{2,}/.test(rows[1])){ head = cells(rows[0]); rows = rows.slice(2); }
    out.push('<div class="md-table"><table>'+
      (head ? '<thead><tr>'+head.map(c=>`<th>${c}</th>`).join('')+'</tr></thead>' : '')+
      '<tbody>'+rows.map(r=>'<tr>'+cells(r).map(c=>`<td>${c}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>');
    rows = [];
  };
  const close=()=>{ if(list){ out.push('</ul>'); list=false; } };
  for(const raw of (src||'').split('\n')){
    const line = raw.replace(/\s+$/,''); let m;
    // 표 시작은 '|'로 열고 닫힌 줄만. 이미 표 안이면 끝 '|'를 빠뜨린 줄도 같은 표로 받는다.
    if(/^\s*\|.*\|$/.test(line) || (rows.length && /^\s*\|/.test(line))){ close(); rows.push(line); continue; }
    flushTable();
    if(m = line.match(/^(#{1,6})\s+(.*)$/)){ close(); out.push(`<div class="mh">${inl(m[2])}</div>`); }
    else if(m = line.match(/^\s*[-*]\s+(.*)$/)){ if(!list){ out.push('<ul>'); list=true; } out.push(`<li>${inl(m[1])}</li>`); }
    else if(!line.trim()){ close(); out.push('<div class="mgap"></div>'); }
    else { close(); out.push(`<div>${inl(line)}</div>`); }
  }
  flushTable(); close();
  return out.join('');
}
const todayStr = () => new Date().toISOString().slice(0,10);
const fmtTs = s => (s||'').slice(5,16);
// 비용은 달러가 아니라 '세션'으로 보인다 — 1세션 = 맥스 100달러 요금제 5시간 한도(SESSION_USD 달러어치),
// 하루 = 4세션. 서버가 .env 값을 아래 자리에 채워 준다.
const SESSION_USD = __SESSION_USD__;
const fmtCost = c => {
  if(!(c||c===0)) return '-';
  const s = Number(c) / SESSION_USD;
  if(s < 1){ const pct = s*100; return `1세션의 ${pct < 10 ? pct.toFixed(1) : Math.round(pct)}%`; }
  return `${s.toFixed(1)}세션` + (s >= 4 ? ` (약 ${(s/4).toFixed(1)}일)` : '');
};
// 주기적으로 다시 그리는 목록은 내용이 바뀔 때만 갈아 끼운다 — 매번 갈면 Tab으로 옮겨 둔 위치(포커스)와
// 스크롤이 날아간다. 바꿨으면 true.
const setHTML = (el, html) => {
  if(el.dataset.source === html) return false;
  el.innerHTML = html; el.dataset.source = html; return true;
};
const getJ = (url) => fetch(url).then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); });   // 404 등은 예외 → 호출부 catch가 빈 값으로 처리
const postJ = (url, body) => fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
  body: body===undefined ? undefined : JSON.stringify(body)}).then(async r=>{
    // 서버가 죽어 'Internal Server Error' 같은 글자를 주면 JSON이 아니다 — 연결 실패와 구별해 HTTP 번호로 알린다.
    let j; try{ j = await r.json(); }catch(e){ j = {}; }
    if(!r.ok){ j.ok = false; j.status = r.status; j.error = j.error || j.detail || `서버 오류 (HTTP ${r.status})`; }
    return j;
  }).catch(()=>({ok:false, offline:true, error:'서버에 연결하지 못했습니다'}));

// ── 확인/알림 모달 ──────────────────────────────────────
function appModal({title, body, okText='확인', cancel=true, danger=false}){
  return new Promise(res=>{
    const bg = document.createElement('div'); bg.className = 'modal-bg';
    bg.innerHTML = '<div class="modal"><div class="m-title"></div><div class="m-body"></div>'+
      '<div class="m-btns">'+(cancel?'<button class="m-cancel">취소</button>':'')+
      '<button class="m-ok'+(danger?' danger':'')+'"></button></div></div>';
    bg.querySelector('.m-title').textContent = title || '';
    bg.querySelector('.m-body').textContent = body || '';
    bg.querySelector('.m-ok').textContent = okText;
    const done = v=>{ bg.remove(); document.removeEventListener('keydown', escK); res(v); };
    const escK = e=>{ if(e.key==='Escape') done(false); };
    bg.addEventListener('click', e=>{ if(e.target===bg) done(false); });
    bg.querySelector('.m-ok').onclick = ()=>done(true);
    const c = bg.querySelector('.m-cancel'); if(c) c.onclick = ()=>done(false);
    document.addEventListener('keydown', escK);
    document.body.appendChild(bg);
    bg.querySelector('.m-ok').focus();
  });
}
const appConfirm = o => appModal(o);
const appAlert = (title, body) => appModal({title, body, cancel:false});
// 실패 알림의 본문 — 서버가 준 이유 + '그럼 뭘 하면 되나' 한 줄을 붙인다.
const errMsg = r => {
  const why = (r && r.error) || '서버가 이유를 알려 주지 않았습니다.';
  const next = r && r.offline
    ? 'ohmyPM 서버가 꺼져 있을 수 있습니다. scripts 폴더의 run_ohmypm.cmd로 다시 켠 뒤 이 화면을 새로고침해 주세요.'
    : '잠시 후 다시 시도해 주세요. 계속되면 logs 폴더의 server_console.log에 자세한 이유가 남습니다.';
  return why + '\n\n' + next;
};

let PROJECTS = [];                      // 마지막 로드 캐시
let pollTimer = null;                   // 뷰별 자동 새로고침 타이머(하나만)
let tickTimer = null;                   // 토론 카운트다운(1초)
let CUR_ROOM = null;
let portEditing = false;

let REPORTED = new Set();               // 가장 최근 주간보고에 몫이 있는 프로젝트 path
async function loadData(){
  const [projects, weekly] = await Promise.all([getJ('/api/projects').catch(()=>[]), getJ('/api/weekly').catch(()=>[])]);
  PROJECTS = projects;
  REPORTED = new Set(weekly.length ? weekly[0].projects.map(x=>x.project) : []);
  renderSidebar();
}
const nameOfPath = p => (PROJECTS.find(x=>x.path===p)||{}).name || p;

// ── 사이드바 ───────────────────────────────────────────
function renderSidebar(){
  const cur = decodeURIComponent(location.hash);
  // 초록 점 = 가장 최근 주간보고에 몫이 있는 프로젝트(2026-10-10 사용자 요청) — 그 프로젝트들이 위로
  const ordered = PROJECTS.slice().sort((a,b)=>(REPORTED.has(b.path)-REPORTED.has(a.path)) || a.name.localeCompare(b.name,'ko'));
  document.getElementById('rooms').innerHTML = ordered.map(p=>{
    const active = cur === '#/room/'+p.path ? ' active':'';
    return `<div class="room-item${active}" data-room="${escAttr(p.path)}" title="${escAttr(p.path)}">`+
           (REPORTED.has(p.path) ? '<span class="dot on" title="최근 주간보고에 이 프로젝트 몫이 있음"></span><span class="sr">최근 주간보고 있음, </span>'
                                 : '<span class="dot"></span>')+`<span class="rname">${esc(p.name)}</span>`+
           `<span class="rx" data-exclude="${escAttr(p.path)}" title="관리 제외">x</span></div>`;
  }).join('') || '<div style="color:#9aa0aa;font-size:12px;padding:8px 18px">스캔을 눌러보세요</div>';
  document.querySelectorAll('[data-nav]').forEach(el=>el.classList.remove('active'));
  const view = (cur.startsWith('#/board') || cur.startsWith('#/post')) ? 'board'
             : cur.startsWith('#/weekly') ? 'weekly'
             : cur.startsWith('#/lab') ? 'lab'
             : cur.startsWith('#/agents') ? 'agents'
             : cur.startsWith('#/ports') ? 'ports'
             : (cur.startsWith('#/room') ? null : 'dashboard');
  if(view) document.querySelector(`[data-nav="${view}"]`)?.classList.add('active');
}

// ── 헤더: 제목 · 요약 · 상태줄 · 버튼(뷰마다 다르게) ─────────────
function setHeader(title, opts){
  opts = opts || {};
  document.getElementById('hdr-title').textContent = title;
  const sum = document.getElementById('hdr-summary');
  sum.hidden = !opts.summary; sum.innerHTML = opts.summary || '';
  const st = document.getElementById('hdr-status');
  st.hidden = !opts.status; st.innerHTML = opts.status || '';
  const act = document.getElementById('hdr-actions');
  act.hidden = !(opts.buttons && opts.buttons.length);
  act.innerHTML = (opts.buttons||[]).map(b => b.html ? b.html :
    `<button${b.id?` id="${b.id}"`:''}${b.ghost?' class="ghost"':''}${b.danger?' class="danger"':''}${b.disabled?' disabled':''} onclick="${b.onclick}">${esc(b.label)}</button>`).join('');
}
function setStatus(html){ const st=document.getElementById('hdr-status'); st.hidden = !html; st.innerHTML = html||''; }

// ── 대시보드 ───────────────────────────────────────────
async function renderDashboard(){
  setHeader('대시보드', {summary:'<span>불러오는 중…</span>',
    buttons:[{id:'btn-scan', label:'스캔(설치)', onclick:'doScan()'}]});
  document.getElementById('view').innerHTML = '<div class="empty loading">불러오는 중…</div>';
  clearInterval(pollTimer);
  const [agents, weekly, sess] = await Promise.all([
    getJ('/api/agents').catch(()=>[]), getJ('/api/weekly').catch(()=>[]), getJ('/api/board/session').catch(()=>null)]);
  const byPath = {}; agents.forEach(a=>byPath[a.project]=a);
  const installed = PROJECTS.filter(p=>p.installed).length;
  const lastW = weekly.length ? weekly[0].date : '없음';
  const lastS = sess && sess.started_at ? (sess.started_at.slice(5,16)+' · '+sessionLabel(sess)) : '없음';
  setHeader('대시보드', {summary:
      `<span>프로젝트 <b>${PROJECTS.length}</b></span><span>설치 <b>${installed}</b></span>`+
      `<span>마지막 주간보고 <b>${esc(lastW)}</b></span><span>마지막 토론 <b>${esc(lastS)}</b></span>`,
    buttons:[{id:'btn-scan', label:'스캔(설치)', onclick:'doScan()'}]});
  // 초록 점 = 가장 최근 주간보고에 몫이 있는 프로젝트(2026-10-10 사용자 요청) — 그 프로젝트들이 위로
  const ordered = PROJECTS.slice().sort((a,b)=>(REPORTED.has(b.path)-REPORTED.has(a.path)) || a.name.localeCompare(b.name,'ko'));
  const cards = ordered.map(p=>{
    const a = byPath[p.path] || {};
    return `<div class="card"><h3>${esc(p.name)}`+
      `<span class="badge ${p.installed?'on':'off'}">${p.installed?'설치됨':'미설치'}</span>`+
      `<span class="open" data-room="${escAttr(p.path)}">룸 열기</span></h3>`+
      `<div class="line">담당 <b>${esc(a.name||p.name)}</b> · 점수 ${a.points??0}${a.last_delta!=null?` (최근 ${a.last_delta>=0?'+':''}${a.last_delta})`:''}</div>`+
      (a.note_head?`<div class="line" style="color:var(--muted)">${esc(a.note_head)}</div>`:'')+
      `</div>`;
  }).join('');
  document.getElementById('view').innerHTML =
    `<section><h2>프로젝트</h2><div class="grid">${cards||'<div class="empty">관리 대상 없음 — 스캔을 눌러보세요</div>'}</div></section>`;
}

async function doScan(){
  const b = document.getElementById('btn-scan'); if(b){ b.disabled=true; b.textContent='스캔 중…'; }
  const r = await postJ('/api/scan');
  await loadData();
  if(r.projects===undefined){ appAlert('스캔 실패', errMsg(r)); }
  else appAlert('스캔 완료', `프로젝트 ${r.projects}개\n새로 설치 ${r.installed} · 이미 설치 ${r.already} · 자기 자신 제외 ${r.self_skipped}`+
    (r.errors&&r.errors.length?`\n실패 ${r.errors.length}: ${r.errors.map(e=>e.name).join(', ')}`:''));
  route();
}

// ── 채팅 공용 ─────────────────────────────────────────
function chatMarkup(ph){
  return `<div class="chat"><div class="stream" id="stream"><div class="chat-empty loading">불러오는 중…</div></div>`+
    `<div class="composer"><textarea id="msg-input" rows="1" placeholder="${escAttr(ph||'')}" autocomplete="off"></textarea></div></div>`;
}
function bindChat(room, agentRoom, sender){
  const input = document.getElementById('msg-input');
  const grow = ()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,140)+'px'; };
  input.onkeydown = e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); (sender||sendMsg)(room, agentRoom); }};
  input.addEventListener('input', grow);
  input.focus({preventScroll:true});
  loadMessages(room, false, agentRoom);
  clearInterval(pollTimer);
  pollTimer = setInterval(()=>loadMessages(room, true, agentRoom), 4000);
}
async function loadMessages(room, silent, agentRoom){
  let msgs;
  try{ msgs = await getJ('/api/messages?room='+encodeURIComponent(room)); }catch(e){ return; }
  const stream = document.getElementById('stream');
  if(!stream) return;
  const atBottom = stream.scrollHeight - stream.scrollTop - stream.clientHeight < 40;
  let html = msgs.length ? msgs.map(m=>{
    const mine = m.author === 'user';
    return `<div class="msg ${mine?'user':'agent'}">`+(mine?'':`<div class="who">${esc({agent:'담당',pm:'PM'}[m.author]||m.author)}</div>`)+
           `<div class="md">${md(m.body)}</div><div class="ts">${esc(fmtTs(m.created_at))}</div></div>`;
  }).join('') : '<div class="chat-empty">아직 대화가 없습니다. 첫 메시지를 남겨보세요.</div>';
  if(agentRoom && msgs.length && msgs[msgs.length-1].author === 'user')
    html += pendingMarkup(room, msgs[msgs.length-1], '에이전트');
  if(setHTML(stream, html) && (!silent || atBottom)) stream.scrollTop = stream.scrollHeight;
}
async function sendMsg(room, agentRoom){
  const input = document.getElementById('msg-input');
  const body = input.value.trim(); if(!body) return;
  input.value = ''; input.style.height = 'auto';
  await postJ('/api/messages', {room, author:'user', body});
  await loadMessages(room, false, agentRoom);
}
const PENDING_STUCK_MIN = 5;
function pendingMarkup(room, lastMsg, who){
  const asked = new Date((lastMsg.created_at||'').replace(' ','T'));
  const mins = isNaN(asked) ? 0 : Math.floor((Date.now() - asked.getTime())/60000);
  if(mins < PENDING_STUCK_MIN) return `<div class="msg pending">${who}이 확인하고 답하는 중…</div>`;
  return `<div class="msg pending stuck">${mins}분째 답이 없습니다 — 답변이 중간에 끊겼을 수 있습니다`+
         `<button class="retry" onclick="retryRoomReply('${encodeURIComponent(room)}')">다시 요청</button></div>`;
}
async function retryRoomReply(room){
  room = decodeURIComponent(room);
  const r = await postJ('/api/room-retry', {room});
  if(!r.ok){ appAlert('다시 요청 실패', errMsg(r)); return; }
  document.querySelectorAll('.msg.pending').forEach(el=>{ el.classList.remove('stuck'); el.textContent = '다시 요청했습니다 — 담당이 답하는 중…'; });
}

// ── 게시판: 토론 세션 + 글 목록 ─────────────────────────────
const PHASE_LABEL = {write:'글쓰기', browse:'둘러보기·댓글', feedback:'글쓴이 반응', followup:'대대댓글', reflect:'복기'};
const STATUS_LABEL = {running:'진행 중', stopping:'중지하는 중', done:'끝남', stopped:'중지됨', failed:'실패'};
function sessionLabel(s){ return STATUS_LABEL[s.status]||s.status; }
let SESSION = null, SESSION_END = 0;

function renderBoard(){
  setHeader('게시판', {buttons: boardButtons(null)});
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:12px">토론 시작을 누르면 담당 에이전트들이 정한 시간 동안 글을 쓰고, 서로 읽고 댓글·좋아요를 남기고, 글쓴이가 답합니다. 끝나면 각 담당이 받은 반응을 복기해 \'배운 것\'으로 남깁니다.</div>'+
    '<div id="board"><div class="empty loading">불러오는 중…</div></div>';
  fillBoardList();
  clearInterval(pollTimer);
  pollTimer = setInterval(fillBoardList, 5000);
}
function boardButtons(s){
  const live = s && (s.status==='running' || s.status==='stopping');
  if(live) return [{id:'btn-stop', label: s.status==='stopping'?'중지하는 중…':'중지', onclick:'stopSession()', danger:true, disabled: s.status==='stopping'}];
  return [{html:'<select id="bs-min"><option value="10">10분</option><option value="30" selected>30분</option><option value="60">60분</option></select>'},
          {id:'btn-start', label:'토론 시작', onclick:'startSession()'}];
}
function statusLine(s){
  if(!s) return '';
  const st = s.stats||{};
  const sum = `글 ${st.posted??0} · 댓글 ${st.commented??0} · 좋아요 ${st.liked??0} · 반응 ${st.reacted??0} · 복기 ${st.reflected??0} · 비용 ${fmtCost(st.cost_usd)}`;
  if(s.status==='running' || s.status==='stopping')
    return `<span class="live">토론 ${sessionLabel(s)}</span> · ${PHASE_LABEL[s.phase]||s.phase||''} · 남은 <b id="bs-left">--:--</b> · ${sum}`;
  return `마지막 토론 ${esc((s.started_at||'').slice(5,16))} · <b>${sessionLabel(s)}</b>(${s.minutes}분) · ${sum}`+(s.error?` · ${esc(s.error)}`:'');
}
function tickLeft(){
  const el = document.getElementById('bs-left'); if(!el) return;
  const left = Math.max(0, Math.round((SESSION_END - Date.now())/1000));
  el.textContent = String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');
}
async function fillBoardList(){
  let posts = [], s = null;
  try{ [posts, s] = await Promise.all([getJ('/api/posts'), getJ('/api/board/session').catch(()=>null)]); }catch(e){ return; }
  const box = document.getElementById('board');
  if(!box) return;
  const wasLive = SESSION && (SESSION.status==='running'||SESSION.status==='stopping');
  const isLive = s && (s.status==='running'||s.status==='stopping');
  SESSION = s;
  if(isLive) SESSION_END = Date.now() + (s.remaining_sec||0)*1000;
  if(!SESSION || wasLive !== isLive || !document.getElementById('bs-min') && !document.getElementById('btn-stop'))
    document.getElementById('hdr-actions').innerHTML = boardButtons(s).map(b=>b.html?b.html:
      `<button id="${b.id}"${b.danger?' class="danger"':''}${b.disabled?' disabled':''} onclick="${b.onclick}">${esc(b.label)}</button>`).join('');
  if(isLive && !document.getElementById('btn-stop')) document.getElementById('hdr-actions').innerHTML = boardButtons(s).map(b=>`<button id="${b.id}" class="danger"${b.disabled?' disabled':''} onclick="${b.onclick}">${esc(b.label)}</button>`).join('');
  setStatus(statusLine(s));
  clearInterval(tickTimer); if(isLive){ tickLeft(); tickTimer = setInterval(tickLeft, 1000); }
  if(!posts.length){ setHTML(box, '<div class="empty">아직 글이 없습니다 — 토론 시작을 누르면 담당들이 글을 올립니다</div>'); return; }
  setHTML(box, posts.map(p=>{
    const n = (p.comments||[]).length;
    const day = (p.day || p.created_at || '').slice(0,10);
    return `<div class="prow" onclick="go('#/post/${p.id}')"><span class="prow-t">${esc(p.title)}</span>`+
      `<span class="prow-meta">${esc(day)} · ${esc(p.author)} · 조회 ${p.views||0} · 좋아요 ${p.likes||0}${(p.dislikes||0)?' · 싫어요 '+p.dislikes:''} · 댓글 <span class="c">${n}</span></span></div>`;
  }).join(''));
}
async function startSession(){
  const minutes = parseInt((document.getElementById('bs-min')||{}).value||'30',10);
  const b = document.getElementById('btn-start'); if(b){ b.disabled=true; b.textContent='시작하는 중…'; }
  const r = await postJ('/api/board/session', {minutes});
  if(!r.ok){ appAlert('토론을 시작하지 못함', errMsg(r)); if(b){ b.disabled=false; b.textContent='토론 시작'; } }
  SESSION = null; fillBoardList();
}
async function stopSession(){
  const ok = await appConfirm({title:'토론 중지', okText:'중지', danger:true,
    body:'지금 돌고 있는 담당의 호출은 끝까지 가고, 새 호출만 멈춥니다. 끝난 뒤 복기는 하지 않습니다.'});
  if(!ok) return;
  const r = await postJ('/api/board/session/stop');
  if(!r.ok) appAlert('중지 실패', errMsg(r));
  SESSION = null; fillBoardList();
}

// ── 글 상세 ───────────────────────────────────────────
function renderPost(id){
  setHeader('게시판', {});
  document.getElementById('view').innerHTML = '<div id="post"><div class="empty loading">불러오는 중…</div></div>';
  clearInterval(pollTimer);
  fillPost(id);
}
async function fillPost(id){
  let p = {};
  try{ p = await getJ('/api/posts/'+encodeURIComponent(id)); }catch(e){}
  const box = document.getElementById('post');
  if(!box) return;
  if(!p || !p.id){ box.innerHTML = '<div class="back" onclick="go(\'#/board\')">← 게시판</div><div class="empty">글을 찾을 수 없습니다</div>'; return; }
  const day = (p.day || p.created_at || '').slice(0,10);
  const all = p.comments || [];
  const repliesOf = pid => all.filter(c=>c.parent_id===pid);
  const cmtHtml = (c, isReply) => {
    const mine = c.author === 'user';
    return `<div class="cmt${mine?' user':''}${isReply?' reply':''}"><span class="cmt-who">${mine?'나':esc(c.author)}</span>`+
      `<div class="md">${md(c.body)}</div><div class="cmt-act">`+
        `<span onclick="reactCmt(${c.id},'like','${id}')">좋아요 ${c.likes||0}</span>`+
        `<span onclick="reactCmt(${c.id},'dislike','${id}')">싫어요 ${c.dislikes||0}</span>`+
        (isReply?'':`<span onclick="replyTo(${c.id},'${id}')">답글</span>`)+
      `</div><div class="reply-box" id="reply-${c.id}"></div>`+
      repliesOf(c.id).map(r=>cmtHtml(r,true)).join('')+`</div>`;
  };
  const top = all.filter(c=>!c.parent_id);
  const cs = top.length ? top.map(c=>cmtHtml(c,false)).join('') : '<div class="cmt none">아직 댓글 없음 — 첫 댓글을 남겨보세요</div>';
  box.innerHTML =
    `<div class="back" onclick="go('#/board')">← 게시판</div>`+
    `<div class="post"><div class="post-h"><span class="post-title">${esc(p.title)}</span><span class="post-day">${esc(day)}</span></div>`+
      `<div class="post-stat">${esc(p.author)} · 조회 ${p.views||0} · 좋아요 <b>${p.likes||0}</b> <span class="likebtn" onclick="likePost('${id}')">좋아요</span> `+
        `· 싫어요 <b>${p.dislikes||0}</b> <span class="likebtn" onclick="dislikePost('${id}')">싫어요</span></div>`+
      `<div class="post-body md">${md(p.body)}</div><div class="cmts">${cs}</div>`+
      `<div class="cmt-form"><textarea id="cmt-input" rows="1" placeholder="댓글 달기…"></textarea><button onclick="postComment('${id}')">댓글</button></div></div>`;
  const ta = document.getElementById('cmt-input');
  ta.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); postComment(id); }});
}
async function postComment(id, parentId){
  const ta = document.getElementById(parentId ? 'reply-input-'+parentId : 'cmt-input');
  const body = ta.value.trim(); if(!body) return;
  ta.value = '';
  const payload = {author:'user', body}; if(parentId) payload.parent_id = parentId;
  await postJ('/api/posts/'+encodeURIComponent(id)+'/comments', payload);
  fillPost(id);
}
async function likePost(id){ await postJ('/api/posts/'+encodeURIComponent(id)+'/like'); fillPost(id); }
async function dislikePost(id){ await postJ('/api/posts/'+encodeURIComponent(id)+'/dislike'); fillPost(id); }
async function reactCmt(cid, reaction, postId){ await postJ('/api/comments/'+cid+'/react', {reaction}); fillPost(postId); }
function replyTo(cid, postId){
  const box = document.getElementById('reply-'+cid);
  if(!box || box.querySelector('textarea')){ if(box) box.innerHTML=''; return; }
  box.innerHTML = `<textarea id="reply-input-${cid}" rows="1" placeholder="답글…"></textarea><button onclick="postComment('${postId}', ${cid})">답글</button>`;
  const t = document.getElementById('reply-input-'+cid); if(t) t.focus();
}

// ── 주간보고 ───────────────────────────────────────────
// 옛 일간보고 구조(2026-10-10 사용자 요청): 날짜 → 프로젝트 → 가운데 PM↔담당 점검 대화,
// 오른쪽은 그 담당과 사용자가 직접 나누는 채팅(room=프로젝트 path — 프로젝트 화면과 같은 방).
let WEEKLY = [], WEEKLY_IDX = 0, WEEKLY_SEL = -1;   // WEEKLY_SEL: -1 = 전체 요약, 그 외 projects 인덱스
function renderWeekly(){
  setHeader('주간보고', {buttons:[{id:'btn-weekly', label:'주간보고 실행', onclick:'runWeekly()'}]});
  document.getElementById('view').innerHTML =
    '<div class="wk-wrap"><div class="datebar" id="w-datebar"><span class="loading">불러오는 중…</span></div>'+
    '<div class="wk-body"><div class="wk-nav" id="w-nav"></div>'+
    '<div class="wk-main" id="w-main"><div class="chat-empty loading">불러오는 중…</div></div>'+
    '<div class="wk-side" id="w-side"></div></div></div>';
  clearInterval(pollTimer); clearInterval(tickTimer);
  fillWeekly();
  tickTimer = setInterval(pollWeeklyJob, 5000);   // 채팅이 pollTimer를 쓰므로 작업 상태는 tickTimer로
}
async function pollWeeklyJob(){
  const j = await getJ('/api/jobs/weekly').catch(()=>null);
  const b = document.getElementById('btn-weekly'); if(!b) return;
  if(j && j.running){ b.disabled = true; b.textContent = '작성 중…'; setStatus(`주간보고 작성 중 (${esc((j.started_at||'').slice(11,16))} 시작) — PM이 담당들과 대화하느라 수십 분 걸릴 수 있습니다`); }
  else{
    if(b.disabled){ b.disabled = false; b.textContent = '주간보고 실행'; fillWeekly(); loadData(); }
    if(j && j.finished_at) setStatus(`마지막 실행 ${esc((j.finished_at||'').slice(5,16))} · ${j.ok?'완료':'실패'}${j.error?' · '+esc(j.error):''}${j.result&&j.result.cost_usd!=null?' · 비용 '+fmtCost(j.result.cost_usd):''}`);
  }
}
async function fillWeekly(){
  try{ WEEKLY = await getJ('/api/weekly'); }catch(e){ WEEKLY = []; }
  // 프로젝트 순서는 사이드바와 같게(이름순, 대소문자 무시)
  WEEKLY.forEach(d=>d.projects.sort((a,b)=>a.name.localeCompare(b.name,'ko')));
  const bar = document.getElementById('w-datebar'); if(!bar) return;
  pollWeeklyJob();
  if(!WEEKLY.length){
    bar.innerHTML = ''; document.getElementById('w-nav').innerHTML = '';
    document.getElementById('w-main').innerHTML = '<div class="chat-empty">아직 주간보고가 없습니다 — 오른쪽 위 버튼으로 실행하세요</div>';
    return;
  }
  if(WEEKLY_IDX >= WEEKLY.length) WEEKLY_IDX = 0;
  bar.innerHTML = WEEKLY.map((d,i)=>`<div class="datechip${i===WEEKLY_IDX?' active':''}" onclick="WEEKLY_IDX=${i};WEEKLY_SEL=-1;fillWeekly()">${esc(d.date)}<span class="cnt">${d.projects.length}</span></div>`).join('');
  const d = WEEKLY[WEEKLY_IDX];
  if(WEEKLY_SEL >= d.projects.length) WEEKLY_SEL = -1;
  document.getElementById('w-nav').innerHTML =
    `<div class="wk-item${WEEKLY_SEL===-1?' active':''}" onclick="openWeekly(-1)"><b>전체 요약</b></div>`+
    d.projects.map((p,i)=>`<div class="wk-item${WEEKLY_SEL===i?' active':''}" onclick="openWeekly(${i})">${esc(p.name)}</div>`).join('');
  openWeekly(WEEKLY_SEL);
}
async function openWeekly(i){
  WEEKLY_SEL = i;
  document.querySelectorAll('#w-nav .wk-item').forEach((el,k)=>el.classList.toggle('active', k===i+1));
  const d = WEEKLY[WEEKLY_IDX]; if(!d) return;
  const main = document.getElementById('w-main'); if(!main) return;
  main.innerHTML = '<div class="chat-empty loading">불러오는 중…</div>';
  if(i < 0){
    const msgs = await getJ('/api/messages?room='+encodeURIComponent(d.overall_room)).catch(()=>[]);
    main.innerHTML = `<div class="wk-h">전체 요약 · ${esc(d.date)}</div><div class="wk-scroll"><div class="md">${md(msgs.length ? msgs[msgs.length-1].body : '(보고 본문 없음)')}</div></div>`;
    clearInterval(pollTimer);
    document.getElementById('w-side').innerHTML = '<div class="side-h">담당과 대화</div><div class="chat"><div class="stream"><div class="chat-empty">왼쪽에서 프로젝트를 고르면 그 담당과 바로 대화할 수 있습니다</div></div></div>';
    return;
  }
  const p = d.projects[i];
  const msgs = await getJ('/api/messages?room='+encodeURIComponent(p.room)).catch(()=>[]);
  const who = a => a==='pm' ? 'PM' : a==='agent' ? esc(p.name)+' 담당' : a==='review' ? '이번 주 변경 리뷰 (Ponytail)' : '이번 주 몫';
  const bubbles = msgs.length ? msgs.map(m=>`<div class="msg ${m.author==='pm'?'pm':m.author==='agent'||m.author==='review'?'agent':'final'}"><div class="who">${who(m.author)}</div>`+
      `<div class="md">${md(m.body)}</div><div class="ts">${esc(fmtTs(m.created_at))}</div></div>`).join('')
    : '<div class="chat-empty">이번 주 점검 대화 기록이 없습니다.<br>커밋이 없던 프로젝트는 점검 대화를 건너뜁니다.</div>';
  main.innerHTML = `<div class="wk-h">${esc(p.name)} · ${esc(d.date)} <span class="wk-meta">${p.written?'<span class="tbadge green">ohmypm/weekly.md 기록</span>':'<span class="tbadge gray">미설치 — 파일 기록 안 함</span>'}</span></div>`+
    `<div class="wk-scroll stream-col">${bubbles}</div>`;
  document.getElementById('w-side').innerHTML = `<div class="side-h">${esc(p.name)} 담당과 대화</div>`+chatMarkup('보고 내용을 담당에게 바로 물어보거나 시키세요');
  bindChat(p.project, true);
}
async function runWeekly(){
  const b = document.getElementById('btn-weekly'); if(b){ b.disabled=true; b.textContent='작성 중…'; }
  const r = await postJ('/api/weekly/run');
  if(!r.ok){ appAlert('실행 실패', errMsg(r)); if(b){ b.disabled=false; b.textContent='주간보고 실행'; } }
  pollWeeklyJob();
}

// ── 랩실 ────────────────────────────────────────────────
let LAB = [], LAB_IDX = 2, LAB_SUB = 0, LAB_PANEL = 'notes', LAB_NOTE = '', LAB_LOAD = 0;
const labLink = (rid, panel='notes', key='') => '#/lab/'+encodeURIComponent(rid)+'/'+panel+(key?'/'+encodeURIComponent(key):'');
function renderLab(){
  const parts = location.hash.split('/').slice(2).map(decodeURIComponent);
  LAB_IDX = Math.max(0, ['models','design','skills'].indexOf(parts[0]||'skills'));
  LAB_PANEL = ['notes','request','wiki','proposals','ask'].includes(parts[1]) ? parts[1] : 'notes';
  LAB_NOTE = parts[2]||'';
  LAB_SUB = 0;
  setHeader('랩실', {buttons:[{id:'btn-lab', label:'새 조사 실행', onclick:'runLab()', ghost:true}]});
  document.getElementById('view').innerHTML =
    '<div class="lab-intro">모아 둔 자료를 읽고, 프로젝트에 쓸 만한 아이디어를 살펴보세요.</div>'+
    '<div id="lab-top"><div class="empty loading">불러오는 중…</div></div><nav class="lab-tabs" id="lab-tabs" aria-label="랩실 자료"></nav>'+
    '<div class="lab-content" id="lab-content"><div class="empty loading">불러오는 중…</div></div>';
  clearInterval(pollTimer);
  loadLab();
}
const labRoom = id => 'lab::'+id;
async function loadLab(){
  const version = ++LAB_LOAD;
  const top = document.getElementById('lab-top');
  try{ LAB = await getJ('/api/lab'); }catch(e){ LAB = []; }
  if(!top || top!==document.getElementById('lab-top') || version!==LAB_LOAD) return;
  if(!LAB.length){ top.textContent = '연구원이 없습니다'; return; }
  if(LAB_IDX >= LAB.length) LAB_IDX = 0;
  const r = LAB[LAB_IDX];
  top.innerHTML = `<div class="lab-researchers" aria-label="연구 분야">${LAB.map((x,i)=>`<button aria-pressed="${i===LAB_IDX}" onclick="go('${labLink(x.id)}')">${esc(x.name)}</button>`).join('')}</div>`+
    `<div class="lab-meta">${esc(r.topic)}<br>마지막 조사 ${esc(r.last_run?r.last_run.slice(0,16):'없음')}</div>`;
  document.getElementById('lab-tabs').innerHTML = [['notes','정리 문서'],['request','조사 요청'],['wiki','조사 기록'],['proposals','제안서'],['ask','연구원에게 질문']].map(([key,label])=>
    `<a href="${labLink(r.id,key)}"${LAB_PANEL===key?' aria-current="page"':''}>${label}</a>`).join('');
  const b = document.getElementById('btn-lab');
  if(b){ b.disabled = !!r.running; b.textContent = r.running ? '조사 중…' : '새 조사 실행'; }
  setStatus(r.running ? `<span class="live">${esc(r.name)} 조사 중</span> — 웹 조사라 몇 분 걸립니다` : '');
  const content = document.getElementById('lab-content');
  if(LAB_PANEL==='notes' && !content.dataset.loaded){
    try{
      const notes = await getJ('/api/lab/'+r.id+'/notes');
      if(version!==LAB_LOAD || !content.isConnected) return;
      renderLabNotes(content, r.id, notes);
      content.dataset.loaded = 'true';
    }catch(e){ content.innerHTML = '<div class="empty">정리 문서를 불러오지 못했습니다. 잠시 후 다시 열어 주세요.</div>'; }
  }else if(LAB_PANEL==='request'){
    if(!document.getElementById('lab-req-topic')) content.innerHTML = labRequestForm(r);
    await fillLabRequests(r.id);
    if(version!==LAB_LOAD || !content.isConnected) return;
  }else if(LAB_PANEL==='wiki'){
    const w = await getJ('/api/lab/'+r.id+'/wiki').catch(()=>({tabs:[]}));
    if(version!==LAB_LOAD || !content.isConnected) return;
    const tabs = w.tabs||[];
    if(LAB_SUB >= tabs.length) LAB_SUB = 0;
    const sub = tabs.length>1 ? `<div class="etabs">${tabs.map((t,i)=>`<button class="etab${i===LAB_SUB?' on':''}" onclick="LAB_SUB=${i};loadLab()">${esc(t.title)}</button>`).join('')}</div>` : '';
    const text = tabs.length ? tabs[LAB_SUB].wiki : '';
    const html = '<div class="wiki"><div class="lab-label">날짜별 조사 기록</div>'+sub+
      (text ? `<div class="md wiki-body">${md(text)}</div>` : '<div class="empty">아직 조사 기록이 없습니다.<br>오른쪽 위 새 조사 실행을 누르거나, 주 1회 자동 조사를 기다리면 여기에 쌓입니다.</div>')+'</div>';
    if(content.dataset.source!==html){ content.innerHTML=html; content.dataset.source=html; }
  }else if(LAB_PANEL==='proposals'){
    if(!document.getElementById('lab-props')) content.innerHTML='<div class="props" id="lab-props"></div>';
    fillProposals(r.id);
  }else if(LAB_PANEL==='ask'){
    if(!document.getElementById('msg-input')){
      content.innerHTML=chatMarkup('정리 문서와 조사 기록을 바탕으로 답합니다. Enter로 전송');
      document.getElementById('msg-input').setAttribute('aria-label', '연구원에게 질문');
      document.getElementById('msg-input').onkeydown = ev=>{ if(ev.key==='Enter' && !ev.shiftKey){ ev.preventDefault(); sendLabQ(r.id); }};
    }
    loadMessages(labRoom(r.id), true, true);
  }
  if(version!==LAB_LOAD || !content.isConnected) return;
  clearInterval(pollTimer);
  pollTimer = setInterval(()=>{ if(LAB_PANEL==='ask') loadMessages(labRoom(r.id), true, true);
    if(LAB_PANEL==='request' && LAB_REQ_BUSY) fillLabRequests(r.id);
    if(r.running) loadLab(); }, 4000);
}
// ── 조사 요청 — 주제를 주면 이 연구원이 웹을 조사해 정리 문서 한 편을 쓴다(백그라운드, 한 건에 수 분~15분)
let LAB_REQ_BUSY = false;   // 대기·조사 중인 요청이 있으면 4초마다 목록을 다시 읽는다
const LAB_REQ_STATUS = {queued:'대기', running:'조사 중', done:'완료', failed:'실패'};
function labRequestForm(r){
  return `<div class="lab-req"><div class="lab-label">${esc(r.name)}에게 조사 요청</div>`+
    `<input id="lab-req-topic" maxlength="200" placeholder="주제 — 예: 모델별 하네스 엔지니어링" aria-label="조사 주제">`+
    `<textarea id="lab-req-detail" rows="3" maxlength="2000" placeholder="궁금한 점(선택) — 무엇을 알고 싶은지, 어디에 쓰려는지" aria-label="궁금한 점"></textarea>`+
    `<div class="lab-req-row"><button id="lab-req-btn" onclick="sendLabRequest('${escAttr(r.id)}')">조사 요청</button>`+
    `<span class="note-line">웹을 여러 번 찾아보고 길게 써서 한 건에 수 분~15분 걸립니다. 끝나면 정리 문서에 올라갑니다.</span></div></div>`+
    `<div class="lab-label" style="margin-top:22px">요청 기록</div><div id="lab-req-list"></div>`;
}
async function fillLabRequests(rid){
  const list = await getJ('/api/lab/'+encodeURIComponent(rid)+'/requests').catch(()=>[]);
  const box = document.getElementById('lab-req-list'); if(!box) return;
  LAB_REQ_BUSY = list.some(x=>x.status==='queued'||x.status==='running');
  box.innerHTML = list.length ? list.map(x=>{
    const st = `<span class="tbadge ${x.status==='done'?'green':x.status==='failed'?'red':'gray'}">${LAB_REQ_STATUS[x.status]||esc(x.status)}</span>`;
    const link = x.status==='done' && x.note_key ? ` <a href="${escAttr(labLink(rid,'notes',x.note_key))}">정리 문서 열기 →</a>` : '';
    const err = x.status==='failed' && x.error ? `<div class="lab-req-err">${esc(x.error)}</div>` : '';
    const cost = x.cost_usd!=null ? ` · 비용 ${fmtCost(x.cost_usd)}` : '';
    return `<div class="lab-req-item">${st}<b>${esc(x.topic)}</b>${link}`+
      `<div class="lab-req-meta">${esc(fmtTs(x.created_at))} 요청${x.finished_at?' · '+esc(fmtTs(x.finished_at))+' 끝':''}${cost}</div>`+
      (x.detail?`<div class="lab-req-detail">${esc(x.detail)}</div>`:'')+err+`</div>`;
  }).join('') : '<div class="note-line">아직 요청이 없습니다</div>';
}
async function sendLabRequest(rid){
  const t = document.getElementById('lab-req-topic'), d = document.getElementById('lab-req-detail');
  const topic = (t.value||'').trim(); if(!topic){ t.focus(); return; }
  const b = document.getElementById('lab-req-btn'); if(b) b.disabled = true;
  const r = await postJ('/api/lab/'+encodeURIComponent(rid)+'/requests', {topic, detail:(d.value||'').trim()||null});
  if(b) b.disabled = false;
  if(!r.ok){ appAlert('요청 실패', errMsg(r)); return; }
  t.value = ''; d.value = '';
  fillLabRequests(rid);
}
function renderLabNotes(content, rid, notes){
  if(!notes.length){
    content.innerHTML=`<div class="empty">아직 정리 문서가 없습니다.<br><a class="back" href="${labLink(rid,'wiki')}">조사 기록 살펴보기 →</a></div>`;
    return;
  }
  const note = LAB_NOTE ? notes.find(n=>n.key===LAB_NOTE) : notes[0];
  if(!note){ content.innerHTML=`<div class="empty">문서를 찾을 수 없습니다.<br><a class="back" href="${labLink(rid)}">정리 문서 목록으로</a></div>`; return; }
  const chunks = note.body.replace(/^# .*(\r?\n|$)/,'').split(/^## /m);
  const intro = chunks.shift().trim();
  const sections = chunks.map(chunk=>{ const [title,...body]=chunk.split('\n'); return {title,body:body.join('\n').trim()}; });
  const media = note.assets.map(a=>`<figure class="lab-media">${a.kind==='video'?`<video controls playsinline preload="metadata" aria-label="${escAttr(note.title)} 시험 영상" src="${escAttr(a.url)}"></video>`:`<img loading="lazy" src="${escAttr(a.url)}" alt="${escAttr(a.name)}">`}<figcaption>${a.kind==='video'?'직접 만든 시험 영상 · 재생해서 결과를 확인하세요':'첨부 이미지'} · <a href="${escAttr(a.url)}" target="_blank" rel="noopener">파일 열기 ↗</a></figcaption></figure>`).join('');
  content.innerHTML = `<div class="lab-reading"><nav class="lab-index" aria-label="정리 문서와 목차"><div class="lab-label">정리 문서 · ${notes.length}</div>`+
    notes.map(n=>`<a href="${escAttr(labLink(rid,'notes',n.key))}"${n.key===note.key?' aria-current="page"':''}>${esc(n.title)}</a>`).join('')+
    `<div class="lab-toc"><div class="lab-label">이 문서의 내용</div>${sections.map((s,i)=>`<button data-sec="${i}" onclick="document.getElementById('lab-section-${i}').scrollIntoView({block:'start'})">${esc(s.title)}</button>`).join('')}</div></nav>`+
    `<article class="lab-article"><a class="back" href="${labLink(rid,'wiki')}">← 연구 위키로</a><div class="lab-label">연구 노트</div><h1>${esc(note.title)}</h1><div class="md">${md(intro)}</div>`+
    (sections.length?'':media)+sections.map((s,i)=>`<section id="lab-section-${i}" class="lab-section${i===0?' summary-section':''}"><h2>${esc(s.title)}</h2><div class="md">${md(s.body)}</div></section>${i===0?media:''}`).join('')+'</article></div>';
  labTocSpy();
}
// 목차 읽음 표시 — 스크롤하면 지금 읽는 절은 강조(on), 이미 지나온 절은 읽음(read)으로 자동 표시.
// 스크롤 이벤트는 위로 전달되지 않아서 문서에 '잡기 단계'로 한 번만 걸어 어느 상자가 스크롤돼도 받는다.
const LAB_TOC_LINE = 140;   // 화면 위에서 이 높이(px)를 넘어선 절을 '읽는 중'으로 본다
function labTocSpy(){
  const btns = document.querySelectorAll('.lab-toc button[data-sec]'); if(!btns.length) return;
  let cur = 0;
  btns.forEach((b,i)=>{ const sec = document.getElementById('lab-section-'+i);
    if(sec && sec.getBoundingClientRect().top <= LAB_TOC_LINE) cur = i; });
  const last = document.getElementById('lab-section-'+(btns.length-1));
  // 맨 끝까지 내리면 마지막 절이 짧아도 '읽는 중'으로 — 실제로 스크롤되는 상자(지금은 #lab-content)를 찾는다
  let box = last && last.parentElement;
  while(box && !(box.scrollHeight > box.clientHeight && /(auto|scroll)/.test(getComputedStyle(box).overflowY))) box = box.parentElement;
  if(box && box.scrollTop > 0 && box.scrollTop + box.clientHeight >= box.scrollHeight - 4) cur = btns.length-1;
  btns.forEach((b,i)=>{ b.classList.toggle('on', i===cur); b.classList.toggle('read', i<cur);
    if(i===cur) b.setAttribute('aria-current','location'); else b.removeAttribute('aria-current'); });
}
let labTocTick = false;
document.addEventListener('scroll', ()=>{ if(labTocTick) return; labTocTick = true;
  requestAnimationFrame(()=>{ labTocTick = false; labTocSpy(); }); }, true);
function proposalHtml(p, showResearcher){
  return `<div class="prop${p.status!=='open'?' done':''}"><div class="pt">${esc(p.title)}`+
    (showResearcher?`<span class="tbadge">${esc(p.researcher_name||p.researcher)}</span>`:'')+
    (p.target_name?`<span class="tbadge green">${esc(p.target_name)}</span>`:'<span class="tbadge gray">전체</span>')+
    (p.status!=='open'?`<span class="tbadge gray">${p.status==='done'?'처리됨':'무시'}</span>`:'')+`</div>`+
    `<div class="pb md">${md(p.body)}</div>`+(p.source_url?`<div class="pb"><a href="${escAttr(p.source_url)}" target="_blank" rel="noopener noreferrer">출처</a></div>`:'')+
    (p.status==='open'?`<div class="pa"><span onclick="setProposal(${p.id},'done')">처리됨</span><span onclick="setProposal(${p.id},'dismissed')">무시</span></div>`:'')+`</div>`;
}
async function fillProposals(rid){
  const list = await getJ('/api/lab/proposals?researcher='+encodeURIComponent(rid)).catch(()=>[]);
  const box = document.getElementById('lab-props'); if(!box) return;
  box.innerHTML = list.length ? list.map(p=>proposalHtml(p,false)).join('') : '<div class="note-line">아직 제안이 없습니다</div>';
}
async function setProposal(id, status){
  await postJ('/api/lab/proposals/'+id+'/status', {status});
  if(LAB[LAB_IDX]) fillProposals(LAB[LAB_IDX].id);
  if(CUR_ROOM) fillRoomMain(CUR_ROOM);
}
async function sendLabQ(rid){
  const input = document.getElementById('msg-input');
  const body = input.value.trim(); if(!body) return;
  input.value = '';
  await postJ('/api/lab/'+rid+'/ask', {question: body});
  loadMessages(labRoom(rid), false, true);
}
async function runLab(){
  const r = LAB[LAB_IDX]; if(!r) return;
  const b = document.getElementById('btn-lab'); if(b){ b.disabled=true; b.textContent='조사 중…'; }
  const res = await postJ('/api/lab/'+r.id+'/run');
  if(!res.ok){ appAlert('조사를 시작하지 못함', errMsg(res)); if(b){ b.disabled=false; b.textContent='조사 실행'; } }
  loadLab();
}

// ── 에이전트 ───────────────────────────────────────────
let AGENT_LIST = [], AGENT_SEL = null;
function renderAgents(){
  setHeader('에이전트', {});
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:12px">담당 에이전트별 누적 점수(글 좋아요·조회 − 싫어요 + 댓글 좋아요 − 싫어요)와 토론 끝에 복기한 \'배운 것\'. 행을 누르면 회차별 이력이 아래에 펼쳐집니다. 모델 열에서 이 담당의 headless 모델을 바꿀 수 있습니다.</div>'+
    '<div id="agents"><div class="empty loading">불러오는 중…</div></div><div id="agent-hist"></div>';
  clearInterval(pollTimer);
  fillAgents();
}
async function fillAgents(){
  let list = [];
  try{ list = await getJ('/api/agents'); }catch(e){ return; }
  const box = document.getElementById('agents'); if(!box) return;
  if(!list.length){ box.innerHTML = '<div class="empty">아직 담당이 없습니다.<br>대시보드에서 스캔(설치)을 누르면 프로젝트마다 담당이 생깁니다.</div>'; return; }
  AGENT_LIST = list;
  const MODELS = [['','기본(sonnet)'],['opus','opus'],['sonnet','sonnet'],['haiku','haiku']];
  box.innerHTML = '<table class="ptable"><thead><tr><th>#</th><th>담당(프로젝트)</th><th>누적 점수</th><th>최근 회차</th><th>배운 것(최근)</th><th>모델</th></tr></thead><tbody>'+
    list.map((a,i)=>{
      const delta = a.last_delta==null ? '-' : (a.last_delta>=0?'+':'')+a.last_delta;
      const sel = `<select onclick="event.stopPropagation()" onchange="setAgentModel(${i}, this.value)">`+
        MODELS.map(([v,l])=>`<option value="${v}"${(a.model||'')===v?' selected':''}>${l}</option>`).join('')+`</select>`;
      return `<tr class="clickable${AGENT_SEL===a.project?' sel':''}" onclick="showAgentHist(${i})"><td>${i+1}</td><td>${esc(a.name)}</td><td class="port">${a.points}</td>`+
        `<td class="muted">${delta}</td><td class="muted">${esc(a.note_head||'')}</td><td>${sel}</td></tr>`;
    }).join('')+'</tbody></table>';
}
async function showAgentHist(i){
  const a = AGENT_LIST[i]; if(!a) return;
  AGENT_SEL = a.project; fillAgents();
  const box = document.getElementById('agent-hist'); if(!box) return;
  box.innerHTML = '<div class="note-line loading" style="justify-content:flex-start">불러오는 중…</div>';
  const rows = await getJ('/api/scores?project='+encodeURIComponent(a.project)).catch(()=>[]);
  box.innerHTML = `<section style="margin-top:18px"><h2>${esc(a.name)} 회차 이력</h2>`+scoreTable(rows)+`</section>`;
}
function scoreTable(rows){
  if(!rows.length) return '<div class="note-line">아직 토론 이력이 없습니다</div>';
  return '<table class="ptable"><thead><tr><th>회차</th><th>글/댓글</th><th>받은 반응</th><th>점수</th><th>누적</th><th>배운 것</th></tr></thead><tbody>'+
    rows.map(r=>`<tr><td>${esc((r.session_started||'').slice(0,16))}</td><td>${r.posts}/${r.comments}</td>`+
      `<td class="muted">조회 ${r.views} · 좋아요 ${r.post_likes+r.cmt_likes} · 싫어요 ${r.post_dislikes+r.cmt_dislikes} · 답글 ${r.replies_received}</td>`+
      `<td class="port">${r.points>=0?'+':''}${r.points}</td><td>${r.total}</td><td>${esc(r.lesson||'-')}</td></tr>`).join('')+'</tbody></table>';
}
async function setAgentModel(idx, model){
  const project = (AGENT_LIST[idx]||{}).project; if(!project) return;
  const r = await postJ('/api/agents/model', {project, model});
  if(!r.ok) appAlert('모델 변경 실패', errMsg(r));
  fillAgents();
}

// ── 포트 ───────────────────────────────────────────────
function renderPorts(){
  setHeader('포트', {});
  const opts = PROJECTS.map(p=>`<option value="${escAttr(p.path)}">${esc(p.name)}</option>`).join('');
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:12px">지금 열려 있는 포트를 전부 보여주고, 프로세스 명령줄의 경로로 어느 프로젝트 것인지 맞춥니다. 등록하면 떠 있는지·충돌 여부를 보고, 실행 명령을 함께 등록하면 여기서 켜고 끌 수 있습니다.</div>'+
    '<div id="ports"><div class="empty loading">불러오는 중…</div></div>'+
    `<div class="pform"><div class="pform-h">직접 등록</div><select id="pf-proj">${opts}</select>`+
      `<input id="pf-port" type="number" placeholder="포트(예: 8000)" style="width:150px">`+
      `<input id="pf-label" placeholder="용도(예: 웹 대시보드)" style="width:180px">`+
      `<input id="pf-cmd" class="grow" placeholder="실행 명령(선택, 예: uv run uvicorn ...)">`+
      `<button onclick="addPort()">등록</button></div>`;
  fillPorts();
  clearInterval(pollTimer);
  pollTimer = setInterval(fillPorts, 8000);
}
async function fillPorts(){
  if(portEditing) return;
  let d = {rows:[], conflicts:[], detected:[]};
  try{ d = await getJ('/api/ports'); }catch(e){ return; }
  const box = document.getElementById('ports'); if(!box) return;
  let html = '';
  if(d.conflicts && d.conflicts.length)
    html += '<div class="pconf">포트 충돌 — '+d.conflicts.map(c=>`${c.port}: ${esc(c.projects.join(', '))}`).join(' · ')+'</div>';
  if(d.rows.length){
    html += '<table class="ptable"><thead><tr><th>프로젝트</th><th>포트</th><th>용도</th><th>상태</th><th></th></tr></thead><tbody>'+
      d.rows.map(r=>{
        const st = r.up ? `<span class="up">● 떠 있음</span> <span class="pid">${esc(r.proc||'')} #${r.pid}</span>` : '<span class="down">○ 멈춤</span>';
        let act = '';
        if(r.up) act = `<button class="pbtn stop" onclick="stopPort(${r.id},${r.port},'${escAttr(r.proc||'')}',${r.pid})">중지</button>`;
        else if(r.start_cmd) act = `<button class="pbtn start" onclick="startPort(${r.id},this)">시작</button>`;
        return `<tr><td>${esc(r.name)}</td><td class="port">${r.port}</td><td>${esc(r.label||'')}</td><td>${st}</td><td>${act} <span class="del" onclick="delPort(${r.id})">삭제</span></td></tr>`;
      }).join('')+'</tbody></table>';
  } else html += '<div class="empty" style="padding:20px">등록된 포트가 없습니다 — 아래 감지된 포트에서 등록하거나 직접 추가하세요</div>';
  const det = d.detected || [];
  if(det.length){
    html += '<div class="pdet-h">지금 떠 있는데 미등록</div>'+
      '<table class="ptable"><thead><tr><th>포트</th><th>프로세스</th><th>명령줄</th><th>프로젝트</th><th></th></tr></thead><tbody>'+
      det.map(x=>`<tr data-port="${x.port}"><td class="port">${x.port}</td><td>${esc(x.proc)} <span class="pid">#${x.pid}</span></td>`+
        `<td><span class="cmd" title="${escAttr(x.cmdline||'')}">${esc(x.cmdline||'')}</span></td>`+
        `<td>${x.project_name?esc(x.project_name):'<span class="pid">못 맞춤</span>'}</td>`+
        `<td class="reg-cell">${x.project?`<span class="reg" data-reg-port="${x.port}" data-reg-proj="${escAttr(x.project)}">＋ ${esc(x.project_name)}으로 등록</span>`:`<span class="reg" onclick="inlineReg(${x.port}, this)">＋ 등록</span>`}</td></tr>`).join('')+
      '</tbody></table>';
  }
  setHTML(box, html);
}
function inlineReg(port, el){
  portEditing = true;
  delete document.getElementById('ports').dataset.source;   // 칸을 직접 바꾸므로, 편집이 끝나면 목록을 반드시 다시 그리게
  const td = el.closest('td');
  const opts = PROJECTS.map(p=>`<option value="${escAttr(p.path)}">${esc(p.name)}</option>`).join('');
  td.innerHTML = `<select class="ireg-proj">${opts}</select><input class="ireg-label" placeholder="용도(선택)"><input class="ireg-cmd" placeholder="실행 명령(선택)">`+
    `<button onclick="saveInlineReg(${port}, this)">저장</button><span class="del" onclick="cancelInlineReg()">취소</span>`;
  td.querySelector('.ireg-proj').focus();
}
async function saveInlineReg(port, btn){
  const td = btn.closest('td');
  await postJ('/api/ports', {project: td.querySelector('.ireg-proj').value, port, label: td.querySelector('.ireg-label').value, start_cmd: (td.querySelector('.ireg-cmd')||{}).value||''});
  portEditing = false; fillPorts();
}
function cancelInlineReg(){ portEditing = false; fillPorts(); }
async function quickReg(port, project){ await postJ('/api/ports', {project, port: Number(port), label:'', start_cmd:''}); fillPorts(); }
async function addPort(){
  const project = document.getElementById('pf-proj').value;
  const port = parseInt(document.getElementById('pf-port').value, 10);
  if(!port) return;
  await postJ('/api/ports', {project, port, label: document.getElementById('pf-label').value, start_cmd: document.getElementById('pf-cmd').value});
  document.getElementById('pf-port').value = ''; document.getElementById('pf-label').value = ''; document.getElementById('pf-cmd').value = '';
  fillPorts();
}
async function delPort(id){ await fetch('/api/ports/'+id,{method:'DELETE'}); fillPorts(); }
async function startPort(id, btn){
  if(btn){ btn.disabled = true; btn.textContent = '시작 중…'; }
  const r = await postJ('/api/ports/'+id+'/start');
  if(r && r.ok === false) appAlert('시작 못 함', r.reason||r.error||'알 수 없음');
  setTimeout(fillPorts, 1500);
}
async function stopPort(id, port, proc, pid){
  const ok = await appConfirm({title:'포트 '+port+' 프로세스 종료', okText:'종료', danger:true,
    body:'대상: '+(proc||'(이름 미상)')+' (PID '+pid+')\n\n저장하지 않은 작업이 있으면 유실될 수 있습니다. 정말 종료할까요?'});
  if(!ok) return;
  const r = await postJ('/api/ports/'+id+'/stop');
  if(r && r.ok === false) appAlert('종료 못 함', r.reason||r.error||'알 수 없음');
  fillPorts();
}

// ── 프로젝트 룸 ──────────────────────────────────────────
function renderRoom(path){
  CUR_ROOM = path;
  const p = PROJECTS.find(x=>x.path===path);
  const name = p ? p.name : path;
  setHeader(name, {});
  document.getElementById('view').innerHTML =
    `<div class="room-layout"><div class="room-main" id="room-main"><div class="empty loading">불러오는 중…</div></div>`+
    `<div class="room-side"><div class="side-h">${esc(name)} 담당 에이전트</div>${chatMarkup('담당에게 물어보거나 시키세요')}</div></div>`;
  fillRoomMain(path);
  bindChat(path, true);
  // 담당이 채팅으로 카드를 바꾸면 칸반도 따라가게 — 카드 입력 중이면 건드리지 않는다
  clearInterval(tickTimer);
  tickTimer = setInterval(()=>{
    const t = document.getElementById('kadd-title');
    if(t && !t.value && document.activeElement!==t) fillKanban(path);
  }, 8000);
}
async function fillRoomMain(path){
  const main = document.getElementById('room-main'); if(!main) return;
  const p = PROJECTS.find(x=>x.path===path) || {path, name: path};
  const [weekly, props, scores] = await Promise.all([
    getJ('/api/weekly').catch(()=>[]), getJ('/api/lab/proposals?project='+encodeURIComponent(path)).catch(()=>[]),
    getJ('/api/scores?project='+encodeURIComponent(path)+'&limit=10').catch(()=>[])]);
  let weeklyHtml = '<div class="note-line">아직 주간보고 몫이 없습니다</div>';
  for(const d of weekly){
    const mine = (d.projects||[]).find(x=>x.project===path);
    if(mine){ const msgs = await getJ('/api/messages?room='+encodeURIComponent(mine.room)).catch(()=>[]);
      const share = msgs.filter(m=>m.author==='ohmyPM').pop();
      if(share){ weeklyHtml = `<div class="report md"><div class="mh">${esc(d.date)}</div>${md(share.body)}</div>`; } break; }
  }
  main.innerHTML =
    `<section><div class="kv"><div><b>경로</b> ${esc(path)}</div>`+
      `<div><b>설치</b> <span class="badge ${p.installed?'on':'off'}">${p.installed?'ohmypm/ 설치됨':'미설치'}</span> `+
      (p.installed?`<span class="mini-btn red" onclick="uninstallProject('${encodeURIComponent(path)}')">설치 제거</span>`:`<span class="mini-btn" onclick="installProject('${encodeURIComponent(path)}')">설치</span>`)+`</div></div></section>`+
    `<section><h2>환경 세팅</h2><div id="envset"><div class="empty loading">불러오는 중…</div></div></section>`+
    `<section><h2>칸반</h2><div id="kanban"></div></section>`+
    `<section><h2>최근 주간보고 몫</h2>${weeklyHtml}</section>`+
    `<section><h2>이 프로젝트 대상 제안서 (${props.length})</h2>${props.length?`<div class="props" style="max-height:none">${props.map(x=>proposalHtml(x,true)).join('')}</div>`:'<div class="note-line">아직 제안이 없습니다</div>'}</section>`+
    `<section><h2>토론 점수 이력</h2>${scoreTable(scores)}</section>`;
  fillKanban(path);
  fillEnvSetup(path);
}

// ── 환경 세팅 ───────────────────────────────────────────
// ohmyPM이 프로젝트를 살펴 CLAUDE.md·AGENTS.md·.claude/settings.json의 작은 변경안을 내고(모델 한 번),
// 사용자가 고른 항목만 서버가 백업한 뒤 쓴다. 브라우저는 항목 번호만 보낸다 — 내용은 서버에 저장된 제안이다.
let ENV_TIMER = null;          // 제안·적용이 진행 중일 때만 3초마다 다시 읽는다(화면을 떠나면 route()가 끈다)
let ENV_TOKEN = 0;             // 늦게 도착한 응답이 다른 프로젝트 화면을 덮지 않게
const ENV_SEL = {};            // 실행 번호 → 고른 항목 번호들(다시 그려도 선택이 남게)
const ENV_BUSY = ['queued','running','applying','reverting'];
const ENV_RUN_LABEL = {queued:'접수됨', running:'제안을 만드는 중…', proposed:'제안 도착 — 적용할 항목을 고르세요',
  applying:'적용하는 중…', applied:'적용함', partial:'일부만 처리함', failed:'실패', reverting:'되돌리는 중…', reverted:'되돌림'};
const ENV_ITEM_LABEL = {proposed:'제안', approved:'승인함', applied:'적용함', skipped:'건너뜀', rejected:'승인 안 함', reverted:'되돌림'};
const ENV_ITEM_BADGE = {applied:'green', skipped:'gold', reverted:'gray', rejected:'gray', approved:'gray'};
const ENV_OP = {create:'새 파일 만들기', append:'끝에 덧붙이기', replace:'한 부분 바꾸기'};

async function fillEnvSetup(path){
  const box = document.getElementById('envset'); if(!box) return;
  const token = ++ENV_TOKEN;
  let list, detail = null;
  try{ list = await getJ('/api/env-setup?project='+encodeURIComponent(path)); }
  catch(e){ list = {available:false, reason:'환경 세팅 이력을 불러오지 못했습니다', runs:[]}; }
  if(list.runs && list.runs.length){ try{ detail = await getJ('/api/env-setup/'+list.runs[0].id); }catch(e){} }
  if(token !== ENV_TOKEN || CUR_ROOM !== path || !document.getElementById('envset')) return;
  setHTML(box, envSetupHtml(path, list, detail));
  clearTimeout(ENV_TIMER);
  if(detail && ENV_BUSY.includes(detail.run.status)) ENV_TIMER = setTimeout(()=>fillEnvSetup(path), 3000);
}
function envSetupHtml(path, list, detail){
  const enc = encodeURIComponent(path);
  if(!list.available)
    return `<div class="env-head"><button disabled>환경 세팅</button><span class="note-line">${esc(list.reason||'이 프로젝트는 환경 세팅 대상이 아닙니다')}</span></div>`;
  const run = detail && detail.run;
  const busy = run && ENV_BUSY.includes(run.status);
  let h = `<div class="env-head"><button id="env-start"${busy?' disabled':''} onclick="startEnvSetup('${enc}')">${run?'새 제안 만들기':'환경 세팅'}</button>`+
    `<span class="note-line">CLAUDE.md·AGENTS.md·.claude/settings.json을 살펴 작은 변경안을 냅니다. 고른 항목만 쓰고, 쓰기 전에 ohmypm/setup-backup/에 백업합니다. 커밋은 하지 않습니다.</span></div>`;
  if(!run) return h;
  h += `<div class="env-run"><b>${esc(ENV_RUN_LABEL[run.status]||run.status)}</b> · ${esc((run.created_at||'').slice(5,16))}`+
    (run.cost_usd ? ' · 비용 '+fmtCost(run.cost_usd) : '')+
    (run.error ? `<div class="env-err">${esc(run.error)}</div>` : '')+
    ((run.warnings||[]).length ? `<div class="note-line">수집 때 경고: ${run.warnings.map(esc).join(' / ')}</div>` : '')+`</div>`;
  const items = detail.items || [];
  const writable = items.filter(i=>i.applicable);
  const shown = items.filter(i=>!i.applicable && !i.experimental);
  const exp = items.filter(i=>!i.applicable && i.experimental);
  const sel = ENV_SEL[run.id] || (ENV_SEL[run.id] = new Set());
  const canPick = run.status === 'proposed';
  if(writable.length) h += '<h3>적용할 수 있는 항목</h3>' + writable.map(i=>envItemHtml(run, i, canPick, sel.has(i.id))).join('');
  if(shown.length) h += '<h3>보여 주기만 하는 항목</h3>' + shown.map(i=>envItemHtml(run, i, false, false)).join('');
  if(exp.length) h += '<h3>시험 전 재료 — 보여 주기만</h3><div class="note-line">아직 효과를 확인하지 않은 재료라 적용할 수 없습니다.</div>' +
    exp.map(i=>envItemHtml(run, i, false, false)).join('');
  if(canPick && writable.length)
    h += `<div class="env-actions"><button id="env-apply" onclick="applyEnvSetup(${run.id},'${enc}')">고른 항목 적용</button></div>`;
  if(['applied','partial'].includes(run.status) && items.some(i=>i.status==='applied'))
    h += `<div class="env-actions"><button class="ghost" onclick="revertEnvSetup(${run.id},'${enc}')">이 실행 되돌리기</button></div>`;
  return h;
}
function envItemHtml(run, i, canPick, checked){
  const id = `env-${run.id}-${i.id}`;
  const pick = canPick ? `<input type="checkbox" id="${id}"${checked?' checked':''} onchange="envPick(${run.id},${i.id},this.checked)">` : '';
  const title = canPick ? `<label for="${id}"><b>${esc(i.title)}</b></label>` : `<b>${esc(i.title)}</b>`;
  const st = (i.applicable && (run.status !== 'proposed' || i.status !== 'proposed'))
    ? ` <span class="tbadge ${ENV_ITEM_BADGE[i.status]||'gray'}">${esc(ENV_ITEM_LABEL[i.status]||i.status)}</span>` : '';
  const ex = i.experimental ? ' <span class="tbadge gray">시험 전</span>' : '';
  const diff = i.op === 'replace'
    ? `<div class="env-diff"><div class="dh">바꾸기 전</div><pre>${esc(i.before||'')}</pre><div class="dh">바꾼 뒤</div><pre>${esc(i.after||'')}</pre></div>`
    : `<div class="env-diff"><div class="dh">${i.op==='create'?'새로 만들 내용':'끝에 덧붙일 내용'}</div><pre>${esc(i.after||'')}</pre></div>`;
  return `<div class="env-item">${pick}${title}${ex}${st}`+
    `<div class="env-meta">${esc(i.target)} · ${esc(ENV_OP[i.op]||i.op)}</div><div class="env-why">${esc(i.why)}</div>`+
    (i.install_guide ? `<div class="note-line">${esc(i.install_guide)}</div>` : '')+
    (i.reason ? `<div class="env-reason">${esc(i.reason)}</div>` : '')+diff+`</div>`;
}
function envPick(runId, itemId, on){
  const s = ENV_SEL[runId] || (ENV_SEL[runId] = new Set());
  if(on) s.add(itemId); else s.delete(itemId);
}
async function startEnvSetup(enc){
  const path = decodeURIComponent(enc);
  const b = document.getElementById('env-start'); if(b) b.disabled = true;
  const r = await postJ('/api/env-setup/run', {path});
  if(!r.ok){ appAlert('환경 세팅을 시작하지 못함', errMsg(r)); if(b) b.disabled = false; return; }
  fillEnvSetup(path);
}
async function applyEnvSetup(runId, enc){
  const path = decodeURIComponent(enc);
  const ids = [...(ENV_SEL[runId] || [])];
  if(!ids.length){ appAlert('고른 항목이 없음', '적용할 항목의 체크박스를 먼저 고르세요.'); return; }
  const b = document.getElementById('env-apply'); if(b){ b.disabled = true; b.textContent = '적용하는 중…'; }
  const r = await postJ(`/api/env-setup/${runId}/apply`, {item_ids: ids});
  if(!r.ok) appAlert('적용 실패', errMsg(r));
  else { const c = r.counts;
    appAlert('적용 결과', `적용 ${c.applied}건 · 건너뜀 ${c.skipped}건 · 실패 ${c.failed}건 · 승인 안 함 ${c.rejected}건\n\n항목마다 결과와 이유가 화면에 표시됩니다.`); }
  fillEnvSetup(path);
}
async function revertEnvSetup(runId, enc){
  const path = decodeURIComponent(enc);
  const d = await getJ('/api/env-setup/'+runId).catch(()=>null);
  const targets = d ? d.items.filter(i=>i.status==='applied').map(i=>i.target) : [];
  const ok = await appConfirm({title:'환경 세팅 되돌리기', okText:'되돌리기', danger:true,
    body:`실행 시각: ${d ? d.run.created_at : '(알 수 없음)'}\n대상 파일: ${targets.join(', ') || '(없음)'}\n\n백업해 둔 원본으로 되살립니다. 적용 뒤 직접 고친 파일은 덮어쓰지 않고 충돌로 남깁니다.`});
  if(!ok) return;
  const r = await postJ(`/api/env-setup/${runId}/revert`);
  if(!r.ok) appAlert('되돌리기 실패', errMsg(r));
  else { const c = r.counts; appAlert('되돌리기 결과', `되돌림 ${c.reverted}건 · 충돌로 남김 ${c.skipped}건 · 실패 ${c.failed}건`); }
  fillEnvSetup(path);
}

// ── 칸반 ────────────────────────────────────────────────
// 카드는 주간보고 PM·담당 채팅·사용자(여기)가 만들고 옮긴다. '지연'은 저장된 칸이 아니라
// 기한이 지났는데 완료가 아닌 카드를 모아 보여 주는 칸 — 카드에 원래 칸 이름이 작게 붙는다.
let KANBAN = {statuses:[], cards:[]};
const KBY = {pm:'PM', agent:'담당', user:'나'};
async function fillKanban(path){
  try{ KANBAN = await getJ('/api/cards?project='+encodeURIComponent(path)); }catch(e){ KANBAN = {statuses:[], cards:[]}; }
  const box = document.getElementById('kanban'); if(!box) return;
  const today = todayStr();
  const late = c => c.status!=='done' && c.due && c.due < today;
  const label = Object.fromEntries(KANBAN.statuses.map(x=>[x.key, x.label]));
  const keys = KANBAN.statuses.map(x=>x.key);
  const card = (c, inLate) => {
    const i = keys.indexOf(c.status);
    const prev = i>0 ? `<span onclick="moveCard(${c.id},'${keys[i-1]}')" title="${escAttr(label[keys[i-1]])}로">‹</span>` : '';
    const next = i<keys.length-1 ? `<span onclick="moveCard(${c.id},'${keys[i+1]}')" title="${escAttr(label[keys[i+1]])}로">›</span>` : '';
    return `<div class="kcard${inLate?' late':''}"><div class="kt">${esc(c.title)}</div>`+
      (c.note?`<div class="kn">${esc(c.note)}</div>`:'')+
      `<div class="kf">${c.due?`<span class="kdue">${inLate?'기한 지남 ':''}${esc(c.due)}</span>`:''}`+
      (inLate?`<span class="tbadge gray">${esc(label[c.status]||c.status)}</span>`:'')+
      `<span class="kby">${esc(KBY[c.created_by]||'')}</span>`+
      `<span class="kmv">${prev}${next}<span onclick="delCard(${c.id})" title="지우기">지우기</span></span></div></div>`;
  };
  const lateCards = KANBAN.cards.filter(late);
  const cols = [];
  if(lateCards.length) cols.push(`<div class="kcol late"><h3>지연<span class="n">${lateCards.length}</span></h3>${lateCards.map(c=>card(c,true)).join('')}</div>`);
  for(const st of KANBAN.statuses){
    let list = KANBAN.cards.filter(c=>c.status===st.key && !late(c));
    let more = '';
    if(st.key==='done'){   // 완료는 최근 것만 — 오래 쌓이면 칸이 끝없이 길어진다
      list = list.sort((a,b)=>(b.done_at||'').localeCompare(a.done_at||''));
      if(list.length>8){ more = `<div class="col-empty">외 ${list.length-8}장</div>`; list = list.slice(0,8); }
    }
    const n = KANBAN.cards.filter(c=>c.status===st.key && !late(c)).length;
    cols.push(`<div class="kcol"><h3>${esc(st.label)}<span class="n">${n}</span></h3>${list.map(c=>card(c,false)).join('')||'<div class="col-empty">없음</div>'}${more}</div>`);
  }
  box.innerHTML =
    `<div class="kadd"><input id="kadd-title" placeholder="새 카드 제목" onkeydown="if(event.key==='Enter')addCard('${encodeURIComponent(path)}')">`+
    `<select id="kadd-status">${KANBAN.statuses.filter(x=>x.key!=='done').map(x=>`<option value="${x.key}"${x.key==='todo'?' selected':''}>${esc(x.label)}</option>`).join('')}</select>`+
    `<input id="kadd-due" type="date" title="기한(선택)"><button onclick="addCard('${encodeURIComponent(path)}')">추가</button></div>`+
    `<div class="kanban">${cols.join('')}</div>`+
    `<div class="note-line">카드는 주간보고 때 PM이 정리하고, 오른쪽 담당에게 "카드 만들어줘·완료로 옮겨줘"라고 해도 바뀝니다.</div>`;
}
async function addCard(enc){
  const path = decodeURIComponent(enc);
  const t = document.getElementById('kadd-title'); const title = (t.value||'').trim(); if(!title) return;
  const r = await postJ('/api/cards', {project:path, title, status:document.getElementById('kadd-status').value,
    due:document.getElementById('kadd-due').value||null});
  if(!r.ok){ appAlert('카드 추가 실패', errMsg(r)); return; }
  fillKanban(path);
}
async function moveCard(id, status){ await postJ('/api/cards/'+id, {status}); fillKanban(CUR_ROOM); }
async function delCard(id){
  const c = KANBAN.cards.find(x=>x.id===id);
  const ok = await appConfirm({title:'카드 지우기', okText:'지우기', danger:true, body:(c?c.title+'\n\n':'')+'지운 카드는 되돌릴 수 없습니다.'});
  if(!ok) return;
  await fetch('/api/cards/'+id, {method:'DELETE'}); fillKanban(CUR_ROOM);
}
async function installProject(enc){
  const path = decodeURIComponent(enc);
  const r = await postJ('/api/projects/install', {path});
  if(!r.ok){ appAlert('설치 실패', errMsg(r)); return; }
  await loadData(); fillRoomMain(path);
}
async function uninstallProject(enc){
  const path = decodeURIComponent(enc);
  const ok = await appConfirm({title:`'${nameOfPath(path)}' 설치 제거`, okText:'제거', danger:true,
    body:'ohmypm/ 폴더를 통째로 지우고(안에 든 주간보고·제안·상태 메모 포함), CLAUDE.md·AGENTS.md의 ohmyPM 블록을 뗍니다.\n프로젝트의 다른 파일은 건드리지 않습니다.'});
  if(!ok) return;
  const r = await postJ('/api/projects/uninstall', {path});
  if(!r.ok){ appAlert('제거 실패', errMsg(r)); return; }
  await loadData(); fillRoomMain(path);
}

// ── 라우터 ─────────────────────────────────────────────
function go(hash){ if(location.hash===hash) route(); else location.hash = hash; }
function route(){
  clearInterval(pollTimer); clearInterval(tickTimer); clearTimeout(ENV_TIMER); ENV_TOKEN++; setStatus('');
  const h = decodeURIComponent(location.hash) || '#/dashboard';
  renderSidebar();
  if(h.startsWith('#/weekly')) renderWeekly();
  else if(h.startsWith('#/lab')) renderLab();
  else if(h.startsWith('#/agents')) renderAgents();
  else if(h.startsWith('#/ports')) renderPorts();
  else if(h.startsWith('#/post/')) renderPost(h.slice('#/post/'.length));
  else if(h.startsWith('#/board')) renderBoard();
  else if(h.startsWith('#/room/')) renderRoom(h.slice('#/room/'.length));
  else renderDashboard();
}
window.addEventListener('hashchange', route);
document.addEventListener('click', e=>{
  const ex = e.target.closest('[data-exclude]');
  if(ex){ excludeProject(ex.getAttribute('data-exclude')); return; }
  const rg = e.target.closest('[data-reg-port]');
  if(rg){ quickReg(rg.getAttribute('data-reg-port'), rg.getAttribute('data-reg-proj')); return; }
  const el = e.target.closest('[data-room]');
  if(el) go('#/room/'+encodeURIComponent(el.getAttribute('data-room')));
});

// ── 키보드로도 누를 수 있게 ─────────────────────────────────
// 메뉴·프로젝트 목록·칸반 화살표처럼 '버튼이 아닌 칸에 클릭만 단 것'은 Tab 키로 닿지 않았다.
// 화면이 다시 그려질 때마다 그런 칸을 찾아 Tab 순서에 넣고(tabindex), 화면 읽기 프로그램에는
// '버튼'이라고 알린다. Enter나 스페이스를 누르면 클릭한 것과 똑같이 동작한다.
const CLICKABLE = '[onclick]:not(button):not(a[href]):not(input):not(textarea):not(select),[data-room],[data-exclude],[data-reg-port]';
function markClickable(root){
  root.querySelectorAll(CLICKABLE).forEach(el=>{
    if(el.hasAttribute('tabindex')) return;
    el.tabIndex = 0;
    if(!el.hasAttribute('role') && el.tagName !== 'TR') el.setAttribute('role','button');
  });
}
new MutationObserver(()=>markClickable(document.body)).observe(document.body, {childList:true, subtree:true});
document.addEventListener('keydown', e=>{
  if((e.key==='Enter' || e.key===' ') && e.target.matches && e.target.matches(CLICKABLE)){
    e.preventDefault(); e.target.click();
  }
});
async function excludeProject(path){
  const ok = await appConfirm({title:`'${nameOfPath(path)}' 관리 제외`, okText:'제외', danger:true,
    body:'프로젝트 폴더는 그대로 둡니다(설치된 ohmypm/ 폴더도 남습니다 — 먼저 룸에서 설치 제거를 하세요).\nohmyPM의 게시판 글/댓글·대화 기록은 삭제됩니다.\n재스캔해도 다시 올라오지 않습니다.'});
  if(!ok) return;
  const r = await postJ('/api/projects/remove', {path});
  if(!r.ok){ appAlert('제외 실패', errMsg(r)); return; }
  await loadData(); go('#/');
}

(async ()=>{ await loadData(); if(!location.hash) location.hash='#/dashboard'; route(); })();
window.addEventListener('focus', ()=>loadData());
setInterval(loadData, 300000);
</script></body></html>"""


@router.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    # no-store: SPA 전체가 이 HTML 하나라, 캐시가 옛 JS를 재사용하면 새 기능이 반영 안 된다
    html = _HTML.replace("__SESSION_USD__", str(float(settings.session_usd) or 80.0))
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
