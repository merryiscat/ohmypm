# ohmyPM 2.0 실행 가이드

Python 3.11+ 표준 라이브러리만 사용한다. 실행기는 외부 runtime 패키지(`runtime.path`, 아래 `<RUNTIME>`)에 있다.
프로젝트 작업 트리에는 실행기·절차·템플릿을 복사하지 않고, 추적 파일·index·HEAD·훅을 바꾸지 않는다.
상태·원문·승인·질문·증거는 Git 공통 디렉터리 `ohmypm/`(`git rev-parse --git-common-dir`)에 보존되며 Git 전송 대상이 아니다.
`--project`는 두 CLI 모두 명령 앞의 공통 옵션이다. 어느 워크트리에서든 같은 공통 상태를 읽는다.

## 등록과 진단

```text
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> [--home <external-data-dir>] [--profiles <roles.json>] [--dry-run]
python <RUNTIME>/scripts/environment_cli.py --project <project> doctor
python <RUNTIME>/scripts/environment_cli.py --project <project> role-connect --role main
```

외부 데이터 디렉터리 우선순위: `--home` → `OHMYPM_HOME` → Windows `LOCALAPPDATA/ohmypm`, POSIX `XDG_DATA_HOME/ohmypm`(기본 `~/.local/share/ohmypm`).
데이터 디렉터리는 모든 프로젝트 체크아웃 밖이어야 한다. 패키지는 `<home>/runtimes/<내용 해시>`에 불변으로 설치된다.
`roles.json`은 `{"roles":{"main":{"agent":"claude"},"pl":{"agent":"codex","model":"gpt-6-astra","effort":"high","approval":"bypass"},"work":{"agent":"claude","model":"sonnet"}}}` 형태다.
필드는 agent·model·effort·approval만 허용하며 값에 공백·특수문자를 넣지 않는다. 생략하면 패키지의 `templates/workflow.json`이 기본값이다.

같은 명령을 다시 실행하면 이미 있는 패키지를 검증만 하고 프로필 변경만 기록한다. 변경은 다음 작업의 기본값이며 진행 중 작업의 계약은 바뀌지 않는다.
`select-runtime --pin <saved-pin.json>`으로 저장된 pin을 다음 작업의 기본값으로 되돌릴 수 있다. 참조 중인 패키지는 삭제하지 않는다.
`doctor`는 설정·패키지 해시·활성 작업·main/pl 연결 기록을 보여 준다. 설치 확인일 뿐 지침 전달·행동 검증의 증거는 아니다.
schema가 다른 상태를 만나면 보존하고 맞는 runtime을 복구한다. 기존 1.0 작업은 그 프로젝트의 `.ohmypm/bin/workflow.py`로 마무리한다.

## 요청 분류와 설계

```text
python <RUNTIME>/scripts/environment_cli.py --project <project> route --request-id R-001 --request-file <request.txt> --path pl --reason "새 화면과 진입점 추가" --scope "계좌 화면, 사이드바 내 계좌/보고서"
python <RUNTIME>/scripts/workflow.py --project <project> create --task T-001 --request-id R-001 --request-file <request.txt> --spec <spec.md> --manifest <manifest.json> --main <main-path> --main-address <run:id> --pl-address <pl-location>
python <RUNTIME>/scripts/workflow.py --project <project> question --task T-001 --file <question.md>
python <RUNTIME>/scripts/workflow.py --project <project> events --task T-001
python <RUNTIME>/scripts/workflow.py --project <project> deliver --task T-001 --event <event-id>
python <RUNTIME>/scripts/workflow.py --project <project> revise --task T-001 --spec <spec.md> --manifest <manifest.json>
python <RUNTIME>/scripts/workflow.py --project <project> approve --task T-001 --revision 1 --decision-file <actual-user-decision.txt>
python <RUNTIME>/scripts/workflow.py --project <project> schedule --task T-001
python <RUNTIME>/scripts/workflow.py --project <project> prepare --task T-001 --work implementation
```

main은 수정 전에 `route`의 announcement(`처리 경로 / 근거 / 요청 범위`)를 사용자에게 그대로 알린다. 분류에 필요한 읽기 조사는 그 전에 해도 된다.
명확하고 작고 가역적인 수정만 `route --path direct --small-clear-reversible`로 기록한 뒤
`direct-exec --request-id <id> -- <argv...>`로 실행한다. 그 밖의 요청은 pl 경로다. 같은 request-id를 다시 route하면 이전 기록은 `route-r<n>.json`으로 남는다.
`create`는 pl 경로의 route와 원문이 일치하고 route 당시 환경(runtime·roles)이 지금과 같아야 한다. 달라졌으면 먼저 재분류한다.
`approve`는 실제 사용자 결정 파일만 받는다. 승인 digest에는 스펙·manifest와 runtime pin·프로필·route가 함께 묶인다.

