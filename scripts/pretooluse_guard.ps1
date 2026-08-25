# ohmyPM PreToolUse 가드 (자율경계 L3 — 인자 레벨 방어).
# headless 호출 시 대상에 주입해, Bash 명령의 되돌리기 불가능/외부발신 패턴을 결정론적으로 차단.
# ★ LLM 자가판단 개입 없음 — 정규식·목록 대조만 (confused-deputy 항체).
# Claude Code PreToolUse 훅 규약: stdin JSON, 차단은 exit 2 + stderr 메시지.

$ErrorActionPreference = "Stop"
try {
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
} catch {
    exit 0  # 파싱 실패 시 통과(방해 금지) — 도구 레벨(allowedTools)이 1차 방어
}

$cmd = $payload.tool_input.command
if (-not $cmd) { exit 0 }

# 되돌리기 불가능 / 외부 발신 패턴 (allowedTools가 도구명 단위라 못 막는 인자 레벨)
$danger = @(
    'rm -rf', 'rm -r', 'rm -f', 'Remove-Item',
    'git push --force', 'git push -f',
    'DROP TABLE', 'DROP DATABASE', 'TRUNCATE',
    'mkfs', 'format ',
    'curl ', 'wget ', 'Invoke-WebRequest', 'Invoke-RestMethod'
)
foreach ($p in $danger) {
    if ($cmd -like "*$p*") {
        [Console]::Error.WriteLine("ohmyPM 게이트: 되돌리기 불가능/외부발신 차단 - '$p'")
        exit 2
    }
}
exit 0
