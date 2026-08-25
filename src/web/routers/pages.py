"""대시보드 화면 (HTML). 최소 카드 대시보드 — 프로젝트별 미해결·기한.

screen-plan으로 정교화하기 전의 MVP 화면. JS가 /api/projects·/api/issues 를 로드해 렌더.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ohmyPM</title>
<style>
  body{font-family:-apple-system,'Segoe UI',sans-serif;max-width:1400px;margin:20px auto;padding:0 16px;background:#f6f7f9;color:#222}
  h1{display:flex;align-items:center;gap:12px;font-size:20px}
  button{padding:7px 13px;border:none;background:#1a8a5a;color:#fff;border-radius:6px;cursor:pointer;font-size:13px}
  .count{color:#888;font-size:12px;font-weight:normal}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;margin-top:14px}
  .card{background:#fff;border:1px solid #e2e2e6;border-radius:10px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
  .card h2{margin:0 0 8px;font-size:14.5px;display:flex;justify-content:space-between}
  .issue{font-size:12.5px;padding:4px 0;border-top:1px solid #f2f2f4;line-height:1.4}
  .due{color:#c0392b;font-weight:bold}
  .kind{display:inline-block;font-size:10px;padding:1px 5px;border-radius:3px;margin-right:5px;background:#eef;color:#446}
  .kind.deadline{background:#fdeaea;color:#c0392b}
</style></head><body>
<h1>🗂 ohmyPM <button onclick="doScan()">↻ 스캔</button> <span id="stat" class="count"></span></h1>
<div class="grid" id="grid">로딩…</div>
<script>
const esc = s => (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function load(){
  const [ps, is] = await Promise.all([
    fetch('/api/projects').then(r=>r.json()),
    fetch('/api/issues').then(r=>r.json()),
  ]);
  const byProj = {};
  for(const i of is){ (byProj[i.project] = byProj[i.project] || []).push(i); }
  document.getElementById('stat').textContent = `프로젝트 ${ps.length} · 이슈 ${is.length}`;
  const g = document.getElementById('grid'); g.innerHTML = '';
  for(const p of ps){
    const items = byProj[p.path] || [];
    const card = document.createElement('div'); card.className = 'card';
    card.innerHTML = `<h2>${esc(p.name)} <span class="count">${items.length}건</span></h2>` +
      items.slice(0,12).map(i =>
        `<div class="issue"><span class="kind ${i.kind}">${i.kind}</span>` +
        `${i.due ? `<span class="due">${i.due}</span> ` : ''}${esc(i.title)}</div>`
      ).join('') +
      (items.length > 12 ? `<div class="count">…외 ${items.length-12}건</div>` : (items.length ? '' : '<div class="count">이슈 없음</div>'));
    g.appendChild(card);
  }
}
async function doScan(){
  document.getElementById('stat').textContent = '스캔 중…';
  await fetch('/api/scan', {method:'POST'});
  await load();
}
load();
</script></body></html>"""


@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return _HTML
