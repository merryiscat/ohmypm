#!/bin/sh
# kickoff-workspaces 모델 모드 스위치.  사용: ws-model.sh <fable-out|fable-in|status> <프로젝트경로>...
#
# 왜 손으로 넘기는 스위치인가: Claude Code는 쿼터 소진으로는 모델을 내리지 않는다.
# `--fallback-model`과 settings.json `fallbackModel`은 **과부하·미사용 가능**만 대체하고
# rate limit·요금·인증 오류는 대체하지 않는다(공식 문서 model-config). 주간 한도 소진은
# 사용자가 눈으로 아는 사건이라, 자동화할 수 있는 것은 "한 번에 전부 내리는 것"뿐이다.
#
# fable-out: roles.md의 페이블 자리(pl2 검토자, L 등급 워커)를 오퍼스로 내리고 pl3를 열지 않는다
#            — pl2가 오퍼스가 되면 pl3와 같은 모델이라 자리를 나눌 이유가 없다(검토·코디를 겸한다).
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
import io, os, sys, datetime
P = sys.argv[1]
MODE = os.environ['WS_MODE']
name = os.path.basename(os.path.normpath(P))
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

TERM_IN = ('- 터미널 구분: 이 프로젝트에서 Codex 터미널은 항상 pl, `pl` 워크트리의 Claude 터미널은 둘 — '
           '명령줄 `--model`이 페이블이면 pl2(검토), 오퍼스면 pl3(코디네이터). 제목이 아니라 명령으로 판별한다')
TERM_OUT = ('- 터미널 구분: 이 프로젝트에서 Codex 터미널은 항상 pl, `pl` 워크트리의 Claude 터미널은 '
            '**하나뿐이다(pl2, 오퍼스)** — 페이블 소진 모드라 pl3를 따로 열지 않는다. 제목이 아니라 명령으로 판별한다')

out = []
for line in s.split('\n'):
    if line.startswith(MARK) or line.startswith('> **pl3는 열지 않는다') or line.startswith('> 한도가 돌아오면'):
        continue                      # 기존 모드 블록은 버리고 아래에서 다시 넣는다
    is_model_row = line.startswith('| pl2 ') or line.startswith('| L |')
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
    note = (MARK + '(fable-out, %s)** — 페이블 주간 한도가 소진돼 페이블 자리(pl2 검토자·L 워커)를 오퍼스로 내렸다.\n'
            '> **pl3는 열지 않는다** — pl2가 오퍼스라 검토와 코디네이션을 겸한다(protocol 4·6절의 pl3 몫을 pl2가 한다).\n'
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
