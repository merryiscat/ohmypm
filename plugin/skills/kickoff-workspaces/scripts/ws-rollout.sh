#!/bin/sh
# kickoff-workspaces 전체 배포 — 발동어 "구조 전체 배포하자" (T-003).
# 사용: ws-rollout.sh [--targets <허용목록 파일>] [--report <결과 파일>] [--api <URL>] [--dry-run] [--force] [--migrate-v1]
#   --force: dirty 저장소도 배포 파일만 커밋한다. 배포 파일 자체에 사용자 변경이 있으면 건너뛴다.
#   ohmyPM 저장소(cwd가 속한 git 저장소)의 로컬 전용 docs/rollout-targets.md를 읽어
#   대상을 탐색(대시보드 API 또는 PROJECTS_ROOT 직하위 폴더) → 허용 목록과 교집합 → 사전 검사(git 루트·dirty·설치 버전·훅 경로)
#   → ws_upgrade.py로 설치/갱신 → 배포 파일만 stage → 한국어 커밋(푸시 없음)
#   → docs/rollouts/rollout-<일시>.md 결과 저장. 한 대상의 실패는 기록하고 다음으로 간다. 실패가 하나라도 있으면 종료 코드 1.
# 재실행 안전: 설치 버전이 플러그인 버전과 같으면 파일·Git 설정·커밋을 건드리지 않는다.
# 허용 목록 파일 형식(줄 단위, `#`·`>` 줄은 주석):
#   루트: <프로젝트 상위 폴더>            이름만 적힌 줄은 <루트>/<이름>으로 푼다 (끝의 "\<이름>" 자리표시자는 있어도 된다)
#   탐색: api [<URL>] | folder [<폴더>]   생략 시 api(http://127.0.0.1:8123/api/projects). folder 폴더 생략 시 PROJECTS_ROOT 환경변수 → 루트 순
#   제외: <이름 또는 경로> — <사유>        허용 목록에서 빼고 사유를 결과에 남긴다
#   기준: <자유 문장>                     참고 문장(결과에 그대로 옮겨 적는다)
#   그 밖의 줄 = 허용 대상(이름 또는 절대 경로)
# 로컬 전용 설정(입력 파일·docs/rollouts/가 .gitignore·.worktreeinclude에 있고 Git 미추적·index.md 미등재)이 아니면 배포 전에 실패한다.
set -u
K="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"    # skills/kickoff-workspaces (Windows 경로 우선)
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ws-rollout: cwd가 git 저장소(ohmyPM)가 아니다" >&2; exit 2; }
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
exec python - "$K" "$REPO" "$0" "$@" <<'EOF'
import io, json, os, re, subprocess, sys, time, urllib.request

K, REPO, SELF = sys.argv[1], sys.argv[2], sys.argv[3]
ARGV = sys.argv[4:]
PLUGIN_ROOT = os.path.normpath(os.path.join(K, '..', '..'))
UPGRADE = os.path.join(K, 'scripts', 'ws_upgrade.py')
DEFAULT_API = 'http://127.0.0.1:8123/api/projects'
MANAGED = ['docs/protocol.md', 'docs/tasks/_template.md', 'docs/reviews/_template.md', '.githooks/pre-commit', 'AGENTS.md', 'CLAUDE.md',
           '.ohmypm/bin/workflow.py', '.ohmypm/bin/workflow_core.py', 'docs/workflow-guide.md', '.gitignore']
OWNED = ['docs/roles.md', 'docs/workflow.json', 'orca.yaml', '.worktreeinclude']
DEPLOY_FILES = MANAGED + OWNED
DRY = '--dry-run' in ARGV          # 탐색·사전 검사까지만, 파일·Git은 건드리지 않는다
FORCE = '--force' in ARGV          # dirty 무시(배포 파일만 stage)
MIGRATE = '--migrate-v1' in ARGV
STARTED = time.strftime('%Y-%m-%d %H:%M:%S')
STAMP = time.strftime('%Y%m%d-%H%M%S')

def arg(name, default=None):
    if name in ARGV:
        i = ARGV.index(name)
        if i + 1 >= len(ARGV): die(2, '%s 뒤에 값이 없다' % name)
        return ARGV[i + 1]
    return default

def die(code, msg):
    print('ws-rollout: 실패 — ' + msg, file=sys.stderr)
    sys.exit(code)

def sh(cmd, cwd=None, check=False):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        raise RuntimeError('%s → rc=%s\n%s' % (' '.join(cmd), r.returncode, (r.stderr or r.stdout).strip()))
    return r

def git(path, *a):
    return sh(['git', '-C', path] + list(a))

