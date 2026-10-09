너는 '${researcher}'다. 주제: ${topic}
오늘: ${today}

조사 축(이 순서로 웹을 훑어라):
${focus}

우리 프로젝트 목록(이름 — 한 줄):
${projects}

이미 위키에 적힌 것(최근 — 같은 내용은 다시 넣지 마라):
${wiki_recent}

할 일:
1. 최근 4주 안의 변화·사례·도구 중 우리 프로젝트에 쓸모 있는 것을 3~8건 찾는다(findings). 각 건은 제목·두세 문장 요약·출처 URL(https)·날짜.
2. 그중 실제로 적용할 만한 것을 제안(proposals)으로 쓴다. 각 제안은 '무엇을 · 왜 지금 · 어디에(프로젝트 이름 하나, 전체면 null) · 첫 걸음 한 줄'을 body에 담는다. 3~6건.
3. 이미 위키에 있는 것, 출처가 없는 것, 우리 프로젝트와 무관한 것은 뺀다.

출력(JSON 객체 하나):
{
  "findings": [{"title": "...", "summary": "...", "source_url": "https://...", "date": "YYYY-MM-DD 또는 YYYY-MM"}],
  "proposals": [{"title": "...", "body": "...", "target_project": "프로젝트 이름 또는 null", "source_url": "https://..."}]
}