manifest는 `criteria`(최대 8개)와 `works`로 구성한다. criterion은 `id`/`description`과 `command`(argv 배열) 또는 `manual`을 가진다.
work는 `id`/`paths`/`criteria`/`depends_on`/`parallel_safe`/`resources`/`harness`를 가진다.
`paths`는 POSIX prefix이며 glob은 받지 않는다. 병렬은 `parallel_safe: true`와 `independence_reason`이 필요하고 경로·자원이 겹치면 순차다.
`harness`는 `tools`/`setup`(argv 배열의 배열)/`files`(`source`,`target`)/`inherit_env`(변수 이름)/`ports`(변수 이름)다.
setup 명령은 셸 문자열로 합치지 않는다. 승인 후 source 해시가 바뀌면 준비를 중단한다.
`files`의 target은 추적 파일·기존 사용자 파일·링크를 덮어쓰지 않으며 제외 처리는 `info/exclude`의 소유 블록에서만 한다.
work의 임시 파일·context·harness 기록은 작업 트리가 아니라 상태 디렉터리 `tasks/<task>/r<n>/<work>/environment`에 둔다.

## 구현과 검증

실행은 Orca `orchestration` 스킬의 감독 흐름을 따르고 main이 Run을 준비한 뒤 `launch --task ... --work ...`로 준비된 work에만 에이전트를 시작한다.
work는 고정 runtime의 `workflow.py`만 사용한다.

```text
python <RUNTIME>/scripts/workflow.py --project <work-path> exec --task T-001 --work implementation -- python <tool.py>
python <RUNTIME>/scripts/workflow.py --project <work-path> submit --task T-001 --work implementation --report <report.md>
python <RUNTIME>/scripts/workflow.py --project <work-path> check --task T-001 --work implementation
python <RUNTIME>/scripts/workflow.py --project <work-path> show --task T-001
python <RUNTIME>/scripts/workflow.py --project <work-path> verdict --task T-001 --work implementation --review <review.json>
python <RUNTIME>/scripts/workflow.py --project <main-path> merge --task T-001 --work implementation
```

`verdict`는 pl이 남긴다. review.json은 `reviewer`=pl, `candidate`(submission과 같은 commit/base/revision/digest),
`code_review`(읽은 변경과 확인한 동작), `criteria`(id별 `status` pass/fail와 `evidence`)다.
자동 검증만 통과했다고 수동 기준을 pass로 만들지 않는다. 실패는 같은 work에서 고치고 submit→check→verdict를 반복한다.
`merge`는 dirty main·stale verdict·범위 밖 수정·하네스 전달물 stage를 거부하고 fast-forward만 한다.
Orca lifecycle 정산 뒤 `cleanup --task ... --work ... --settlement <receipt.json>`로 환경을 회수한다.
설계를 바꾸기 전에는 `retain --settlement <receipt.json>`으로 변경을 보존한 뒤 `revise`한다.
미반영 변경·새 커밋·남은 터미널·사용자 수정 전달물을 만나면 회수를 멈추고 이유를 기록한다.

## pl 세션 연결과 복구

```text
python <RUNTIME>/scripts/environment_cli.py --project <project> role-connect --role pl
python <RUNTIME>/scripts/environment_cli.py --project <project> role-show --role pl
python <RUNTIME>/scripts/environment_cli.py --project <project> role-accept --role pl --generation <n> --digest <context-digest>
python <RUNTIME>/scripts/environment_cli.py --project <project> role-reconcile --role pl --receipt <actual-create-receipt.json>
python <RUNTIME>/scripts/environment_cli.py --project <project> role-exit --role pl --receipt <exit-receipt.json>
python <RUNTIME>/scripts/environment_cli.py --project <project> context --role <main|pl|work>
```

`role-connect`는 살아 있는 세션이 있으면 재사용하고, 미등록이거나 종료가 확인된 경우에만 새 세션을 만든다. `unverifiable`이면 중복 생성하지 않는다.
순서는 durable intent 기록 → 터미널 생성 → context 전달 → pl의 `role-accept`다. 전달 성공과 수락은 구분된다.
생성 응답이 끊겼으면 `role-reconcile`에 실제 생성 receipt를 넣는다. 확인 전에는 다시 만들지 않는다.
종료는 `role-exit`에 실제 종료 receipt(exit wait 만족, terminal status exited, ptyKilled)를 넣어야 인정된다.
셸 잔존·tui-idle·타임아웃·응답 지연만으로는 생존도 종료도 판정하지 않는다. 실행 래퍼가 남긴 프로세스 생성 식별자와 종료 코드를 대조한다.
새 generation의 context에는 runtime 해시·상태 위치·절차·복구 지시가 들어간다. 이전 generation 기록은 `generation-<n>.json`으로 남는다.