def norm(p):
    return os.path.normcase(os.path.normpath(os.path.realpath(p)))

def repo_root(p):
    """git 저장소면 최상위 경로(정규화), 아니면 None."""
    r = git(p, 'rev-parse', '--show-toplevel')
    return norm(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None

def read(p):
    with io.open(p, encoding='utf-8-sig') as f: return f.read()

# ---------- 0. 플러그인 버전 ----------
try:
    V = json.loads(read(os.path.join(PLUGIN_ROOT, '.claude-plugin', 'plugin.json')))['version']
except Exception as e:
    die(2, '플러그인 버전을 읽지 못했다: %s' % e)

# ---------- 1. 로컬 전용 설정 검사 (배포 전 실패) ----------
TARGETS = arg('--targets', os.path.join(REPO, 'docs', 'rollout-targets.md'))
REPORT_DIR = os.path.join(REPO, 'docs', 'rollouts')
REPORT = arg('--report', os.path.join(REPORT_DIR, 'rollout-%s.md' % STAMP))
problems = []
for rel in ['docs/rollout-targets.md', 'docs/rollouts/_probe.md']:
    if git(REPO, 'check-ignore', '-q', rel).returncode != 0:
        problems.append('%s 가 .gitignore에 없다' % rel.replace('_probe.md', ''))
tracked = git(REPO, 'ls-files', '--', 'docs/rollout-targets.md', 'docs/rollouts').stdout.strip()
if tracked: problems.append('Git 추적 중: ' + tracked.replace('\n', ', '))
wti = os.path.join(REPO, '.worktreeinclude')
wt_lines = [l.strip() for l in read(wti).splitlines()] if os.path.exists(wti) else []
for need in ['docs/rollout-targets.md', 'docs/rollouts/']:
    if need not in wt_lines: problems.append('.worktreeinclude에 %s 가 없다' % need)
idx = os.path.join(REPO, 'docs', 'index.md')
if os.path.exists(idx) and re.search(r'rollout-targets\.md|rollouts/', read(idx)):
    problems.append('docs/index.md에 로컬 전용 경로가 등재돼 있다')
if problems:
    die(2, '로컬 전용 설정 누락 — ' + ' / '.join(problems) + ' (결과 파일도 쓰지 않는다)')
if not os.path.isfile(TARGETS):
    die(2, '입력 부재 — %s 가 없다 (main이 로컬 전용으로 작성한다)' % TARGETS)

# ---------- 2. 허용 목록 파싱 ----------
meta = {'루트': None, '탐색': None, '기준': [], '제외': []}
allowed = []          # (원문, 정규화 경로)
fmt_errors = []
KEY = re.compile(r'^([^\s:：]+)\s*[:：]\s*(.*)$')
def is_path(s): return bool(re.match(r'^([A-Za-z]:[\\/]|/|~|\\\\)', s))
for ln, raw in enumerate(read(TARGETS).splitlines(), 1):
    s = raw.strip()
    if not s or s.startswith('#') or s.startswith('>'): continue
    m = None if is_path(s) else KEY.match(s)
    if m:
        k, v = m.group(1), m.group(2).strip()
        if k == '루트':
            if meta['루트']: fmt_errors.append('%d행: 루트가 두 번' % ln)
            meta['루트'] = os.path.expanduser(re.sub(r'[\\/]<[^<>]*>\s*$', '', v))   # "…\project\<이름>" 꼴의 자리표시자는 뗀다
        elif k == '탐색':
            if meta['탐색']: fmt_errors.append('%d행: 탐색이 두 번' % ln)
            meta['탐색'] = v
        elif k == '제외':
            parts = re.split(r'\s+[—–-]+\s+', v, 1)
            meta['제외'].append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else '(사유 없음)'))
        elif k == '기준':
            meta['기준'].append(v)
        else:
            fmt_errors.append('%d행: 모르는 항목 "%s:"' % (ln, k))
        continue
    allowed.append((s, ln))

def resolve(tok):
    if is_path(tok): return os.path.expanduser(tok)
    if not meta['루트']: raise ValueError('이름 "%s"을 풀 루트: 줄이 없다' % tok)
    return os.path.join(meta['루트'], tok)

allow = []            # dict(원문, 경로, key)
seen = set()
for tok, ln in allowed:
    try: p = resolve(tok)
    except ValueError as e: fmt_errors.append('%d행: %s' % (ln, e)); continue
    key = norm(p)
    if key in seen: fmt_errors.append('%d행: 허용 목록 중복 "%s"' % (ln, tok)); continue
    seen.add(key); allow.append({'raw': tok, 'path': os.path.normpath(p), 'key': key})
