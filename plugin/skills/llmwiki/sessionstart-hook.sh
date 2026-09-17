#!/usr/bin/env bash
# llmwiki SessionStart 훅 (macOS/Linux용) — 세션 시작 때 두 가지를 주입한다:
# ① docs/pending.md에서 재검토 시점(ISO 날짜)이 도래한 보류 안건 (조건형은 lint가 점검)
# ② docs/status.md(작업 보드)가 있으면 착수 전 읽기 상기
# Windows용 sessionstart-hook.ps1과 동일 동작 — 한쪽을 고치면 다른 쪽도 같이 고칠 것

if [ -f "docs/pending.md" ]; then
    today=$(date +%Y-%m-%d)
    # 표의 행(| 포함) 중 첫 번째 ISO 날짜가 오늘 이하인 행만 추린다 (ISO 날짜는 문자열 비교 = 날짜 비교)
    due=$(awk -v today="$today" '/\|/ && match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}/) {
        d = substr($0, RSTART, RLENGTH)
        if (d <= today) print
    }' docs/pending.md)
    if [ -n "$due" ]; then
        echo "[llmwiki] 재검토 시점이 도래한 보류 안건이 있다:"
        echo "$due"
        echo "사용자에게 이 안건의 재검토 미팅 시작을 제안하라. 재검토가 끝나면 pending.md에서 해당 행을 결정 페이지로 옮긴다."
    fi
fi

if [ -f "docs/status.md" ]; then
    echo "[llmwiki] 작업 착수 전 docs/status.md(작업 보드)를 먼저 읽어라 — 진행 중·미해결이 거기 있다."
fi
exit 0
