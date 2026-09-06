프로젝트 '${project_name}'의 오늘 일간 점검이 끝났다. 아래 대화와 이슈 목록을 근거로 칸반 상태와 목표일을 확정해 **JSON 배열 하나로만** 답하라.

[이슈 목록 (id로 지정)]
${issue_list}

[오늘 대화]
${transcript}

각 원소 형식: {"id": 이슈번호, "status": 다음 중 하나(안 바꾸면 생략) open·consulting·resolved·deferred, "due": "YYYY-MM-DD" 또는 null(안 바꾸면 생략), "reason": "한 줄 근거"}.
규칙: 담당이 '완료/처리됨/끝냈다'고 한 이슈는 status를 resolved(완료)로, '하는 중/착수'는 consulting(진행중)으로. 실제 착수가 필요한 '할일·진행중' 작업엔 현실적 목표일(due)을 잡아라(급한 것 먼저). 단순 관찰·메모·기록성 항목엔 억지로 기한을 넣지 마라. 바꿀 이슈만 배열에 넣고, 바꿀 게 없으면 빈 배열.