excluded = []
for tok, why in meta['제외']:
    try: key = norm(resolve(tok))
    except ValueError as e: fmt_errors.append('제외 "%s": %s' % (tok, e)); continue
    hit = [a for a in allow if a['key'] == key]
    for a in hit: allow.remove(a)
    excluded.append((tok, why, '허용 목록에서 제거' if hit else '허용 목록에 없음(기록만)'))
if meta['루트'] and not os.path.isdir(meta['루트']): fmt_errors.append('루트 폴더가 없다: %s' % meta['루트'])
if not allow and not fmt_errors: fmt_errors.append('허용 대상이 한 줄도 없다')
mode_line = (meta['탐색'] or 'api').split(None, 1)
mode = mode_line[0].lower(); mode_arg = mode_line[1].strip() if len(mode_line) > 1 else ''
if mode not in ('api', 'folder'): fmt_errors.append('탐색 값이 api/folder가 아니다: "%s"' % meta['탐색'])
API_URL = arg('--api', mode_arg if (mode == 'api' and mode_arg) else DEFAULT_API)
FOLDER_ROOT = mode_arg or os.environ.get('PROJECTS_ROOT') or meta['루트'] or ''
if mode == 'folder' and not os.path.isdir(FOLDER_ROOT): fmt_errors.append('folder 탐색 폴더가 없다: "%s" (탐색 folder <폴더> 또는 PROJECTS_ROOT)' % FOLDER_ROOT)

rows = []             # 결과 표
notes = []            # 탐색·중복·미발견 등 기록
failures = 0
def note(s): notes.append(s); print(s)

def write_report(status_line):
    os.makedirs(REPORT_DIR, exist_ok=True)
    L = ['# 작업 구조 배포 결과 (로컬 전용 — git 미추적)', '',
         '- 실행 일시: %s (종료 %s)' % (STARTED, time.strftime('%Y-%m-%d %H:%M:%S')),
         '- 명령: `%s %s`' % (SELF, ' '.join(ARGV)), '- 플러그인 버전: %s (%s)' % (V, PLUGIN_ROOT),
         '- 입력: `%s`' % TARGETS, '- 탐색 출처: %s' % (('API ' + API_URL) if mode == 'api' else ('folder ' + FOLDER_ROOT)),
         '- 결과: %s%s' % (status_line, ' (dry-run — 파일·Git 무변경)' if DRY else ''), '']
    if meta['기준']: L += ['## 입력 기준(원문)'] + ['- ' + b for b in meta['기준']] + ['']
    L += ['## 제외(입력 `제외:` 줄)'] + (['- %s — %s (%s)' % e for e in excluded] or ['- 없음']) + ['']
    L += ['## 탐색·교집합 기록'] + ['- ' + n for n in notes] + ['']
    L += ['## 대상별 결과', '', '| 프로젝트 | 경로 | 결과 | 사유 | 버전 | 공유폴더 | setup | 커밋 SHA | 변경 잔존 |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append('| %s |' % ' | '.join(str(r.get(k, '')).replace('|', '\\|').replace('\n', ' ') for k in
                 ['name', 'path', 'result', 'reason', 'version', 'shared', 'setup', 'sha', 'residual']))
    det = [r for r in rows if r.get('log')]
    if det:
        L += ['', '## 설치기·커밋 출력']
        for r in det: L += ['', '### %s' % r['name'], '```', r['log'].rstrip(), '```']
    with io.open(REPORT, 'w', encoding='utf-8', newline='\n') as f: f.write('\n'.join(L) + '\n')
    print('결과 저장: %s' % REPORT)

if fmt_errors:
    for e in fmt_errors: note('형식 오류: ' + e)
    write_report('실패 — 입력 형식 오류 %d건(배포 전 중단)' % len(fmt_errors))
    sys.exit(2)

# ---------- 3. 탐색 ----------
discovered = []       # dict(raw, key, name)
try:
    if mode == 'api':
        with urllib.request.urlopen(API_URL, timeout=10) as resp:
            if resp.status != 200: raise RuntimeError('HTTP %s' % resp.status)
            data = json.loads(resp.read().decode('utf-8'))
        if not isinstance(data, list): raise RuntimeError('응답이 목록이 아니다')
        raw_items = [(d.get('path'), d.get('name'), d.get('has_wiki')) for d in data if isinstance(d, dict)]
        kept = [(p, n) for p, n, w in raw_items if p and str(w) == '1']
        dropped = [(n or p) for p, n, w in raw_items if not (p and str(w) == '1')]
        note('API %s → %d건, 클라이언트 has_wiki=1 필터 통과 %d건, 제외 %d건: %s' % (API_URL, len(raw_items), len(kept), len(dropped), ', '.join(map(str, dropped)) or '없음'))
        cand = kept
    else:
        subs = sorted(d for d in os.listdir(FOLDER_ROOT) if not d.startswith('.') and os.path.isdir(os.path.join(FOLDER_ROOT, d)))
        note('folder %s 직하위 폴더 %d건' % (FOLDER_ROOT, len(subs)))
        cand = [(os.path.join(FOLDER_ROOT, d), d) for d in subs]
