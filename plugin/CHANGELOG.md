# ohmypm 플러그인 변경 내역

프로젝트에 깔린 복사본의 버전은 각 프로젝트 `docs/protocol.md` 첫 줄에 있다. 올리려면 그 프로젝트 main에서 "구조 업데이트하자".

## 0.3.1 — 2026-09-17
- 항체 3: 일하는 중인 터미널엔 아무것도 보내지 않는다(보내기 전 화면 확인) / pl2 검증은 산출물 읽기, 1분 넘는 명령 금지 / main 대기는 백그라운드 + 15분 상한, 넘으면 `--interrupt`

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
