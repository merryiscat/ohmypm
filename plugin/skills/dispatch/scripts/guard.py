#!/usr/bin/env python3
"""PreToolUse guard — Bash 명령의 되돌리기 불가능·외부 발신 패턴을 결정론적으로 차단한다.

역할 세션은 승인 프롬프트 없이(bypass) 뜬다. 승인 프롬프트는 안전장치가 아니라 사람이
온종일 읽고 누르는 일이 되기 때문이다(2026-09-23 사용자 결정). 대신 이 가드가 런타임에
실려 다니며 --settings로 세션에 얹힌다 — 프로젝트에는 아무 파일도 설치하지 않는다(T-006, PROTOCOL [P-16]).

★ 모델 자가판단 없음 — 목록 대조만 한다(confused-deputy 항체). 규약: stdin JSON,
차단은 exit 2 + stderr 메시지, 그 외 exit 0. stdin을 못 읽으면 통과시킨다(방해 금지 —
도구 단위 차단은 --disallowedTools가 따로 맡는다).
"""

import argparse
import json
import sys
from pathlib import Path

# templates/harness.json과 같은 값 — 파일을 못 읽을 때의 마지막 보루
DEFAULT_DENY = [
    "rm -rf", "rm -r", "rm -f", "Remove-Item",
    "git push --force", "git push -f", "git reset --hard", "git clean -f",
    "DROP TABLE", "DROP DATABASE", "TRUNCATE",
    "mkfs", "format ",
    "curl ", "wget ", "Invoke-WebRequest", "Invoke-RestMethod",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deny", help='{"deny": [...]} JSON; 없거나 못 읽으면 기본 목록')
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    deny = DEFAULT_DENY
    if args.deny:
        try:
            loaded = json.loads(Path(args.deny).read_text(encoding="utf-8-sig"))["deny"]
            deny = [p for p in loaded if isinstance(p, str) and p.strip()]
        except Exception:
            pass
    low = command.lower()
    for pattern in deny:
        if pattern.lower() in low:   # PowerShell 원본의 -like "*p*"와 같이 대소문자 무시
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
            sys.stderr.write(f"ohmyPM 가드: 되돌리기 불가능/외부발신 차단 - '{pattern}'\n")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
