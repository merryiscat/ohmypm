# 에이전트 지시문 (prompts/)

여기 있는 파일들이 ohmyPM 에이전트들의 실제 지시문이다. 코드가 아니라 문서라서
**사용자가 직접 읽고 고칠 수 있다**(2026-09-06 확정: 지시문 하드코딩 금지).

## 고치는 법

- `${변수}` 자리표시자는 코드가 실행 때 채운다 — 이름을 바꾸거나 지우면 안 된다.
  문장·규칙·예시는 자유롭게 고쳐도 된다.
- **본문 템플릿**(`board_write.md`, `weekly_report.md` 등)은 매 호출 새로 읽는다 → 저장하면 즉시 반영.
- **시스템 프롬프트**(`*_system.md`, `gate.md`)는 서버 시작 때 읽는다 → 고친 뒤 서버 재시작.
- 조립 로직(빈 값 기본치, 게이트 부착)은 `src/cc/prompts.py`, 랩실·복기·주간보고는 각 모듈이 `load/render`로 직접 읽는다.

## 파일 지도

| 쓰는 곳 | 시스템 | 본문 템플릿 |
|----------|--------|------------|
| 담당 룸 대화 | room_system | room_chat |
| 게시판 글쓰기 / 둘러보기 | board_write_system · board_system | board_write · board_comment |
| 게시판 글쓴이 반응 / 대대댓글 | feedback_system · followup_system | post_feedback · comment_followup |
| 토론 복기(배운 것) | board_reflect_system | board_reflect |
| 주간보고 | weekly_system · weekly_pm_system | weekly_report · weekly_pm · weekly_agent |
| 랩실 웹 조사(디자인·스킬) / 모델 제안 | lab_research_system | lab_research · lab_proposal |
| 랩실 자문 | expert_system | expert_consult |
| 모델 동향 수집(모델 연구원 엔진) | — | model_catalog_update · model_profile |
| 공통 | gate(안전 게이트) | — |
