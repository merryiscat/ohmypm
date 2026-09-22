---
name: dispatch
description: ohmyPM 요청을 수정 전 direct/pl로 분류하고 설계 승인, work 구현, pl 검증, 로컬 통합으로 진행한다. 새 화면·사용자 기능·흐름은 pl로 연결하며 종료된 pl은 영속 기록에서 복구한다.
---

# 요청에서 검증된 결과까지

외부 환경이 등록되어 있으면 runtime.path의 PROTOCOL.md와 references/entry.md를 읽는다.
미등록이면 kickoff-workspaces로 등록한다. 기존 1.0 작업은 원래 실행기와 상태를 유지한다.
프로젝트 지침을 새 하네스 지침으로 덮어쓰지 않는다.

main은 읽기 조사는 할 수 있지만 수정 전에 경로·근거·범위를 표시하고 route에 기록한다.
새 화면·사용자 기능/흐름·데이터/권한 계약·연동·비가역 변경은 pl이다. 명확하고 작고 가역적인 수정만 direct다.
“계좌 화면과 내 계좌/보고서 사이드바”는 pl에 연결한다. 파일 수 임계치를 쓰지 않는다.

pl이 없으면 role-connect로 준비한다. 종료 확인과 불명 상태를 구분하고 불명 상태에서 중복 실행하지 않는다.
새 pl은 기존 spec/승인/질문/증거를 읽고 generation과 context digest를 수락한다.
질문은 enqueue/deliver/acknowledge로 보존·전달·수락·완료를 구분한다.
main은 사용자가 직접 대화할 pl 위치를 안내한다. main이 설계 승인·품질 판정을 대신하지 않는다.

1. pl이 사용자와 기준·검증·경로·하네스를 합의한다. main은 route ID로 create하고 실제 사용자 요청으로 approve한다.
2. main이 schedule/prepare 후 Orca orchestration 스킬의 감독 흐름에서 launch한다. main만 coordinator다.
3. work는 workflow exec로 도구 실행, 구현 커밋, submit을 하고 자기 live preamble로 완료를 보고한다.
4. pl은 check 증거와 실제 동작으로 verdict한다. 실패·새 후보는 수정·재검증하며 기준을 낮추지 않는다.
5. main은 검증된 결과를 로컬 merge하고 Orca 정산을 확인한 후 cleanup한다. 새 변경·무관한 세션을 보존한다.

[운영 명령과 복구](references/runtime.md)를 따른다. 업데이트는 미래 작업에만 적용한다.
진행 작업은 고정 패키지로 라우팅한다. 푸시·배포·타 프로젝트 전환은 별도 범위다.
