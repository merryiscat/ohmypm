#!/bin/sh
# kickoff-workspaces 관리 파일 설치/업데이트.  사용: ws-upgrade.sh <project-path> [--install "<shared dirs>" "<setup cmd>"]
# 관리 파일(순수 복사본)만 갈아 끼운다: docs/protocol.md, docs/tasks/_template.md, docs/reviews/_template.md,
#   .githooks/pre-commit, AGENTS.md·CLAUDE.md의 "## 작업 구조 (kickoff-workspaces)" 블록.
# 프로젝트 소유 파일(docs/roles.md, orca.yaml, .worktreeinclude, .gitignore)은 --install 때 없으면 만들 뿐, 절대 덮지 않는다.
# 커밋은 하지 않는다 — 호출한 쪽(main)이 diff를 보고 커밋한다.
set -e
P="$1"; MODE="$2"; SHARED="$3"; SETUP="$4"
K="$(cd "$(dirname "$0")/.." && pwd)"                 # skills/kickoff-workspaces
ROOT="$(cd "$K/../.." && pwd)"                         # plugin root
V=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)
T="$K/templates"
[ -d "$P" ] || { echo "no such project: $P" >&2; exit 2; }
cd "$P"
CUR=$(sed -n '1s/.*kickoff-workspaces v\([0-9.]*\).*/\1/p' docs/protocol.md 2>/dev/null)
echo "project: $P"; echo "installed: ${CUR:-none}  ->  plugin: $V"

stamp() { printf '<!-- kickoff-workspaces v%s — 원본은 ohmypm 플러그인. 여기서 고치지 말고 플러그인을 고친 뒤 "구조 업데이트하자" -->\n' "$V"; }
mkdir -p docs/tasks docs/reviews .githooks
{ stamp; cat "$K/PROTOCOL.md"; } > docs/protocol.md
{ stamp; cat "$T/task.md"; }    > docs/tasks/_template.md
{ stamp; cat "$T/review.md"; }  > docs/reviews/_template.md
{ printf '#!/bin/sh\n# kickoff-workspaces v%s (관리 파일 — 플러그인에서 갱신)\n' "$V"; sed '1{/^#!/d;}' "$T/pre-commit"; } > .githooks/pre-commit
git config core.hooksPath .githooks 2>/dev/null || true

# 블록 교체: "## 작업 구조 (kickoff-workspaces)" 헤더부터 다음 "## " 헤더 또는 파일 끝까지
python - "$T" "$V" <<'EOF'
import io,sys,os,re
T,V=sys.argv[1],sys.argv[2]
for f,blk,head in [('AGENTS.md','AGENTS.md.block','# AGENTS.md — Codex용 지시문 (Claude는 CLAUDE.md를 읽는다)\n\n'),
                   ('CLAUDE.md','CLAUDE.md.block',None)]:
    new=io.open(os.path.join(T,blk),encoding='utf-8').read().rstrip('\n')
    new=new.replace('## 작업 구조 (kickoff-workspaces)','## 작업 구조 (kickoff-workspaces v%s)'%V,1)+'\n'
    if os.path.exists(f):
        s=io.open(f,encoding='utf-8').read()
    else:
        s=head if head else '# %s\n\n'%os.path.basename(os.getcwd())
    pat=re.compile(r'## 작업 구조 \(kickoff-workspaces[^)]*\)\n.*?(?=\n## |\Z)', re.S)
    if pat.search(s): s=pat.sub(lambda m:new.rstrip('\n'), s, count=1)
    else: s=s.rstrip('\n')+'\n\n'+new
    io.open(f,'w',encoding='utf-8',newline='\n').write(s if s.endswith('\n') else s+'\n')
    print('block:',f)
EOF

if [ "$MODE" = "--install" ]; then
  [ -f docs/roles.md ] || cp "$T/roles.md" docs/roles.md
  if [ ! -f orca.yaml ]; then
    { echo "# Orca 워크트리 설정 (kickoff-workspaces). 공유 폴더는 symlink — 정확 동기화(uv sync 등)를 setup에 걸지 않는다."
      echo "worktree:"; echo "  sharedDirectories:"; for d in $SHARED; do echo "    - $d"; done
      [ -n "$SETUP" ] && { echo "scripts:"; echo "  setup: |"; echo "    $SETUP"; }; } > orca.yaml
  fi
  [ -f .worktreeinclude ] || printf '# 새 워크트리마다 복사되는 gitignore 파일 (Orca .worktreeinclude)\n.env\n.claude/settings.local.json\n' > .worktreeinclude
fi
echo "--- changed:"; git status --short -- docs/protocol.md docs/tasks/_template.md docs/reviews/_template.md .githooks/pre-commit AGENTS.md CLAUDE.md docs/roles.md orca.yaml .worktreeinclude 2>/dev/null || true
echo "done: v$V  (pl·pl2 세션은 /clear — 규칙 파일이 바뀌었다)"