except Exception as e:
    note('탐색 실패(범위를 넓히지 않고 중단): %s' % e)
    write_report('실패 — 탐색 실패')
    sys.exit(1)

dups = []
for p, n in cand:
    key = repo_root(p) if os.path.isdir(p) else None
    key = key or (norm(p) if os.path.exists(p) else os.path.normcase(os.path.normpath(p)))
    hit = next((d for d in discovered if d['key'] == key), None)
    if hit: dups.append('%s ≡ %s' % (p, hit['raw'])); continue
    discovered.append({'raw': p, 'key': key, 'name': n or os.path.basename(key)})
note('정규화(실경로·git 루트)로 중복 제거: %d → %d건%s' % (len(cand), len(discovered), (' — ' + '; '.join(dups)) if dups else ''))
disc_keys = {d['key']: d for d in discovered}
targets = []
for a in allow:
    key = a['key']
    d = disc_keys.get(key)
    if d is None and os.path.isdir(a['path']):
        rr = repo_root(a['path'])
        if rr and rr != key:            # 허용 목록이 하위 폴더를 가리킴 → 저장소 루트로 정규화
            d = disc_keys.get(rr); key = rr
    if d: targets.append((a, d, key)); continue
    if not os.path.exists(a['path']): why = '경로 없음'
    elif mode == 'api' and any(norm(p) == key for p, n, w in raw_items if p and os.path.exists(p)): why = 'API에 있으나 has_wiki=0'
    else: why = '탐색 결과에 없음(%s)' % ('API' if mode == 'api' else 'folder')
    rows.append({'name': a['raw'], 'path': a['path'], 'result': '미발견', 'reason': why})
    note('허용 목록 미발견: %s — %s' % (a['raw'], why))
outside = [d['name'] for d in discovered if d['key'] not in {k for _, _, k in targets}]
note('허용 목록 %d건 중 탐색과 교집합 %d건, 미발견 %d건; 탐색됐으나 허용 목록 밖 %d건(미처리): %s' % (len(allow), len(targets), len(allow) - len(targets), len(outside), ', '.join(outside) or '없음'))

# ---------- 5. 대상별 처리 ----------
def installed_version(p):
    f = os.path.join(p, 'docs', 'protocol.md')
    if not os.path.exists(f): return None
    m = re.search(r'kickoff-workspaces v([0-9.]+)', read(f).splitlines()[0] if read(f) else '')
    return m.group(1) if m else None

