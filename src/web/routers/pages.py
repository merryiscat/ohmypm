"""대시보드 화면 (HTML). 정보 위계: 요약 바 → 임박 기한 → 프로젝트 카드.

JS가 /api/projects·/api/issues 를 로드해 렌더. 취소선(~~) 항목은 화면에서 제외(노이즈 컷).
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ohmyPM</title>
<style>
  :root{--bg:#f5f6f8;--card:#fff;--line:#e4e6ea;--muted:#8b8f96;--ink:#20242b;--red:#d64545;--amber:#c77b1e;--green:#1a8a5a}
  *{box-sizing:border-box}
  body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:var(--bg);color:var(--ink);font-size:14px}
  header{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);padding:12px 22px;display:flex;align-items:center;gap:18px;z-index:10}
  header h1{font-size:18px;margin:0}
  .summary{display:flex;gap:16px;color:var(--muted);font-size:13px}
  .summary b{color:var(--ink);font-size:15px}
  .summary .hot b{color:var(--red)}
  .actions{margin-left:auto;display:flex;gap:8px}
  button{padding:7px 14px;border:none;background:var(--green);color:#fff;border-radius:6px;cursor:pointer;font-size:13px}
  button.ghost{background:#fff;color:var(--ink);border:1px solid var(--line)}
  main{padding:20px 22px;max-width:1500px;margin:0 auto}
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
  .badge{font-size:11px;padding:1px 7px;border-radius:20px;font-weight:700}
  .badge.u{background:#eef1fb;color:#3a52a8} .badge.d{background:#fdeceb;color:var(--red)}
  .issue{font-size:12.5px;padding:4px 0;border-top:1px solid #f2f3f5;line-height:1.45;color:#3a3f47}
  .issue .due{color:var(--red);font-weight:700}
  .more{color:var(--muted);font-size:12px;padding-top:4px}
  .note-line{color:var(--muted);font-size:12px;padding:8px 2px 0}
  .empty{color:var(--muted);text-align:center;padding:40px}
</style></head><body>
<header>
  <h1>🗂 ohmyPM</h1>
  <div class="summary">
    <span>프로젝트 <b id="s-proj">–</b></span>
    <span>이슈 <b id="s-iss">–</b></span>
    <span class="hot">임박 <b id="s-soon">–</b></span>
  </div>
  <div class="actions">
    <button class="ghost" onclick="doJudge()" id="btn-judge">✓ 판정</button>
    <button onclick="doScan()">↻ 스캔</button>
  </div>
</header>
<main>
  <section id="soon-sec" hidden>
    <h2>⏰ 임박 기한 (7일 내)</h2>
    <div class="soon" id="soon"></div>
    <div class="note-line" id="soon-note"></div>
  </section>
  <section>
    <h2>프로젝트</h2>
    <div class="grid" id="grid">로딩…</div>
  </section>
</main>
<script>
const esc = s => (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const clean = s => (s||'').replace(/~~/g,'').trim();          // 취소선 마크 제거
const isCancelled = s => /~~.+~~/.test(s||'');                 // ~~...~~ = 취소 → 제외
const todayStr = () => new Date().toISOString().slice(0,10);

function daysTo(due){
  const d = (new Date(due) - new Date(todayStr())) / 86400000;
  return Math.round(d);
}

async function load(){
  const [ps, allIs] = await Promise.all([
    fetch('/api/projects').then(r=>r.json()),
    fetch('/api/issues').then(r=>r.json()),
  ]);
  // 노이즈 컷: 취소선 항목 + 판정 에이전트가 drop한 오탐 제외
  const is = allIs.filter(i => !isCancelled(i.title) && i.verdict !== 'drop');
  const nameOf = {}; ps.forEach(p => nameOf[p.path] = p.name);

  // 임박 기한 = 판정된 deadline만(keep·reclass). 미판정·조건부는 여기 안 넣고 아래 카운터로.
  const judged = i => i.verdict === 'keep' || i.verdict === 'reclass';
  const soon = is.filter(i => i.kind==='deadline' && judged(i) && i.due && daysTo(i.due) <= 7)
                 .sort((a,b)=> a.due.localeCompare(b.due));
  // 아직 안 가린 기한 후보 / 조건부 보류(기한 아님) — 소리 없이 사라지지 않게 카운트
  const pendingJudge = is.filter(i => i.kind==='deadline' && !i.verdict).length;
  const conditional = is.filter(i => i.kind==='conditional').length;
  document.getElementById('s-proj').textContent = ps.length;
  document.getElementById('s-iss').textContent = is.length;
  document.getElementById('s-soon').textContent = soon.length;

  const sec = document.getElementById('soon-sec'), box = document.getElementById('soon');
  const note = document.getElementById('soon-note');
  const noteParts = [];
  if(pendingJudge) noteParts.push(`미판정 기한 후보 ${pendingJudge}건 — '판정'을 눌러 가려내세요`);
  if(conditional) noteParts.push(`조건부 보류 ${conditional}건(기한 아님)`);
  note.textContent = noteParts.join(' · ');
  // 임박 기한이 하나도 없어도, 미판정/조건부가 있으면 섹션을 보여 카운터를 노출
  if(soon.length || pendingJudge || conditional){
    sec.hidden = false;
    box.innerHTML = soon.map(i=>{
      const dd = daysTo(i.due);
      const cls = dd<=0?'today':'week';
      const label = dd<0?`${-dd}일 지남`:(dd===0?'오늘':`${dd}일 후`);
      return `<div class="row"><span class="d ${cls}">${i.due} · ${label}</span>`+
             `<span class="proj">${esc(nameOf[i.project]||'')}</span>`+
             `<span>${esc(clean(i.title))}</span></div>`;
    }).join('') || '<div class="row"><span class="proj">확정된 임박 기한 없음</span></div>';
  } else sec.hidden = true;

  // 프로젝트 그리드: 이슈 많은 순
  const byProj = {}; is.forEach(i => (byProj[i.project]=byProj[i.project]||[]).push(i));
  const ordered = ps.slice().sort((a,b)=> (byProj[b.path]||[]).length - (byProj[a.path]||[]).length);
  const g = document.getElementById('grid'); g.innerHTML = '';
  for(const p of ordered){
    const items = byProj[p.path] || [];
    const u = items.filter(i=>i.kind==='unresolved').length;
    const d = items.filter(i=>i.kind==='deadline').length;
    const card = document.createElement('div'); card.className='card';
    card.innerHTML = `<h3>${esc(p.name)}`+
      (u?`<span class="badge u">미해결 ${u}</span>`:'')+
      (d?`<span class="badge d">기한 ${d}</span>`:'')+`</h3>`+
      items.slice(0,8).map(i=>
        `<div class="issue">${i.due?`<span class="due">${i.due}</span> `:''}${esc(clean(i.title))}</div>`
      ).join('') +
      (items.length>8?`<div class="more">…외 ${items.length-8}건</div>`:(items.length?'':'<div class="more">이슈 없음</div>'));
    g.appendChild(card);
  }
  if(!ordered.length) g.innerHTML = '<div class="empty">관리 대상 없음 — 스캔을 눌러보세요</div>';
}
async function doScan(){
  document.getElementById('s-iss').textContent = '…';
  await fetch('/api/scan',{method:'POST'});
  await load();
}
async function doJudge(){
  const b = document.getElementById('btn-judge');
  const old = b.textContent; b.disabled = true; b.textContent = '판정 중…';
  try{ await fetch('/api/judge',{method:'POST'}); await load(); }
  finally{ b.disabled = false; b.textContent = old; }
}
load();
</script></body></html>"""


@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return _HTML
