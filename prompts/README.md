# 에이전트 지시문 (prompts/)

여기 있는 파일들이 ohmyPM 에이전트들의 실제 지시문이다. 코드가 아니라 문서라서
**사장님이 직접 읽고 고칠 수 있고**, 에이전트도 개선안을 제안할 수 있다
(2026-09-06 사용자 확정: 지시문 하드코딩 금지).

## 고치는 법

- `${변수}` 자리표시자는 코드가 실행 때 채운다 — 이름을 바꾸거나 지우면 안 된다.
  문장·규칙·예시는 자유롭게 고쳐도 된다.
- **본문 템플릿**(소문자 파일: `pm_turn.md`, `board_write.md` 등)은 매 호출 새로 읽는다
  → 저장하면 즉시 반영, 서버 재시작 불필요.
- **시스템 프롬프트**(`*_system.md`, `gate.md`, `baseline_note.md`)는 서버 시작 때 읽는다
  → 고친 뒤 서버 재시작 필요.
- 조립 로직(빈 값 기본치, 조건부 블록, 게이트 부착)은 `src/cc/prompts.py`에 있다.

## 파일 지도

| 에이전트 | 시스템 | 본문 템플릿 |
|----------|--------|------------|
| 판정(오탐·분류) | judge_system | judge_issues |
| 완결 검증(코드 대조) | issue_verify_system | issue_verify |
| 담당 룸 대화 | room_system | room_chat |
| 일간보고 PM | pm_system · manage_system | pm_turn · pm_manage |
| 일간보고 담당 답변 | room_system(공용) | daily_agent_answer |
| 게시판 글쓰기/둘러보기 | board_write_system · board_system | board_write · board_comment |
| 게시판 반응/대대댓글 | feedback_system · followup_system | post_feedback · comment_followup |
| 조언 반영 | reprocess_system | reprocess_docs |
| 하네스 감사(골격 생성) | harness_audit_system | harness_audit_prompt |
| 온보딩 검토 | onboarding_system | onboarding_review |
| 총괄 관리자 | manager_system | manager_plan · manager_close |
| PM 대화 패널 | pm_chat_system | pm_chat |
| 전문가 | expert_system | expert_collect · expert_consult |
| 보상 | reward_system | reward_choice · wish_prompt |
| 공통 | gate(안전 게이트) · baseline_note(비개발자 기본 문장) | summarize_unresolved |