for a, d, key in targets:
    p = a['path'] if os.path.isdir(a['path']) else d['raw']
    row = {'name': d['name'] if is_path(a['raw']) else a['raw'], 'path': p, 'result': '', 'reason': '', 'version': '', 'shared': '', 'setup': '', 'sha': '', 'residual': '', 'log': ''}
    rows.append(row)
    try:
        if not os.path.isdir(p): row.update(result='건너뜀', reason='경로 없음'); continue
        rr = repo_root(p)
        if rr is None: row.update(result='건너뜀', reason='Git 저장소 아님'); continue
        if rr != norm(p): row.update(result='건너뜀', reason='Git 저장소 루트가 아님(루트: %s)' % rr); continue
        cur = installed_version(p)
        st = git(p, 'status', '--porcelain', '--untracked-files=all').stdout.splitlines()
        hp = git(p, 'config', '--get', 'core.hooksPath').stdout.strip()
        hp_bad = bool(hp) and re.sub(r'^\./', '', hp.replace('\\', '/')).rstrip('/') != '.githooks'
        row['version'] = ('v%s' % cur if cur else '미설치') + ' → v%s' % V
        extra = []
        if st: extra.append('dirty %d건' % len(st))
        if hp_bad: extra.append('hooksPath=%s' % hp)
        if cur == V:
            resid = [s for s in st if s[3:].strip().strip('"') in DEPLOY_FILES]
            if resid: extra.append('배포 파일 미커밋 잔존 %d건(이전 실패분 — 손으로 커밋/정리)' % len(resid))
            row.update(result='건너뜀', reason='같은 버전 v%s — 파일·Git 설정·커밋 무변경' % V + ((' (참고: ' + ', '.join(extra) + ')') if extra else ''), version='v%s' % V); continue
        pre_dirty_deploy = [s[3:].strip().strip('"') for s in st if s[3:].strip().strip('"') in DEPLOY_FILES]
        if st and not FORCE:
            row.update(result='건너뜀', reason='dirty(staged/unstaged/untracked %d건: %s%s)' % (len(st), '; '.join(s.strip() for s in st[:3]), ' …' if len(st) > 3 else '')); continue
        if st and pre_dirty_deploy:
            row.update(result='건너뜀', reason='강제 모드지만 배포 파일 자체에 사용자 변경이 있어 섞일 수 있음: %s' % ', '.join(pre_dirty_deploy)); continue
        if hp_bad:
            row.update(result='건너뜀', reason='core.hooksPath=%s (.githooks 아님 — 기존 훅 보존)' % hp); continue
        if os.path.exists(os.path.join(p, 'docs/protocol.md')) and not MIGRATE:
            row.update(result='건너뜀', reason='1.0 전환은 --migrate-v1 명시 필요; 진행 중 작업 보존'); continue
        cmd = [sys.executable, UPGRADE, p] + (['--migrate-v1'] if MIGRATE else [])
        row.update(shared='기존 설정 보존 / 신규는 공유 없음', setup='작업별 승인 manifest',
                   reason='1.0 설치/이전 — 기존 작업·모델 설정 보존, 역할표는 백업 후 갱신')
        if DRY:
            row.update(result='예정(dry-run)', reason=row['reason'] + ' — 쓰지 않음'); continue
        r = sh(cmd, cwd=p)
        row['log'] = '$ ' + ' '.join(cmd) + '\n' + (r.stdout or '') + (r.stderr or '')
        if r.returncode != 0:
            failures += 1
            resid = git(p, 'status', '--porcelain', '--', *DEPLOY_FILES).stdout.strip()
            row.update(result='실패', reason='설치기 rc=%d — %s' % (r.returncode, (r.stderr or r.stdout).strip().splitlines()[-1:] or ''), residual='예' if resid else '아니오'); continue
        changed = [l[3:].strip().strip('"') for l in git(p, 'status', '--porcelain', '--', *DEPLOY_FILES).stdout.splitlines()]
        if not changed:
            row.update(result='건너뜀', reason='설치기 실행 후 변경 없음'); continue
        r = git(p, 'add', '--', *changed)
        if r.returncode != 0: raise RuntimeError('git add 실패: ' + r.stderr.strip())
        msg = '작업 구조 설치/갱신: kickoff-workspaces v%s' % V
        r = git(p, 'commit', '--only', '-m', msg, '--', *changed)
        row['log'] += '$ git add -- %s\n$ git commit -m "%s"\n%s%s' % (' '.join(changed), msg, r.stdout or '', r.stderr or '')
        if r.returncode != 0:
            failures += 1
            row.update(result='실패', reason='커밋 실패 rc=%d(훅 거부 등, 우회 없음): %s' % (r.returncode, ' '.join((r.stderr or r.stdout).strip().splitlines()[:2])), residual='예(stage된 변경 남음: %s)' % ', '.join(changed)); continue
        sha = git(p, 'rev-parse', '--short', 'HEAD').stdout.strip()
        files = git(p, 'show', '--name-only', '--format=', 'HEAD').stdout.split()
        ignored = [f for f in DEPLOY_FILES if os.path.exists(os.path.join(p, f)) and git(p, 'check-ignore', '-q', f).returncode == 0]
        row.update(result='설치' if cur is None else '갱신', sha=sha, residual='아니오', reason=row['reason'] + ' — 커밋 파일 %d개: %s' % (len(files), ', '.join(files))
                   + (' — 주의: 프로젝트 .gitignore가 무시해 커밋에서 빠진 배포 파일 %d개(강제 추가하지 않음): %s' % (len(ignored), ', '.join(ignored)) if ignored else ''))
    except Exception as e:
        failures += 1
        resid = git(p, 'status', '--porcelain', '--', *DEPLOY_FILES).stdout.strip() if os.path.isdir(p) else ''
        row.update(result='실패', reason='예외: %s' % e, residual='예' if resid else '아니오')
    finally:
        print('%-24s %-6s %s' % (row['name'], row['result'], row['reason'][:110]))

summary = {}
for r in rows: summary[r['result']] = summary.get(r['result'], 0) + 1
status = ('실패 %d건 — ' % failures if failures else '성공 — ') + ', '.join('%s %d' % kv for kv in summary.items())
print(status)
write_report(status)
sys.exit(1 if failures else 0)
EOF
