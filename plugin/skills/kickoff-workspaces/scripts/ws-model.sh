#!/bin/sh
# kickoff-workspaces 모델 모드 스위치.  사용: ws-model.sh <fable-out|fable-in|status> <프로젝트경로>...
#
# 왜 손으로 넘기는 스위치인가: Claude Code는 쿼터 소진으로는 모델을 내리지 않는다.
# `--fallback-model`과 settings.json `fallbackModel`은 **과부하·미사용 가능**만 대체하고
# rate limit·요금·인증 오류는 대체하지 않는다(공식 문서 model-config). 주간 한도 소진은
# 사용자가 눈으로 아는 사건이라, 자동화할 수 있는 것은 "한 번에 전부 내리는 것"뿐이다.
#
# fable-out: roles.md의 페이블 자리(pl2 검토자)를 오퍼스로 내린다.
#            구현은 main이 하므로 워커 모델은 없다(0.7.0).
#            교차 검토의 근거는 그대로다: 작성자 Codex vs 검토자 Claude, 벤더가 다르면 성립한다.
# fable-in:  한도가 돌아오면 되돌린다.
set -e
MODE="$1"
[ -n "$MODE" ] || { echo "usage: ws-model.sh <fable-out|fable-in|status> <project>..." >&2; exit 2; }
shift
case "$MODE" in fable-out|fable-in|status) ;; *) echo "unknown mode: $MODE" >&2; exit 2;; esac
[ $# -gt 0 ] || { echo "no projects given" >&2; exit 2; }
for P in "$@"; do
  if [ ! -f "$P/docs/roles.md" ]; then echo "skip (no docs/roles.md): $P"; continue; fi
  WS_MODE="$MODE" python - "$P" <<'EOF'
import io, os, sys, datetime, json
P = sys.argv[1]
MODE = os.environ['WS_MODE']
name = os.path.basename(os.path.normpath(P))
config = os.path.join(P, 'docs', 'workflow.json')
if os.path.exists(config):
    if MODE == 'status':
        print(json.dumps(json.load(io.open(config, encoding='utf-8')), ensure_ascii=False, indent=2))
        raise SystemExit
    raise SystemExit('1.0 uses explicit roles in docs/workflow.json. Update the agreed role there; legacy pl2 modes do not apply.')
f = os.path.join(P, 'docs', 'roles.md')
s = io.open(f, encoding='utf-8').read()

MARK = '> **모델 모드: 페이블 소진'
cur = 'fable-out' if MARK in s else 'fable-in'

if MODE == 'status':
    print('%-24s %s' % (name, cur))
    raise SystemExit
if cur == MODE:
    print('%-24s 이미 %s' % (name, MODE))
    raise SystemExit

TERM_IN = ('- 터미널 구분: `pl` 워크트리에서 Codex 터미널은 pl, Claude 터미널은 pl2. '
           '제목이 아니라 명령으로 판별한다')
TERM_OUT = TERM_IN

out = []
for line in s.split('\n'):
    if line.startswith(MARK) or line.startswith('> 검토 방향(Codex') or line.startswith('> 한도가 돌아오면'):
        continue                      # 기존 모드 블록은 버리고 아래에서 다시 넣는다
    is_model_row = line.startswith('| pl2 ')
    if MODE == 'fable-out':
        if is_model_row:
            line = line.replace('`claude-fable-5-1`', '`claude-opus-5`')
        if line.startswith('- 터미널 구분'):
            line = TERM_OUT
    else:
        if is_model_row:
            line = line.replace('`claude-opus-5`', '`claude-fable-5-1`')
        if line.startswith('- 터미널 구분'):
            line = TERM_IN
    out.append(line)
s = '\n'.join(out)

if MODE == 'fable-out':
    note = (MARK + '(fable-out, %s)** — 페이블 주간 한도가 소진돼 pl2 검토자를 오퍼스로 내렸다.\n'
            '> 검토 방향(Codex 작성 → Claude 검토)은 그대로다.\n'
            '> 한도가 돌아오면 `ws-model.sh fable-in <프로젝트>`. 쿼터 소진은 Claude Code가 자동으로 모델을 내려 주지 않는다.\n'
            ) % datetime.date.today().isoformat()
    i = s.index('| 역할 |')
    s = s[:i] + note + '\n' + s[i:]

while '\n\n\n' in s:
    s = s.replace('\n\n\n', '\n\n')
io.open(f, 'w', encoding='utf-8', newline='\n').write(s if s.endswith('\n') else s + '\n')
print('%-24s %s -> %s' % (name, cur, MODE))
EOF
done
