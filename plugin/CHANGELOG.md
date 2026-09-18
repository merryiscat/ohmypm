# ohmypm 플러그인 변경 내역

프로젝트에 깔린 복사본의 버전은 각 프로젝트 `docs/protocol.md` 첫 줄에 있다. 올리려면 그 프로젝트 main에서 "구조 업데이트하자".

## 0.5.0 — 2026-09-18
- **모델 모드 스위치** `scripts/ws-model.sh <fable-out|fable-in|status> <프로젝트>...` — 페이블 주간 한도가 소진되면 roles.md의 페이블 자리(pl2 검토자·L 등급 워커)를 오퍼스로 내리고 **pl3를 열지 않는다**(pl2가 오퍼스라 검토·코디를 겸한다). 되돌리기는 `fable-in`
- 근거: Claude Code는 쿼터 소진으로 모델을 자동으로 내리지 않는다 — `--fallback-model`·settings.json `fallbackModel`은 과부하·미사용 가능만 대체하고 rate limit·요금 오류는 대체하지 않는다(공식 문서 model-config). 자동화할 수 있는 건 한 번에 전부 내리는 것뿐
- PROTOCOL "모델 모드" 절, dispatch 1절(모드 줄 먼저 읽기)·하지 않는 것, workspaces 1·3절
- 항체: Git Bash에서 `orca terminal send --text "/clear"`를 보내면 MSYS 경로 변환이 `C:/Program Files/Git/clear`로 바꿔 텍스트로 꽂힌다(두 번 실측) — PowerShell이나 `MSYS_NO_PATHCONV=1`

## 0.4.1 — 2026-09-18
- 항체 2(protocol 8절·dispatch 5절): `❯`여도 하단 "shell still running / ← agent"면 백그라운드 대기를 쥔 자리 — 비우지 않는다 / `/clear`는 텍스트로 들어가기도 하니 보낸 뒤 화면을 읽어 확인

## 0.4.0 — 2026-09-18
- **pl2를 둘로 가른다**: pl2 = 검토자(페이블 5.1, 검토서 한 장, 직후 `/clear`) / **pl3 = 코디네이터(오퍼스 5)** — 게이트·배정·`check --wait`·검증·compact. 0.1.1에서 배관을 전부 pl2로 몰았더니 최상위 모델 사용량이 감당이 안 됐다(사용자). 이종 교차 검토의 근거는 벤더 차이지 배관까지 최상위일 이유가 아니다
- protocol 토큰 규율·흐름·4·6·8절, dispatch 1·3·4·5·6절(pl2 `/clear`는 검토 직후, pl3 compact·clear는 기존 pl2 규칙 승계), workspaces 3절(터미널 셋), `templates/prompt-pl3.md` 신설
- **프로젝트 소유 파일 손질 필요**: `docs/roles.md`에 pl3 행 추가 + 터미널 구분 규칙(`--model`로 판별) — `templates/roles.md` 참고. ws-upgrade.sh가 pl3 행이 없으면 WARN을 찍는다. 열려 있는 pl 워크트리엔 pl3 터미널을 하나 더 연다(workspaces 3절)

## 0.3.1 — 2026-09-17
- 항체 3: 일하는 중인 터미널엔 아무것도 보내지 않는다(보내기 전 화면 확인) / 긴 실행은 백그라운드 + 진행 로그 / 멈춤 판정은 시간 상한이 아니라 **진행 신호 끊김**(기본 10분) — "1분 금지·15분 상한"은 사용자 지적으로 철회(0.3.2)

## 0.3.0 — 2026-09-17
- **차선 S/M/L**(protocol 0절): 실측 20~40분이던 절차를 요청 크기별로. S는 main이 직접(3~5분), M은 짧은 스펙·차단만 검토·v2 생략·게이트 없음·짧은 검증(10분), L은 전체
- dispatch 0절 차선 판정, 메시지에 차선 명시. CLAUDE.md 블록 마지막 줄 교체(관리 파일이라 업데이트로 반영)
- 선택: roles.md에 `게이트: M`을 적으면 M도 승인을 묻는다(프로젝트 소유 파일 — 손으로)

## 0.2.0 — 2026-09-17
- 버전 관리 시작: 관리 파일에 버전 도장, `scripts/ws-upgrade.sh`로 설치·업데이트 일원화, 이 CHANGELOG
- 관리 파일(덮어씀): docs/protocol.md, docs/tasks/_template.md, docs/reviews/_template.md, .githooks/pre-commit, AGENTS.md·CLAUDE.md 블록
- 프로젝트 소유(안 덮음): docs/roles.md, orca.yaml, .worktreeinclude, .gitignore

## 0.1.7 — 2026-09-17
- dispatch 6절 동시 요청: main 하나·대기는 백그라운드·pl 직렬·워커 병렬

## 0.1.6
- 세션 위생: clear=태스크 경계, compact=도중. dispatch 4절을 배정·대기 / compact / 검증으로 분리

## 0.1.5
- protocol 8절 세션 비우기 기준

## 0.1.4
- dispatch 스킬 신설(main은 요청을 pl→pl2로 넘긴다), CLAUDE.md 블록 마지막 줄 교체

## 0.1.3
- protocol 4절 "배정 전 원격과 맞추기" 항체

## 0.1.2
- pl 규율 정정: 금지는 셸이 아니라 실행·설치(Codex는 파일도 셸로 읽는다)

## 0.1.1
- pl은 스펙 v1·v2만, 검토·배정·대기·검증은 pl2. Codex 기본 effort high

## 0.1.0
- 킥오프 하네스를 플러그인으로: kickoff-interview → kickoff-workspaces 기본 경로, refsweep·usecases 선택, llmwiki
