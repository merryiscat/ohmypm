"""대시보드 화면 (HTML). 왼쪽 사이드바(대시보드 / 전체 채팅방 / 프로젝트 룸) + 오른쪽 뷰.

단일 HTML SPA — location.hash 로 뷰를 전환한다:
  #/dashboard          : 요약 바 → 임박 기한 → 프로젝트 카드
  #/chat/global        : 에이전트·사용자 전체 채팅방(메시지 보드)
  #/room/<프로젝트path> : 프로젝트 룸(그 프로젝트 이슈 + 전용 채팅방)

데이터는 /api/projects·/api/issues·/api/messages 를 fetch해 그린다.
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
  /* 레이아웃: 사이드바 + 본문 */
  .app{display:flex;height:100vh;overflow:hidden}   /* 앱 셸을 뷰포트에 가둔다 — 스크롤은 각 영역 내부에서만 */
  aside{width:230px;flex:0 0 230px;background:var(--sb);color:#cfd3da;position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column}
  aside .brand{font-size:16px;font-weight:700;color:#fff;padding:16px 18px;border-bottom:1px solid #2c313b}
  aside nav{padding:8px 0}
  aside .nav-item{display:flex;align-items:center;gap:9px;padding:9px 18px;cursor:pointer;font-size:13.5px;color:#cfd3da;border-left:3px solid transparent}
  aside .nav-item:hover{background:#272c35;color:#fff}
  aside .nav-item.active{background:#2d333e;color:#fff;border-left-color:var(--green)}
  aside .nav-item .cnt{margin-left:auto;font-size:11px;background:#3a414d;color:#cfd3da;border-radius:20px;padding:1px 7px}
  aside .sec-label{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#7a808b;padding:14px 18px 5px;font-weight:700}
  aside .rooms{flex:1;overflow-y:auto}
  aside .room-item{display:flex;align-items:center;gap:8px;padding:7px 18px 7px 16px;cursor:pointer;font-size:12.5px;color:#b8bdc6;border-left:3px solid transparent}
  aside .room-item:hover{background:#272c35;color:#fff}
  aside .room-item.active{background:#2d333e;color:#fff;border-left-color:var(--green)}
  aside .room-item .dot{width:6px;height:6px;border-radius:50%;background:#4a515d;flex:0 0 6px}
  aside .room-item .dot.u{background:var(--amber)} aside .room-item .dot.d{background:var(--red)}
  aside .room-item .rname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  aside .room-item .rc{margin-left:auto;font-size:10.5px;color:#7a808b}
  /* 본문 */
  .body{flex:1;min-width:0;display:flex;flex-direction:column}
  header{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);padding:12px 22px;display:flex;align-items:center;gap:18px;z-index:10}
  header h1{font-size:17px;margin:0}
  .summary{display:flex;gap:16px;color:var(--muted);font-size:13px}
  .summary b{color:var(--ink);font-size:15px}
  .summary .hot b{color:var(--red)}
  .actions{margin-left:auto;display:flex;gap:8px}
  /* hidden 속성이 display:flex를 이기게 — 뷰별 헤더 토글이 실제로 먹도록 */
  .summary[hidden],.actions[hidden]{display:none!important}
  button{padding:7px 14px;border:none;background:var(--green);color:#fff;border-radius:6px;cursor:pointer;font-size:13px}
  button.ghost{background:#fff;color:var(--ink);border:1px solid var(--line)}
  button:disabled{opacity:.55;cursor:default}
  main{padding:20px 22px;max-width:1500px;margin:0 auto;width:100%;flex:1;min-height:0;display:flex;flex-direction:column;overflow-y:auto}
  section{margin-bottom:26px}
  section>h2{font-size:13px;letter-spacing:.02em;color:var(--muted);text-transform:uppercase;margin:0 0 10px;font-weight:700}
  /* 임박 기한 */
  .soon{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  .soon .row{display:flex;align-items:center;gap:12px;padding:9px 14px;border-top:1px solid var(--line);font-size:13px}
  .soon .row:first-child{border-top:none}
  .soon .d{font-weight:700;min-width:96px}
  .soon .d.today{color:var(--red)} .soon .d.week{color:var(--amber)}
  .soon .proj{color:var(--muted);min-width:130px;font-size:12px}
  /* 프로젝트 그리드 */
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card h3{margin:0 0 9px;font-size:14.5px;display:flex;align-items:center;gap:8px}
  .card h3 .open{margin-left:auto;font-size:11.5px;color:var(--green);cursor:pointer}
  .badge{font-size:11px;padding:1px 7px;border-radius:20px;font-weight:700}
  .badge.u{background:#eef1fb;color:#3a52a8} .badge.d{background:#fdeceb;color:var(--red)}
  .issue{font-size:12.5px;padding:4px 0;border-top:1px solid #f2f3f5;line-height:1.45;color:#3a3f47}
  .issue .due{color:var(--red);font-weight:700}
  .more{color:var(--muted);font-size:12px;padding-top:4px}
  .note-line{color:var(--muted);font-size:12px;padding:8px 2px 0}
  .empty{color:var(--muted);text-align:center;padding:40px}
  /* 채팅방 */
  .chat{display:flex;flex-direction:column;flex:1;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;min-height:0}
  .chat .stream{flex:1;overflow-y:auto;padding:16px 18px;display:flex;flex-direction:column;gap:10px;min-height:340px}
  .msg{max-width:74%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
  .msg .who{font-size:11px;color:var(--muted);margin-bottom:2px;font-weight:700}
  .msg .ts{font-size:10.5px;color:var(--muted);margin-top:3px}
  .msg.user{align-self:flex-end;background:#e7f3ec;border:1px solid #cfe6da}
  .msg.agent{align-self:flex-start;background:#f1f3f6;border:1px solid var(--line)}
  .chat .composer{display:flex;gap:8px;padding:12px;border-top:1px solid var(--line);background:#fafbfc}
  .chat .composer textarea{flex:1;padding:9px 12px;border:1px solid var(--line);border-radius:8px;font-size:13.5px;font-family:inherit;resize:none;line-height:1.45;max-height:140px;overflow-y:auto}
  .chat .composer .as{width:110px;padding:9px 8px;border:1px solid var(--line);border-radius:8px;font-size:12.5px;background:#fff}
  .chat-empty{color:var(--muted);text-align:center;margin:auto;padding:30px}
  .msg.pending{align-self:flex-start;background:#f7f8fa;border:1px dashed var(--line);color:var(--muted);font-style:italic}
  /* 프로젝트 룸: 왼쪽 내용 + 오른쪽 세로 채팅 패널 */
  .room-layout{display:flex;gap:16px;flex:1;min-height:0}
  .room-main{flex:1;min-width:0;min-height:0;overflow-y:auto}
  .room-main>section{margin-bottom:0}
  .room-side{width:420px;flex:0 0 420px;display:flex;flex-direction:column;min-height:0}
  .room-side .side-h{font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.02em;margin:0 2px 8px}
  @media(max-width:1000px){.room-layout{flex-direction:column}.room-side{width:auto;flex:none}}
  /* 달력 */
  .cal{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:14px}
  .cal-h{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-weight:700;font-size:13px}
  .cal-h span{min-width:110px}
  .cal-h button{padding:2px 10px;background:#f1f3f6;color:var(--ink);border:1px solid var(--line)}
  .cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
  .cal-grid .dow{font-size:10.5px;color:var(--muted);text-align:center;padding:2px}
  .cal-cell{min-height:46px;min-width:0;overflow:hidden;border:1px solid #eef0f2;border-radius:6px;padding:3px}
  .cal-cell.out{background:#fafbfc}
  .cal-cell.today{border-color:var(--green);border-width:2px}
  .cal-cell .dd{font-size:10.5px;color:var(--muted)}
  .cal-cell .ev{background:#fdeceb;color:var(--red);border-radius:4px;padding:0 3px;margin-top:2px;font-size:10px;line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:default}
  /* 칸반 */
  .kanban{display:flex;gap:10px;align-items:flex-start}
  .kcol{flex:1;min-width:0;background:#eef0f3;border-radius:10px;padding:8px}
  .kcol>h3{font-size:11.5px;color:var(--muted);text-transform:uppercase;margin:4px 4px 8px;font-weight:700;display:flex;gap:6px;align-items:center}
  .kcol>h3 .n{background:#d9dde3;color:#555;border-radius:20px;padding:0 7px;font-size:11px}
  .kcard{background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 9px;margin-bottom:7px;font-size:12.5px;line-height:1.45;color:#3a3f47}
  .kcard .due{color:var(--red);font-weight:700;font-size:11px}
  .kcard .mv{display:flex;gap:6px;margin-top:7px}
  .kcard .mv button{padding:1px 9px;font-size:12px;background:#f1f3f6;color:var(--ink);border:1px solid var(--line);border-radius:5px}
  .kcol .col-empty{color:var(--muted);font-size:12px;padding:8px 4px}
  /* 게시판(글+댓글) */
  .post{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:12px;max-width:920px}
  .post-h{display:flex;align-items:center;gap:10px;margin-bottom:6px}
  .post-title{font-weight:700;font-size:14px}
  .post-day{color:var(--muted);font-size:11.5px;margin-left:auto}
  .post-body{font-size:13px;color:#3a3f47;line-height:1.5;white-space:pre-wrap;margin-bottom:10px}
  .cmts{border-top:1px solid #f2f3f5;padding-top:8px;display:flex;flex-direction:column;gap:6px}
  .cmt{font-size:12.5px;color:#3a3f47;line-height:1.45;background:#f7f8fa;border-radius:6px;padding:6px 9px}
  .cmt-who{font-weight:700;color:var(--green);margin-right:5px}
  .cmt.none{color:var(--muted);background:none;padding:2px 0;font-style:italic}
  .cmt-who{display:block;margin-bottom:2px}
  /* 마크다운 렌더 */
  .md .mh{font-weight:700;margin:6px 0 2px}
  .md ul{margin:4px 0;padding-left:18px} .md li{margin:1px 0}
  .md code{background:#eceef1;border-radius:4px;padding:0 3px;font-size:.9em;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
  .md .mgap{height:5px} .md>div:first-child,.md>ul:first-child{margin-top:0}
  /* 게시판 목록(제목 행) → 클릭해 글 상세로 */
  .prow{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:11px 14px;margin-bottom:8px;cursor:pointer;max-width:920px}
  .prow:hover{border-color:var(--green)}
  .prow-t{font-weight:600;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .prow-meta{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}
  .prow-meta .c{color:var(--green);font-weight:700}
  .back{color:var(--green);cursor:pointer;font-size:13px;margin-bottom:12px;display:inline-block}
  .cmt-form{display:flex;gap:8px;margin-top:12px}
  .cmt-form textarea{flex:1;padding:8px 11px;border:1px solid var(--line);border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;min-height:38px}
  .cmt.user{background:#e7f3ec;border:1px solid #cfe6da}
</style></head><body>
<div class="app">
  <aside>
    <div class="brand">ohmyPM</div>
    <nav>
      <div class="nav-item" data-nav="dashboard" onclick="go('#/dashboard')">대시보드</div>
      <div class="nav-item" data-nav="board" onclick="go('#/board')">게시판</div>
      <div class="nav-item" data-nav="daily" onclick="go('#/chat/daily')">일간보고</div>
    </nav>
    <div class="sec-label">프로젝트 룸</div>
    <div class="rooms" id="rooms"></div>
  </aside>

  <div class="body">
    <header>
      <h1 id="hdr-title">대시보드</h1>
      <div class="summary" id="hdr-summary">
        <span>프로젝트 <b id="s-proj">–</b></span>
        <span>이슈 <b id="s-iss">–</b></span>
        <span class="hot">임박 <b id="s-soon">–</b></span>
      </div>
      <div class="actions" id="hdr-actions">
        <button class="ghost" onclick="doJudge()" id="btn-judge">판정</button>
        <button onclick="doScan()">스캔</button>
      </div>
    </header>
    <main id="view">로딩…</main>
  </div>
</div>
<script>
const esc = s => (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// HTML 속성값용(따옴표까지 이스케이프) — Windows 경로엔 \ 와 " 가 섞여 인라인 onclick을 깨므로 data-*로 넘긴다
const escAttr = s => esc(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
// 가벼운 마크다운 렌더 — 에이전트 답에 ## 제목·**굵게**·- 목록·`코드`가 섞여 온다(외부 lib 없이)
function md(src){
  const e = s => s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const inl = s => e(s).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+?)\*\*/g,'<strong>$1</strong>');
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
const clean = s => (s||'').replace(/~~/g,'').trim();          // 취소선 마크 제거
const isCancelled = s => /~~.+~~/.test(s||'');                 // ~~...~~ = 취소 → 제외
const todayStr = () => new Date().toISOString().slice(0,10);
function daysTo(due){ return Math.round((new Date(due)-new Date(todayStr()))/86400000); }

let PROJECTS = [], ISSUES = [];        // 마지막 로드 캐시
let pollTimer = null;                   // 채팅 자동 새로고침 타이머
let CUR_ROOM = null;                    // 현재 열린 프로젝트 룸 path
let CAL_YM = null;                      // 달력이 보여주는 {y, m} (m=0-based)

// ── 데이터 로드 ─────────────────────────────────────────
async function loadData(){
  const [ps, allIs] = await Promise.all([
    fetch('/api/projects').then(r=>r.json()),
    fetch('/api/issues').then(r=>r.json()),
  ]);
  PROJECTS = ps;
  ISSUES = allIs.filter(i => !isCancelled(i.title) && i.verdict !== 'drop');  // 노이즈 컷
  renderSidebar();
}

function issuesByProject(){
  const m = {}; ISSUES.forEach(i => (m[i.project]=m[i.project]||[]).push(i)); return m;
}
const nameOfPath = p => (PROJECTS.find(x=>x.path===p)||{}).name || p;

// ── 사이드바(프로젝트 룸 목록) ───────────────────────────
function renderSidebar(){
  const byProj = issuesByProject();
  const ordered = PROJECTS.slice().sort((a,b)=>(byProj[b.path]||[]).length-(byProj[a.path]||[]).length);
  const cur = decodeURIComponent(location.hash);
  document.getElementById('rooms').innerHTML = ordered.map(p=>{
    const items = byProj[p.path]||[];
    const u = items.filter(i=>i.kind==='unresolved').length;
    const d = items.filter(i=>i.kind==='deadline').length;
    const dot = d?'d':(u?'u':'');
    const active = cur === '#/room/'+p.path ? ' active':'';
    return `<div class="room-item${active}" data-room="${escAttr(p.path)}">`+
           `<span class="dot ${dot}"></span><span class="rname">${esc(p.name)}</span>`+
           (items.length?`<span class="rc">${items.length}</span>`:'')+`</div>`;
  }).join('') || '<div style="color:#7a808b;font-size:12px;padding:8px 18px">스캔을 눌러보세요</div>';
  // 사이드바 상단 nav 활성화 표시
  document.querySelectorAll('[data-nav]').forEach(el=>el.classList.remove('active'));
  const view = (cur.startsWith('#/board') || cur.startsWith('#/post')) ? 'board'
             : cur.startsWith('#/chat/daily') ? 'daily'
             : (cur.startsWith('#/room') ? null : 'dashboard');
  if(view) document.querySelector(`[data-nav="${view}"]`)?.classList.add('active');
}

// ── 대시보드 뷰 ─────────────────────────────────────────
function renderDashboard(){
  setHeader('대시보드', {summary:true, actions:true});   // 판정·스캔은 전역 액션 → 대시보드에서만
  const is = ISSUES;
  const judged = i => i.verdict === 'keep' || i.verdict === 'reclass';
  const soon = is.filter(i => i.kind==='deadline' && judged(i) && i.due && daysTo(i.due) <= 7)
                 .sort((a,b)=> a.due.localeCompare(b.due));
  const pendingJudge = is.filter(i => i.kind==='deadline' && !i.verdict).length;
  const conditional = is.filter(i => i.kind==='conditional').length;
  document.getElementById('s-proj').textContent = PROJECTS.length;
  document.getElementById('s-iss').textContent = is.length;
  document.getElementById('s-soon').textContent = soon.length;

  const noteParts = [];
  if(pendingJudge) noteParts.push(`미판정 기한 후보 ${pendingJudge}건 — '판정'을 눌러 가려내세요`);
  if(conditional) noteParts.push(`조건부 보류 ${conditional}건(기한 아님)`);

  let soonHtml = '';
  if(soon.length || pendingJudge || conditional){
    const rows = soon.map(i=>{
      const dd = daysTo(i.due); const cls = dd<=0?'today':'week';
      const label = dd<0?`${-dd}일 지남`:(dd===0?'오늘':`${dd}일 후`);
      return `<div class="row"><span class="d ${cls}">${i.due} · ${label}</span>`+
             `<span class="proj">${esc(nameOfPath(i.project))}</span>`+
             `<span>${esc(clean(i.title))}</span></div>`;
    }).join('') || '<div class="row"><span class="proj">확정된 임박 기한 없음</span></div>';
    soonHtml = `<section><h2>임박 기한 (7일 내)</h2><div class="soon">${rows}</div>`+
               (noteParts.length?`<div class="note-line">${esc(noteParts.join(' · '))}</div>`:'')+`</section>`;
  }

  const byProj = issuesByProject();
  const ordered = PROJECTS.slice().sort((a,b)=>(byProj[b.path]||[]).length-(byProj[a.path]||[]).length);
  const cards = ordered.map(p=>{
    const items = byProj[p.path]||[];
    const u = items.filter(i=>i.kind==='unresolved').length;
    const d = items.filter(i=>i.kind==='deadline').length;
    return `<div class="card"><h3>${esc(p.name)}`+
      (u?`<span class="badge u">미해결 ${u}</span>`:'')+
      (d?`<span class="badge d">기한 ${d}</span>`:'')+
      `<span class="open" data-room="${escAttr(p.path)}">룸 열기</span></h3>`+
      items.slice(0,8).map(i=>`<div class="issue">${i.due?`<span class="due">${i.due}</span> `:''}${esc(clean(i.title))}</div>`).join('')+
      (items.length>8?`<div class="more">…외 ${items.length-8}건</div>`:(items.length?'':'<div class="more">이슈 없음</div>'))+
      `</div>`;
  }).join('');
  document.getElementById('view').innerHTML = soonHtml +
    `<section><h2>프로젝트</h2><div class="grid">${cards||'<div class="empty">관리 대상 없음 — 스캔을 눌러보세요</div>'}</div></section>`;
}

// ── 헤더 토글 (뷰별로 요약바·액션버튼 노출 제어) ──────────
function setHeader(title, opts){
  opts = opts || {};
  document.getElementById('hdr-title').textContent = title;
  document.getElementById('hdr-summary').hidden = !opts.summary;
  document.getElementById('hdr-actions').hidden = !opts.actions;
}

// ── 채팅 공용 마크업/바인딩 (전체 채팅방 + 프로젝트 룸) ─────
function chatMarkup(){
  return `<div class="chat">`+
    `<div class="stream" id="stream"><div class="chat-empty">불러오는 중…</div></div>`+
    `<div class="composer">`+
      `<textarea id="msg-input" rows="1" placeholder="" autocomplete="off"></textarea>`+
    `</div>`+
  `</div>`;
}

function bindChat(room, agentRoom){
  const input = document.getElementById('msg-input');
  const grow = ()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,140)+'px'; };
  // Enter=전송, Shift+Enter=줄바꿈(기본 동작 허용)
  input.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendMsg(room, agentRoom); }});
  input.addEventListener('input', grow);
  input.focus({preventScroll:true});   // 포커스가 페이지를 하단으로 끌어내리지 않게
  loadMessages(room, false, agentRoom);
  clearInterval(pollTimer);
  // 담당 에이전트 답은 headless라 뒤늦게 온다 → 폴링으로 잡는다
  pollTimer = setInterval(()=>loadMessages(room, true, agentRoom), 4000);
}

function renderChat(room, title, subtitle){
  setHeader(title, {summary:false, actions:false});
  document.getElementById('view').innerHTML =
    (subtitle?`<div class="note-line" style="padding-bottom:12px">${subtitle}</div>`:'')+
    chatMarkup();
  bindChat(room, false);
}

async function loadMessages(room, silent, agentRoom){
  let msgs;
  try{ msgs = await fetch('/api/messages?room='+encodeURIComponent(room)).then(r=>r.json()); }
  catch(e){ return; }
  const stream = document.getElementById('stream');
  if(!stream) return;                              // 뷰가 바뀌었으면 중단
  const atBottom = stream.scrollHeight - stream.scrollTop - stream.clientHeight < 40;
  let html = msgs.length ? msgs.map(m=>{
    const mine = m.author === 'user';
    const who = mine ? '나' : m.author;
    const ts = (m.created_at||'').slice(5,16);
    return `<div class="msg ${mine?'user':'agent'}">`+
           (mine?'':`<div class="who">${esc(who)}</div>`)+
           `<div class="md">${md(m.body)}</div><div class="ts">${esc(ts)}</div></div>`;
  }).join('') : '<div class="chat-empty">아직 대화가 없습니다. 첫 메시지를 남겨보세요.</div>';
  // 담당 에이전트 방에서 마지막 글이 사용자면 = 답이 오는 중 → 대기 표시
  if(agentRoom && msgs.length && msgs[msgs.length-1].author === 'user'){
    html += `<div class="msg pending">담당 에이전트가 프로젝트를 읽고 답하는 중…</div>`;
  }
  stream.innerHTML = html;
  if(!silent || atBottom) stream.scrollTop = stream.scrollHeight;
}

async function sendMsg(room, agentRoom){
  const input = document.getElementById('msg-input');
  const body = input.value.trim(); if(!body) return;
  input.value = ''; input.style.height = 'auto';   // 전송 후 높이 리셋
  // 채팅창은 항상 사용자('나')가 쓴다. PM·담당 에이전트는 서버가 자동으로 남긴다.
  await fetch('/api/messages',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({room, author: 'user', body})});
  await loadMessages(room, false, agentRoom);
}

// ── 게시판 목록 뷰(제목 행 → 클릭해 글 상세로) ───────────────
function renderBoard(){
  setHeader('게시판', {summary:false, actions:false});
  document.getElementById('view').innerHTML =
    '<div class="note-line" style="padding-bottom:12px">일간보고에서 올라온 프로젝트별 글. 제목을 눌러 들어가면 내용과 댓글을 보고 댓글을 달 수 있습니다.</div>'+
    '<div id="board">불러오는 중…</div>';
  fillBoardList();
  clearInterval(pollTimer);
  pollTimer = setInterval(fillBoardList, 5000);
}

async function fillBoardList(){
  let posts = [];
  try{ posts = await fetch('/api/posts').then(r=>r.json()); }catch(e){ return; }
  const box = document.getElementById('board');
  if(!box) return;
  if(!posts.length){
    box.innerHTML = '<div class="empty">아직 글이 없습니다 — 일간보고가 돌면 프로젝트별 글이 올라옵니다</div>';
    return;
  }
  box.innerHTML = posts.map(p=>{
    const n = (p.comments||[]).length;
    const day = (p.day || p.created_at || '').slice(0,10);
    return `<div class="prow" onclick="go('#/post/${p.id}')">`+
      `<span class="prow-t">${esc(p.title)}</span>`+
      `<span class="prow-meta">${esc(p.author)} · ${esc(day)} · 댓글 <span class="c">${n}</span></span></div>`;
  }).join('');
}

// ── 글 상세 뷰(내용 + 댓글 + 댓글 작성) ────────────────────────
function renderPost(id){
  setHeader('게시판', {summary:false, actions:false});
  document.getElementById('view').innerHTML = '<div id="post">불러오는 중…</div>';
  clearInterval(pollTimer);   // 상세에선 폴링 안 함(댓글 입력 중 날아가지 않게)
  fillPost(id);
}

async function fillPost(id){
  let p = {};
  try{ p = await fetch('/api/posts/'+encodeURIComponent(id)).then(r=>r.json()); }catch(e){}
  const box = document.getElementById('post');
  if(!box) return;
  if(!p || !p.id){ box.innerHTML = '<div class="back" onclick="go(\'#/board\')">← 게시판</div><div class="empty">글을 찾을 수 없습니다</div>'; return; }
  const day = (p.day || p.created_at || '').slice(0,10);
  const cs = (p.comments||[]).map(c=>{
    const mine = c.author === 'user';
    return `<div class="cmt${mine?' user':''}"><span class="cmt-who">${mine?'나':esc(c.author)}</span>`+
      `<div class="md">${md(c.body)}</div></div>`;
  }).join('') || '<div class="cmt none">아직 댓글 없음 — 첫 댓글을 남겨보세요</div>';
  box.innerHTML =
    `<div class="back" onclick="go('#/board')">← 게시판</div>`+
    `<div class="post"><div class="post-h"><span class="post-title">${esc(p.title)}</span>`+
      `<span class="post-day">${esc(p.author)} · ${esc(day)}</span></div>`+
      `<div class="post-body md">${md(p.body)}</div>`+
      `<div class="cmts">${cs}</div>`+
      `<div class="cmt-form"><textarea id="cmt-input" rows="1" placeholder="댓글 달기…"></textarea>`+
      `<button onclick="postComment('${id}')">댓글</button></div>`+
    `</div>`;
  const ta = document.getElementById('cmt-input');
  ta.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); postComment(id); }});
}

async function postComment(id){
  const ta = document.getElementById('cmt-input');
  const body = ta.value.trim(); if(!body) return;
  ta.value = '';
  await fetch('/api/posts/'+encodeURIComponent(id)+'/comments',{method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({author:'user', body})});
  fillPost(id);
}

// ── 프로젝트 룸 뷰(왼쪽 달력+칸반 / 오른쪽 담당 에이전트 채팅) ──
const KCOLS = [['open','할일'],['consulting','진행중'],['resolved','완료']];
const KORDER = ['open','consulting','resolved'];   // 열 순서(‹ › 이동)

function renderRoom(path){
  CUR_ROOM = path;
  const t = new Date(todayStr()); CAL_YM = {y:t.getFullYear(), m:t.getMonth()};  // 달력은 이번 달부터
  const p = PROJECTS.find(x=>x.path===path);
  const name = p ? p.name : path;
  setHeader(name, {summary:false, actions:false});
  document.getElementById('view').innerHTML =
    `<div class="room-layout">`+
      `<div class="room-main" id="room-main"></div>`+
      `<div class="room-side">`+
        `<div class="side-h">${esc(name)} 담당 에이전트</div>`+
        chatMarkup()+
      `</div>`+
    `</div>`;
  fillRoomMain(path);
  bindChat(path, true);   // 프로젝트 룸 = 담당 에이전트 방
}

// 왼쪽(달력+칸반)만 다시 그린다 — 상태 이동·달력 넘김에서 채팅은 안 건드리게 분리
function fillRoomMain(path){
  const main = document.getElementById('room-main');
  if(!main) return;
  const items = issuesByProject()[path] || [];
  const u = items.filter(i=>i.kind==='unresolved').length;
  const d = items.filter(i=>i.kind==='deadline').length;
  const sub = `${esc(path)}` + (items.length?` · 미해결 ${u} · 기한 ${d} · 이슈 ${items.length}건`:' · 이슈 없음');
  main.innerHTML = `<div class="note-line" style="padding:0 0 10px">${sub}</div>`+
                   calMarkup(items) + kanbanMarkup(items);
}

function calMarkup(items){
  const y = CAL_YM.y, m = CAL_YM.m;
  const startDow = new Date(y, m, 1).getDay();
  const daysIn = new Date(y, m+1, 0).getDate();
  const byDay = {};
  items.forEach(i=>{
    if(!i.due) return;
    const dt = new Date(i.due);
    if(dt.getFullYear()===y && dt.getMonth()===m) (byDay[dt.getDate()]=byDay[dt.getDate()]||[]).push(i);
  });
  const td = new Date(todayStr());
  const isToday = d => td.getFullYear()===y && td.getMonth()===m && td.getDate()===d;
  let cells = ['일','월','화','수','목','금','토'].map(w=>`<div class="dow">${w}</div>`).join('');
  for(let k=0;k<startDow;k++) cells += `<div class="cal-cell out"></div>`;
  for(let day=1;day<=daysIn;day++){
    const evs = (byDay[day]||[]).map(i=>
      `<div class="ev" title="${escAttr(clean(i.title))}">${esc(clean(i.title))}</div>`).join('');
    cells += `<div class="cal-cell${isToday(day)?' today':''}"><div class="dd">${day}</div>${evs}</div>`;
  }
  return `<div class="cal"><div class="cal-h">`+
    `<button onclick="calNav(-1)">‹</button><span>${y}년 ${m+1}월</span><button onclick="calNav(1)">›</button>`+
    `</div><div class="cal-grid">${cells}</div></div>`;
}

function kanbanMarkup(items){
  const cols = KCOLS.map(([st,label])=>{
    const list = items.filter(i=>(i.status||'open')===st);
    const cards = list.map(i=>{
      const idx = KORDER.indexOf(st);
      const prev = idx>0 ? `<button onclick="moveIssue(${i.id},'${KORDER[idx-1]}')" title="${KCOLS[idx-1][1]}로">‹</button>` : '';
      const next = idx<KORDER.length-1 ? `<button onclick="moveIssue(${i.id},'${KORDER[idx+1]}')" title="${KCOLS[idx+1][1]}로">›</button>` : '';
      return `<div class="kcard">`+
        (i.due?`<span class="due">${i.due}</span> `:'')+esc(clean(i.title))+
        (i.verdict?` <span class="badge ${i.verdict==='drop'?'d':'u'}">${i.verdict}</span>`:'')+
        `<div class="mv">${prev}${next}</div></div>`;
    }).join('') || `<div class="col-empty">없음</div>`;
    return `<div class="kcol"><h3>${label}<span class="n">${list.length}</span></h3>${cards}</div>`;
  }).join('');
  return `<div class="kanban">${cols}</div>`;
}

function calNav(delta){
  let m = CAL_YM.m + delta, y = CAL_YM.y;
  if(m<0){ m=11; y--; } if(m>11){ m=0; y++; }
  CAL_YM = {y, m};
  fillRoomMain(CUR_ROOM);
}

async function moveIssue(id, status){
  await fetch('/api/issues/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({status})});
  const it = ISSUES.find(i=>i.id===id); if(it) it.status = status;   // 로컬 캐시 갱신
  fillRoomMain(CUR_ROOM);
  renderSidebar();
}

// ── 라우터 ─────────────────────────────────────────────
function go(hash){ if(location.hash===hash) route(); else location.hash = hash; }

function route(){
  clearInterval(pollTimer);
  const h = decodeURIComponent(location.hash) || '#/dashboard';
  renderSidebar();
  if(h.startsWith('#/post/')){
    renderPost(h.slice('#/post/'.length));
  } else if(h.startsWith('#/board')){
    renderBoard();
  } else if(h.startsWith('#/chat/')){
    const room = h.slice('#/chat/'.length);
    if(room === 'daily') renderChat('daily', '일간보고', '매일 새벽 PM과 각 담당 에이전트의 일간보고 대화 기록');
    else renderChat('global', '전체 채팅방', '에이전트와 사용자가 함께 쓰는 방');
  } else if(h.startsWith('#/room/')){
    renderRoom(h.slice('#/room/'.length));
  } else {
    renderDashboard();
  }
}
window.addEventListener('hashchange', route);
// 프로젝트 룸 진입 — data-room 을 가진 요소(사이드바 룸·카드 '룸 열기') 위임 처리
document.addEventListener('click', e=>{
  const el = e.target.closest('[data-room]');
  if(el) go('#/room/'+encodeURIComponent(el.getAttribute('data-room')));
});

// ── 상단 액션 버튼 ──────────────────────────────────────
async function doScan(){
  document.getElementById('s-iss').textContent = '…';
  await fetch('/api/scan',{method:'POST'});
  await loadData(); route();
}
async function doJudge(){
  const b = document.getElementById('btn-judge'); const old = b.textContent;
  b.disabled = true; b.textContent = '판정 중…';
  try{ await fetch('/api/judge',{method:'POST'}); await loadData(); route(); }
  finally{ b.disabled = false; b.textContent = old; }
}

// 시작
(async ()=>{ await loadData(); if(!location.hash) location.hash='#/dashboard'; route(); })();
</script></body></html>"""


@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return _HTML
