"""대시보드 화면 (HTML). 왼쪽 사이드바(탭 + 프로젝트 룸) + 오른쪽 뷰.

단일 HTML SPA — location.hash 로 뷰를 전환한다:
  #/dashboard   요약 + 프로젝트 카드 (헤더 '스캔(설치)')
  #/board       게시판 — 토론 시작/중지, 글 목록      #/post/<id> 글 상세
  #/weekly      주간보고 — 실행, 날짜별 보고, 프로젝트별 몫
  #/lab         랩실 — 연구원 3명의 위키·제안서·자문
  #/agents      담당 에이전트 — 점수·배운 것·모델
  #/ports       포트 — 등록·감지·시작/중지
  #/room/<path> 프로젝트 룸 — 설치 상태·주간보고 몫·제안서·점수 이력 + 담당 채팅

2026-10-09 2차 리뉴얼: 이슈·칸반·달력·일간보고 화면 제거. 데이터는 /api/* 를 fetch해 그린다.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ohmyPM</title>
<style>
  :root{--bg:#f5f6f8;--card:#fff;--line:#e4e6ea;--muted:#8b8f96;--ink:#20242b;--red:#d64545;--amber:#c77b1e;--green:#1a8a5a;--sb:#1f232b}
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
  aside .sec-label{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#7a808b;padding:14px 18px 5px;font-weight:700}
  aside .rooms{flex:1;overflow-y:auto}
  aside .room-item{display:flex;align-items:center;gap:8px;padding:7px 18px 7px 16px;cursor:pointer;font-size:12.5px;color:#b8bdc6;border-left:3px solid transparent}
  aside .room-item:hover{background:#272c35;color:#fff}
  aside .room-item.active{background:#2d333e;color:#fff;border-left-color:var(--green)}
  aside .room-item .dot{width:6px;height:6px;border-radius:50%;background:#4a515d;flex:0 0 6px}
  aside .room-item .dot.on{background:var(--green)}
  aside .room-item .rname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  aside .room-item .rx{margin-left:auto;font-size:11px;color:#7a808b;display:none;padding:0 3px;line-height:1}
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
  .tbadge.gold{background:#fdf3d6;color:#9a7b1e} .tbadge.green{background:#e7f3ec;color:#1f7a44} .tbadge.gray{background:#f1f3f6;color:var(--muted)}
  .ptable .reg-cell select,.ptable .reg-cell input,.ptable .reg-cell button{font-size:12px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;font-family:inherit;margin-right:5px}
  .ptable .reg-cell .ireg-label{width:120px}
  .ptable .reg-cell button{background:var(--green);color:#fff;border:none;cursor:pointer}
  .datebar{display:flex;gap:8px;overflow-x:auto;padding:2px;flex:0 0 auto;margin-bottom:12px}
  .datechip{flex:0 0 auto;padding:7px 14px;border:1px solid var(--line);border-radius:20px;background:var(--card);cursor:pointer;font-size:12.5px;font-weight:600;white-space:nowrap}
  .datechip:hover{background:#f1f3f6}
  .datechip.active{background:#e7f3ec;border-color:#bcdcc7}
  .datechip .cnt{margin-left:6px;color:var(--muted);font-weight:700;font-size:11px}
  .report{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;max-width:920px;margin-bottom:18px;font-size:14px;line-height:1.75}
  .report .mh{font-size:15px;margin:14px 0 5px}
  .wiki{flex:1;min-width:0;min-height:0;overflow-y:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .wiki-body{font-size:13.5px;line-height:1.7;color:#2b2f36}
  .wiki-body .mh{font-size:15px;margin:14px 0 5px}
  .wiki-body .mgap{height:9px}
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
    <main id="view">로딩…</main>
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
  const out=[]; let list=false;
  const close=()=>{ if(list){ out.push('</ul>'); list=false; } };
  for(const raw of (src||'').split('\n')){
    const line = raw.replace(/\s+$/,''); let m;
    if(m = line.match(/^(#{1,6})\s+(.*)$/)){ close(); out.push(`<div class="mh">${inl(m[2])}</div>`); }
    else if(m = line.match(/^\s*[-*]\s+(.*)$/)){ if(!list){ out.push('<ul>'); list=true; } out.push(`<li>${inl(m[1])}</li>`); }
    else if(!line.trim()){ close(); out.push('<div class="mgap"></div>'); }
    else { close(); out.push(`<div>${inl(line)}</div>`); }
  }
  close();
  return out.join('');
}
const todayStr = () => new Date().toISOString().slice(0,10);
const fmtTs = s => (s||'').slice(5,16);
const fmtCost = c => (c||c===0) ? '$'+Number(c).toFixed(2) : '-';
const getJ = (url) => fetch(url).then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); });   // 404 등은 예외 → 호출부 catch가 빈 값으로 처리
const postJ = (url, body) => fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
  body: body===undefined ? undefined : JSON.stringify(body)}).then(r=>r.json()).catch(()=>({ok:false,error:'서버에 연결하지 못했습니다'}));

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

let PROJECTS = [];                      // 마지막 로드 캐시
let pollTimer = null;                   // 뷰별 자동 새로고침 타이머(하나만)
let tickTimer = null;                   // 토론 카운트다운(1초)
let CUR_ROOM = null;
let portEditing = false;

async function loadData(){
  try{ PROJECTS = await getJ('/api/projects'); }catch(e){ PROJECTS = []; }
  renderSidebar();
}
const nameOfPath = p => (PROJECTS.find(x=>x.path===p)||{}).name || p;

// ── 사이드바 ───────────────────────────────────────────
function renderSidebar(){
  const cur = decodeURIComponent(location.hash);
  const ordered = PROJECTS.slice().sort((a,b)=>a.name.localeCompare(b.name,'ko'));
  document.getElementById('rooms').innerHTML = ordered.map(p=>{
    const active = cur === '#/room/'+p.path ? ' active':'';
    return `<div class="room-item${active}" data-room="${escAttr(p.path)}" title="${escAttr(p.path)}">`+
           `<span class="dot${p.installed?' on':''}"></span><span class="rname">${esc(p.name)}</span>`+
           `<span class="rx" data-exclude="${escAttr(p.path)}" title="관리 제외">x</span></div>`;
  }).join('') || '<div style="color:#7a808b;font-size:12px;padding:8px 18px">스캔을 눌러보세요</div>';
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
  document.getElementById('view').innerHTML = '<div class="empty">불러오는 중…</div>';
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
  const ordered = PROJECTS.slice().sort((a,b)=>a.name.localeCompare(b.name,'ko'));
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
  if(r.projects===undefined){ appAlert('스캔 실패', r.error||'알 수 없는 오류'); }
  else appAlert('스캔 완료', `프로젝트 ${r.projects}개\n새로 설치 ${r.installed} · 이미 설치 ${r.already} · 자기 자신 제외 ${r.self_skipped}`+
    (r.errors&&r.errors.length?`\n실패 ${r.errors.length}: ${r.errors.map(e=>e.name).join(', ')}`:''));
  route();
}

// ── 채팅 공용 ─────────────────────────────────────────
function chatMarkup(ph){
  return `<div class="chat"><div class="stream" id="stream"><div class="chat-empty">불러오는 중…</div></div>`+
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
    return `<div class="msg ${mine?'user':'agent'}">`+(mine?'':`<div class="who">${esc(m.author)}</div>`)+
           `<div class="md">${md(m.body)}</div><div class="ts">${esc(fmtTs(m.created_at))}</div></div>`;
  }).join('') : '<div class="chat-empty">아직 대화가 없습니다. 첫 메시지를 남겨보세요.</div>';
  if(agentRoom && msgs.length && msgs[msgs.length-1].author === 'user')
    html += pendingMarkup(room, msgs[msgs.length-1], '에이전트');
  stream.innerHTML = html;
  if(!silent || atBottom) stream.scrollTop = stream.scrollHeight;
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
  if(!r.ok){ appAlert('다시 요청 실패', r.error||'알 수 없는 오류'); return; }
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
    '<div id="board">불러오는 중…</div>';
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
  if(!posts.length){ box.innerHTML = '<div class="empty">아직 글이 없습니다 — 토론 시작을 누르면 담당들이 글을 올립니다</div>'; return; }
  box.innerHTML = posts.map(p=>{
    const n = (p.comments||[]).length;
    const day = (p.day || p.created_at || '').slice(0,10);
    return `<div class="prow" onclick="go('#/post/${p.id}')"><span class="prow-t">${esc(p.title)}</span>`+
      `<span class="prow-meta">${esc(day)} · ${esc(p.author)} · 조회 ${p.views||0} · 좋아요 ${p.likes||0}${(p.dislikes||0)?' · 싫어요 '+p.dislikes:''} · 댓글 <span class="c">${n}</span></span></div>`;
  }).join('');
}
async function startSession(){
  const minutes = parseInt((document.getElementById('bs-min')||{}).value||'30',10);
  const b = document.getElementById('btn-start'); if(b){ b.disabled=true; b.textContent='시작하는 중…'; }
  const r = await postJ('/api/board/session', {minutes});
  if(!r.ok){ appAlert('토론을 시작하지 못함', r.error||'알 수 없는 오류'); if(b){ b.disabled=false; b.textContent='토론 시작'; } }
  SESSION = null; fillBoardList();
}
async function stopSession(){
  const ok = await appConfirm({title:'토론 중지', okText:'중지', danger:true,
    body:'지금 돌고 있는 담당의 호출은 끝까지 가고, 새 호출만 멈춥니다. 끝난 뒤 복기는 하지 않습니다.'});
  if(!ok) return;
  const r = await postJ('/api/board/session/stop');
  if(!r.ok) appAlert('중지 실패', r.error||'알 수 없는 오류');
  SESSION = null; fillBoardList();
}

// ── 글 상세 ───────────────────────────────────────────
function renderPost(id){
  setHeader('게시판', {});
  document.getElementById('view').innerHTML = '<div id="post">불러오는 중…</div>';
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
let WEEKLY = [], WEEKLY_IDX = 0;
function renderWeekly(){
  setHeader('주간보고', {buttons:[{id:'btn-weekly', label:'주간보고 실행', onclick:'runWeekly()'}]});
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:10px">최근 7일 커밋과 각 프로젝트 ohmypm/state.md를 모아 요약합니다. 프로젝트별 몫은 그 프로젝트의 ohmypm/weekly.md에도 적힙니다.</div>'+
    '<div class="datebar" id="w-datebar">불러오는 중…</div><div id="w-body"></div>';
  clearInterval(pollTimer);
  fillWeekly();
  pollTimer = setInterval(pollWeeklyJob, 5000);
}
async function pollWeeklyJob(){
  const j = await getJ('/api/jobs/weekly').catch(()=>null);
  const b = document.getElementById('btn-weekly'); if(!b) return;
  if(j && j.running){ b.disabled = true; b.textContent = '작성 중…'; setStatus(`주간보고 작성 중 (${esc((j.started_at||'').slice(11,16))} 시작) — 몇 분 걸립니다`); }
  else{
    if(b.disabled){ b.disabled = false; b.textContent = '주간보고 실행'; fillWeekly(); }
    if(j && j.finished_at) setStatus(`마지막 실행 ${esc((j.finished_at||'').slice(5,16))} · ${j.ok?'완료':'실패'}${j.error?' · '+esc(j.error):''}${j.result&&j.result.cost_usd!=null?' · 비용 '+fmtCost(j.result.cost_usd):''}`);
  }
}
async function fillWeekly(){
  try{ WEEKLY = await getJ('/api/weekly'); }catch(e){ WEEKLY = []; }
  const bar = document.getElementById('w-datebar'); if(!bar) return;
  pollWeeklyJob();
  if(!WEEKLY.length){ bar.innerHTML = ''; document.getElementById('w-body').innerHTML = '<div class="empty">아직 주간보고가 없습니다 — 오른쪽 위 버튼으로 실행하세요</div>'; return; }
  if(WEEKLY_IDX >= WEEKLY.length) WEEKLY_IDX = 0;
  bar.innerHTML = WEEKLY.map((d,i)=>`<div class="datechip${i===WEEKLY_IDX?' active':''}" onclick="WEEKLY_IDX=${i};fillWeekly()">${esc(d.date)}<span class="cnt">${d.projects.length}</span></div>`).join('');
  const d = WEEKLY[WEEKLY_IDX];
  const body = document.getElementById('w-body'); body.innerHTML = '<div class="empty">불러오는 중…</div>';
  const msgs = await getJ('/api/messages?room='+encodeURIComponent(d.overall_room)).catch(()=>[]);
  const report = msgs.length ? msgs[msgs.length-1].body : '(보고 본문 없음)';
  body.innerHTML = `<div class="report md">${md(report)}</div>`+
    `<section><h2>프로젝트별 몫 (${d.projects.length})</h2>`+
    d.projects.map((p,i)=>`<div class="prow" onclick="toggleWeeklyProj(${i},this)"><span class="prow-t">${esc(p.name)}</span>`+
      `<span class="prow-meta">${p.written?'<span class="tbadge green">ohmypm/weekly.md 기록</span>':'<span class="tbadge gray">미설치 — 파일 기록 안 함</span>'}</span></div><div class="prow-body" id="wp-${i}" hidden></div>`).join('')+`</section>`;
}
async function toggleWeeklyProj(i, el){
  const box = document.getElementById('wp-'+i); if(!box) return;
  if(!box.hidden){ box.hidden = true; return; }
  box.hidden = false; box.innerHTML = '불러오는 중…';
  const p = WEEKLY[WEEKLY_IDX].projects[i];
  const msgs = await getJ('/api/messages?room='+encodeURIComponent(p.room)).catch(()=>[]);
  box.innerHTML = `<div class="md">${md(msgs.length ? msgs[msgs.length-1].body : '(없음)')}</div>`;
}
async function runWeekly(){
  const b = document.getElementById('btn-weekly'); if(b){ b.disabled=true; b.textContent='작성 중…'; }
  const r = await postJ('/api/weekly/run');
  if(!r.ok){ appAlert('실행 실패', r.error||'알 수 없는 오류'); if(b){ b.disabled=false; b.textContent='주간보고 실행'; } }
  pollWeeklyJob();
}

// ── 랩실 ────────────────────────────────────────────────
let LAB = [], LAB_IDX = 0, LAB_SUB = 0;
function renderLab(){
  setHeader('랩실', {buttons:[{id:'btn-lab', label:'조사 실행', onclick:'runLab()'}]});
  document.getElementById('view').innerHTML =
    '<div id="lab-top" class="note-line" style="padding-bottom:10px">불러오는 중…</div>'+
    '<div class="room-layout"><div class="wiki" id="lab-wiki"></div>'+
    '<div class="room-side"><div class="side-h">제안서</div><div class="props" id="lab-props"></div>'+
    '<div class="side-h">연구원에게 묻기</div>'+chatMarkup('이 주제에 대해 물어보세요')+'</div></div>';
  clearInterval(pollTimer);
  loadLab();
}
const labRoom = id => 'lab::'+id;
async function loadLab(){
  try{ LAB = await getJ('/api/lab'); }catch(e){ LAB = []; }
  const top = document.getElementById('lab-top'); if(!top) return;
  if(!LAB.length){ top.textContent = '연구원이 없습니다'; return; }
  if(LAB_IDX >= LAB.length) LAB_IDX = 0;
  const r = LAB[LAB_IDX];
  top.innerHTML = `<div class="etabs">${LAB.map((x,i)=>`<span class="etab${i===LAB_IDX?' on':''}" onclick="LAB_IDX=${i};LAB_SUB=0;loadLab()">${esc(x.name)}</span>`).join('')}</div>`+
    `<b style="color:var(--ink);font-size:14px">${esc(r.name)}</b> · ${esc(r.topic)} · 위키 ${r.wiki_chars}자 · 마지막 조사 ${esc(r.last_run?r.last_run.slice(0,16):'없음')}`;
  const b = document.getElementById('btn-lab');
  if(b){ b.disabled = !!r.running; b.textContent = r.running ? '조사 중…' : '조사 실행'; }
  setStatus(r.running ? `<span class="live">${esc(r.name)} 조사 중</span> — 웹 조사라 몇 분 걸립니다` : '');
  const w = await getJ('/api/lab/'+r.id+'/wiki').catch(()=>({tabs:[]}));
  const wikiBox = document.getElementById('lab-wiki');
  if(wikiBox){
    const tabs = w.tabs||[];
    if(LAB_SUB >= tabs.length) LAB_SUB = 0;
    const sub = tabs.length>1 ? `<div class="etabs">${tabs.map((t,i)=>`<span class="etab${i===LAB_SUB?' on':''}" onclick="LAB_SUB=${i};loadLab()">${esc(t.title)}</span>`).join('')}</div>` : '';
    const text = tabs.length ? tabs[LAB_SUB].wiki : '';
    wikiBox.innerHTML = '<div class="side-h">연구 위키</div>'+sub+
      (text ? `<div class="md wiki-body">${md(text)}</div>` : '<div class="empty" style="padding:20px">아직 비어 있음 — 조사 실행을 누르면 채워집니다</div>');
  }
  fillProposals(r.id);
  const input = document.getElementById('msg-input');
  if(input){ input.onkeydown = ev=>{ if(ev.key==='Enter' && !ev.shiftKey){ ev.preventDefault(); sendLabQ(r.id); }}; }
  loadMessages(labRoom(r.id), false, true);
  clearInterval(pollTimer);
  pollTimer = setInterval(()=>{ loadMessages(labRoom(r.id), true, true); if(r.running) loadLab(); }, 4000);
}
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
  if(!res.ok){ appAlert('조사를 시작하지 못함', res.error||'알 수 없는 오류'); if(b){ b.disabled=false; b.textContent='조사 실행'; } }
  loadLab();
}

// ── 에이전트 ───────────────────────────────────────────
let AGENT_LIST = [], AGENT_SEL = null;
function renderAgents(){
  setHeader('에이전트', {});
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:12px">담당 에이전트별 누적 점수(글 좋아요·조회 − 싫어요 + 댓글 좋아요 − 싫어요)와 토론 끝에 복기한 \'배운 것\'. 행을 누르면 회차별 이력이 아래에 펼쳐집니다. 모델 열에서 이 담당의 headless 모델을 바꿀 수 있습니다.</div>'+
    '<div id="agents">불러오는 중…</div><div id="agent-hist"></div>';
  clearInterval(pollTimer);
  fillAgents();
}
async function fillAgents(){
  let list = [];
  try{ list = await getJ('/api/agents'); }catch(e){ return; }
  const box = document.getElementById('agents'); if(!box) return;
  if(!list.length){ box.innerHTML = '<div class="empty">담당 없음</div>'; return; }
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
  box.innerHTML = '<div class="note-line">불러오는 중…</div>';
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
  if(!r.ok) appAlert('모델 변경 실패', r.error||'알 수 없는 오류');
  fillAgents();
}

// ── 포트 ───────────────────────────────────────────────
function renderPorts(){
  setHeader('포트', {});
  const opts = PROJECTS.map(p=>`<option value="${escAttr(p.path)}">${esc(p.name)}</option>`).join('');
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:12px">지금 열려 있는 포트를 전부 보여주고, 프로세스 명령줄의 경로로 어느 프로젝트 것인지 맞춥니다. 등록하면 떠 있는지·충돌 여부를 보고, 실행 명령을 함께 등록하면 여기서 켜고 끌 수 있습니다.</div>'+
    '<div id="ports">불러오는 중…</div>'+
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
  box.innerHTML = html;
}
function inlineReg(port, el){
  portEditing = true;
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
    `<div class="room-layout"><div class="room-main" id="room-main"><div class="empty">불러오는 중…</div></div>`+
    `<div class="room-side"><div class="side-h">${esc(name)} 담당 에이전트</div>${chatMarkup('담당에게 물어보거나 시키세요')}</div></div>`;
  fillRoomMain(path);
  bindChat(path, true);
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
      if(msgs.length){ weeklyHtml = `<div class="report md"><div class="mh">${esc(d.date)}</div>${md(msgs[msgs.length-1].body)}</div>`; } break; }
  }
  main.innerHTML =
    `<section><div class="kv"><div><b>경로</b> ${esc(path)}</div>`+
      `<div><b>설치</b> <span class="badge ${p.installed?'on':'off'}">${p.installed?'ohmypm/ 설치됨':'미설치'}</span> `+
      (p.installed?`<span class="mini-btn red" onclick="uninstallProject('${encodeURIComponent(path)}')">설치 제거</span>`:`<span class="mini-btn" onclick="installProject('${encodeURIComponent(path)}')">설치</span>`)+`</div></div></section>`+
    `<section><h2>최근 주간보고 몫</h2>${weeklyHtml}</section>`+
    `<section><h2>이 프로젝트 대상 제안서 (${props.length})</h2>${props.length?`<div class="props" style="max-height:none">${props.map(x=>proposalHtml(x,true)).join('')}</div>`:'<div class="note-line">아직 제안이 없습니다</div>'}</section>`+
    `<section><h2>토론 점수 이력</h2>${scoreTable(scores)}</section>`;
}
async function installProject(enc){
  const path = decodeURIComponent(enc);
  const r = await postJ('/api/projects/install', {path});
  if(!r.ok){ appAlert('설치 실패', r.error||'알 수 없는 오류'); return; }
  await loadData(); fillRoomMain(path);
}
async function uninstallProject(enc){
  const path = decodeURIComponent(enc);
  const ok = await appConfirm({title:`'${nameOfPath(path)}' 설치 제거`, okText:'제거', danger:true,
    body:'ohmypm/ 폴더를 통째로 지우고(안에 든 주간보고·제안·상태 메모 포함), CLAUDE.md·AGENTS.md의 ohmyPM 블록을 뗍니다.\n프로젝트의 다른 파일은 건드리지 않습니다.'});
  if(!ok) return;
  const r = await postJ('/api/projects/uninstall', {path});
  if(!r.ok){ appAlert('제거 실패', r.error||'알 수 없는 오류'); return; }
  await loadData(); fillRoomMain(path);
}

// ── 라우터 ─────────────────────────────────────────────
function go(hash){ if(location.hash===hash) route(); else location.hash = hash; }
function route(){
  clearInterval(pollTimer); clearInterval(tickTimer); setStatus('');
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
async function excludeProject(path){
  const ok = await appConfirm({title:`'${nameOfPath(path)}' 관리 제외`, okText:'제외', danger:true,
    body:'프로젝트 폴더는 그대로 둡니다(설치된 ohmypm/ 폴더도 남습니다 — 먼저 룸에서 설치 제거를 하세요).\nohmyPM의 게시판 글/댓글·대화 기록은 삭제됩니다.\n재스캔해도 다시 올라오지 않습니다.'});
  if(!ok) return;
  const r = await postJ('/api/projects/remove', {path});
  if(!r.ok){ appAlert('제외 실패', r.error||'알 수 없는 오류'); return; }
  await loadData(); go('#/');
}

(async ()=>{ await loadData(); if(!location.hash) location.hash='#/dashboard'; route(); })();
window.addEventListener('focus', ()=>loadData());
setInterval(loadData, 300000);
</script></body></html>"""


@router.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    # no-store: SPA 전체가 이 HTML 하나라, 캐시가 옛 JS를 재사용하면 새 기능이 반영 안 된다
    return HTMLResponse(_HTML, headers={"Cache-Control": "no-store"})