```text
python <RUNTIME>/scripts/environment_cli.py --project <project> enqueue --role pl --message-id Q-001 --task T-001 --revision 1 --body-file <question.md>
python <RUNTIME>/scripts/environment_cli.py --project <project> deliver --message-id Q-001
python <RUNTIME>/scripts/environment_cli.py --project <project> acknowledge --message-id Q-001 --generation <n> --revision 1
python <RUNTIME>/scripts/environment_cli.py --project <project> acknowledge --message-id Q-001 --generation <n> --revision 1 --completed
```

질문·판정 요청은 먼저 outbox에 보존한다. `deliver`는 수락된(`ready`) 세션에만 보내고 같은 generation에 두 번 보내지 않는다.
새 pl은 outbox를 읽고 ID·generation·revision을 `acknowledge`로 수락한 뒤 처리하고 `--completed`로 끝낸다.
과거 generation 또는 다른 revision의 답변은 보존하되 적용하지 않는다. 세션 종료만으로 기존 승인·유효 판정을 무효화하지 않는다.

## 전환·백업·해제

```text
python <RUNTIME>/scripts/environment_cli.py --project <project> migration-plan [--catalog <legacy-v1.json>]
python <RUNTIME>/scripts/environment_cli.py --project <project> migration-apply --id <plan-id> --digest <reviewed-plan-digest>
python <RUNTIME>/scripts/environment_cli.py --project <project> migration-rollback --id <plan-id>
python <RUNTIME>/scripts/environment_cli.py --project <project> export --destination <new-external-backup-directory>
python <RUNTIME>/scripts/environment_cli.py --project <project> reconnect
python <RUNTIME>/scripts/environment_cli.py --project <project> disable
```

`migration-plan`은 1.0 설치본을 원본 바이트 기준으로 대조해 파일별 `remove/edit/keep/conflict`와 근거를 낸다.
정확히 알려진 설치본과 확인된 관리 블록만 제거·편집 후보다. 사용자 수정·불명 소유·출처 불명 훅은 conflict로 보존한다.
`docs/workflow.json`의 역할 프로필은 검증 후 로컬 상태로 옮긴다. `.gitignore`·`orca.yaml`·`.worktreeinclude`·`docs/tasks`·`docs/reviews`는 유지한다.
`migration-apply`는 검토한 plan digest를 요구하고 HEAD·index·hooksPath가 plan과 같을 때만 적용한다. 활성 1.0 작업이 있으면 적용하지 않는다.
적용 결과는 작업 트리 변경으로만 남는다. stage·commit·push하지 않으며 추적 파일 정리 커밋은 사용자가 별도로 검토한다.
중단된 apply는 receipt로 이어 가고, `migration-rollback`은 현재 바이트가 before/after 중 하나일 때만 복원한다. 충돌하면 둘 다 보존한다.

`export`는 상태 디렉터리를 새 외부 경로로 복사한다. 참조 중인 runtime 패키지는 따로 백업한다. 로컬 상태는 clone만으로 복구되지 않는다.
저장소가 이동했으면 `reconnect`로 공통 디렉터리 경로를 갱신한다. 원본이 남아 있는 복사본은 새 등록으로 처리하고 작업이 있으면 경로를 먼저 정리한다.
`disable`은 새 작업만 막고 진행 중 work·증거·패키지를 보존한다. 활성 work의 회수는 각 작업의 cleanup 절차를 따른다.

## Codex pl 실행 정책

사용자 지정에 따라 Codex pl의 기본 approval은 `bypass`다. 실행 argv는
`codex --dangerously-bypass-approvals-and-sandbox --model <합의 모델> -c model_reasoning_effort="<합의 effort>"`이며 마지막 인자로 초기 context를 넘긴다.
프로필에 `approval=default`를 명시하면 기본 CLI 정책을 쓴다. 정책은 프로필과 작업 계약 snapshot에 기록된다.
실행 래퍼(`role_runner.py`)가 실제 모델 프로세스의 pid·생성 식별자·종료 코드를 lifecycle 파일에 남긴다. tui-idle만으로 생존을 판단하지 않는다.
