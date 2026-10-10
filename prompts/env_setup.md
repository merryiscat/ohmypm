아래는 프로젝트 하나의 스냅샷(코드가 수집한 사실)과 ohmyPM이 가진 재료 표다. 이 프로젝트의 Claude Code 작업 환경을 조금 낫게 만들 변경안을 최대 ${max_items}개 내라. 고칠 게 없으면 {"items": []}로 답한다.

형식(키 이름 그대로, JSON 객체 하나):
{"items": [{"id": "item-1", "kind": "claude_md", "title": "짧은 제목", "why": "왜 필요한지 한두 문장", "target": "CLAUDE.md", "op": "append", "before": null, "after": "덧붙일 내용", "material": null, "experimental": false}]}

규칙:
- kind는 claude_md, agents_md, settings, skill, doc 중 하나. op는 create, append, replace 중 하나.
- 대상은 종류마다 하나로 정해져 있다: claude_md → 루트 CLAUDE.md, agents_md → 루트 AGENTS.md, settings → .claude/settings.json. .claude/settings.local.json은 바꾸지 않는다. 같은 파일을 바꾸는 항목은 하나만 낸다.
- create는 없는 파일에만, append는 있는 파일 끝에 덧붙일 때, replace는 있는 파일의 한 부분을 바꿀 때. replace에는 before에 바꿀 원문을 스냅샷 원문 그대로(한 번만 나오는 조각으로) 넣는다. replace가 아니면 before는 null.
- settings는 기존 permissions.deny에 거부 규칙을 더하는 변경만 된다(예: .env 읽기, rm, 강제 푸시 막기). 허용 권한을 넓히거나, 기존 규칙을 지우거나, 훅을 바꾸지 않는다. create면 after는 그 파일 전체 JSON, replace면 before/after는 바꿀 부분 원문.
- 실행·검증 명령은 스냅샷 commands에 근거가 있는 것만 적는다. 지어내지 않는다.
- <!-- ohmypm:start --> ~ <!-- ohmypm:end --> 블록 안은 건드리지 않는다. CLAUDE.md가 @AGENTS.md로 AGENTS.md를 불러오고 있으면 그 줄을 지우지 않는다. 내용 있는 AGENTS.md만 있는데 CLAUDE.md를 새로 만들면 첫 줄에 @AGENTS.md를 넣는다.
- 이미 지침에 있는 내용과 겹치는 줄은 내지 않는다. 한 번에 크게 바꾸지 말고 꼭 필요한 것만.
- skill은 재료 표에 있는 스킬만, material에 재료 이름(표의 백틱 안 이름 그대로)을 넣는다. target은 .claude/skills/<스킬 폴더 이름>/SKILL.md, op는 create. 설치 명령은 쓰지 않는다(ohmyPM이 안내문을 만든다). doc도 재료 표의 문서 재료를 쓸 때 material에 이름을 넣는다. 재료 표에 없는 스킬·도구는 제안하지 않는다.
- experimental은 아무 값이나 넣어도 된다(ohmyPM 코드가 재료 표를 보고 다시 정한다).
- title·why·after의 설명 문장은 한국어로, 비개발자도 읽을 수 있게 쉽게. 명령·JSON 키·경로는 원래 글자 그대로. 이모지·장식 기호·설명 없는 줄임말은 쓰지 않는다.

[재료 표]
${materials}

[스냅샷]
${snapshot}
