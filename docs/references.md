# 레퍼런스 (킥오프 레퍼런스 스윕)

derived_from: 레퍼런스 스윕 워크플로 2026-08-21 (원시 결과: [raw/refsweep-2026-08-21.json](raw/refsweep-2026-08-21.json))

스윕 매트릭스: 기능 4축(하네스 점검 / 진행 추적·브리핑 / 문서 건강 / 자율 실행) × 지역 4(한·미·중·일).
알림·보고(텔레그램) 축은 Project Odin 기지 영역이라 제외.
통계: 원시 128건 → 중복 제거 124건 → **검증 keep 30 / drop 0 / 미검증 94**(검증 상한 30에 잘림 — 하단 접힌 절 참조).

## 환경·하네스 점검 (7)

| 이름 | kind | 지역 | 요약 | 활성·신호 |
|------|------|------|------|----------|
| [ctxlint](https://github.com/YawLabs/ctxlint) | code | US | CLAUDE.md·AGENTS.md를 **실제 코드베이스와 대조**해 lint — 깨진 경로·틀린 명령·낡은 컨텍스트·모순, cross-project 일관성까지. '컨텍스트 부패 감지'의 핵심 참고 | ★9, push 2026-08 활성 |
| [AgentLint (0xmariowu)](https://github.com/0xmariowu/AgentLint) | tool | US | '에이전트 하네스 linter' — 컨텍스트 파일+CI+훅+.gitignore를 51개 결정적 체크로 점검, 근거 출처 인용. 점검 항목 설계 참고 | ★53, push 2026-07, agentlint.app |
| [agentlint (akz4ol)](https://github.com/akz4ol/agentlint) | code | US | 에이전트 설정 supply-chain 보안 스캐너 — curl\|bash·시크릿 유출·권한 상승 등 20룰/8카테고리. 보안 축 체크 카탈로그 | ★3, push 2026-04 |
| [agents-md (ivawzh)](https://github.com/ivawzh/agents-md) | code | US | AGENTS.md를 프래그먼트 조합으로 생성, pre-commit 훅으로 자동 최신화. '훅 기반 컨텍스트 자동 갱신' 패턴 | ★8, push 2025-10 (10개월 정체) |
| [cc-switch](https://github.com/farion1231/cc-switch) | tool | CN | 여러 AI 코딩 에이전트의 설정(API·모델·MCP·스킬)을 통합 관리·전환하는 데스크톱 앱. 멀티 설정 관리 UX 참고 | ★128.5K, push 2026-08 매우 활발 |
| [awesome-korean-agent-skills](https://github.com/J-nowcow/awesome-korean-agent-skills) | code | KR | 한국어 AI 코딩 에이전트 스킬 400+ 큐레이션. '이 프로젝트에 넣을 스킬' 추천 소스 | ★34, push 2026-08 |
| [roboco-io/plugins](https://github.com/roboco-io/plugins) | code | KR | 스킬+커맨드+에이전트+훅을 묶은 Claude Code 플러그인 마켓플레이스(한국어). 하네스 배포 단위 설계 참고 | ★21, push 2026-07 |

## 진행 추적·데일리 브리핑 (6)

| 이름 | kind | 지역 | 요약 | 활성·신호 |
|------|------|------|------|----------|
| [claude-code-telegram](https://github.com/RichardAtCT/claude-code-telegram) | code | US | Claude Code를 텔레그램으로 원격 조작 + cron 스케줄러로 반복 작업(데일리 헬스체크) → 텔레그램 보고. **스케줄+텔레그램 인프라를 통째로 참고** | ★2,759, push 2026-03 |
| [nogataka/ai-secretary](https://github.com/nogataka/ai-secretary) | code | JP | Claude Code AI 비서 템플릿 — PARA 프로젝트 관리·아침 브리핑('오늘의 포인트/태스크/판단 대기' 섹션). **ohmyPM과 가장 근접한 아키텍처 선례** | ★5, 2026-03 공개 (커밋 1개) |
| [AI-Codereview-Gitlab](https://github.com/sunmh207/AI-Codereview-Gitlab) | code | CN | 커밋 활동 요약 → 일보(日报) 생성 → IM 푸시 파이프라인의 완결 선례. 대시보드·Docker 포함 | ★1,818, push 2026-07 |
| [gitstandup (MCP)](https://github.com/muba00/gitstandup) | code | US | 멀티 repo 커밋 수집을 **MCP 서버로 노출** — Claude Code 기반인 ohmyPM에 가장 맞는 아키텍처 | ★5, push 2026-02 |
| [SmartTodo](https://github.com/LiZeC123/SmartTodo) | code | CN | 할 일 영향 요인 점수화 + 생성 시각 합산으로 **우선순위 자동 산정** — 알고리즘 문서화됨 | ★22, push 2026-08 |
| [k-skill](https://github.com/NomaDamas/k-skill) | code | KR | '에이전트를 한국인으로' 스킬 모음집 — 한국어 에이전트 스킬 작성 관례 참고 | ★7,257, push 2026-08 매우 활발 |

## 문서·위키 건강 관리 (5)

| 이름 | kind | 지역 | 요약 | 활성·신호 |
|------|------|------|------|----------|
| [lychee](https://github.com/lycheeverse/lychee) | tool | US | Rust 고속 링크 체커 — 깨진 링크 점검 엔진으로 **그대로 채택 가능** (CLI+GitHub Action) | ★3,846, push 2026-08, 사실상 표준 |
| [Vale](https://vale.sh/) | tool | US | 커스터마이즈 가능한 prose 린터 — 용어 일관성·문체 규칙. Datadog·GitLab 등 90팀 채택 | ★5.6K, 활발 |
| [doc-drift](https://github.com/jbrockSTL/doc-drift) | code | US | PR diff + docs를 **LLM으로 대조해 stale 문서 검출** — 접근 방식 참고 (실체는 스크립트 1개) | ★0, 2026-01 스냅샷 |
| [phpstan-todo-by](https://github.com/staabm/phpstan-todo-by) | code | US | **만료되는 TODO** — 날짜·조건 지나면 정적분석 에러. 보류 안건 재부상 규칙의 구현 레퍼런스 | ★205, push 2026-08 |
| [TODO to Issue Action](https://github.com/marketplace/actions/todo-to-issue) | tool | US | TODO/FIXME 주석 → 이슈 자동 생성·종료. TODO를 브리핑 안건으로 승격시키는 패턴 | ★800, 릴리스 2026-07 |

## 자율 업무 실행 (5)

| 이름 | kind | 지역 | 요약 | 활성·신호 |
|------|------|------|------|----------|
| [GitHub Agentic Workflows (gh-aw)](https://github.com/github/gh-aw) | tool | US | Markdown+frontmatter → 하드닝된 Actions 워크플로 컴파일, cron 실행. **스케줄+권한 제한+safe outputs 패턴의 핵심 레퍼런스** | ★4,966, GitHub 공식, push 2026-08 |
| [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action) | code | US | 공식 액션 — cron 스케줄로 야간 유지보수 프롬프트 실행(Scheduled Maintenance 패턴 문서화) | ★8,675, 공식, 매우 활발 |
| [claude-code-showcase](https://github.com/ChrisWiles/claude-code-showcase) | code | US | 훅·스킬·에이전트·스케줄 워크플로(월간 문서 동기화, 주간 품질 수정, 격주 의존성 감사) 총망라 예제 | ★6,027, 단 2026-01 일회성 스냅샷 |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code/blob/main/README-zh.md) | code | CN | Claude Code류 에이전트 바닥부터 구현 교육 리포 — **self-scheduling(cron 자가 예약)** 장 포함, 자매 리포 claw0(heartbeat+cron) | ★74.8K, push 2026-08 |
| [itops-agent-platform](https://github.com/qinshihu/itops-agent-platform) | code | CN | IT 운영 멀티 에이전트 — 감지→진단→**인간 승인 게이트**→실행→검증 폐루프. 자율 실행 안전장치 모델 (리팩토링 과도기) | ★885, 활발 |

## 드랍 (사유 기록 — 재검토 방지)

<details markdown="1">
<summary>검수에서 드랍한 7건 (2026-08-21)</summary>

| 이름 | 축 | 드랍 사유 |
|------|-----|----------|
| [depromeet/daily-scrum-slack-bot](https://github.com/depromeet/daily-scrum-slack-bot) | 브리핑 | 2022년 2KB 스크립트, 크론+메시지 예시 이상의 참고 가치 없음 |
| [yurencloud/daily](https://github.com/yurencloud/daily) | 브리핑 | 2019년 방치 ★5 — 일보/주보 컨셉은 다른 자료로 충분 |
| [GitRecap](https://github.com/aaaaorg/gitrecap) | 브리핑 | archived 스냅샷 — 커밋→LLM 요약 구조는 gitstandup(MCP)이 대신 커버 |
| [py-hanspell](https://github.com/ssut/py-hanspell) | 문서 | 네이버 passportKey 변경으로 현재 동작 안 함, 포크 필요 |
| [Hangul-MCP](https://github.com/Alfex4936/Hangul-MCP) | 문서 | 14개월 정체 ★2 — 맞춤법 점검이 필요해지면 그때 재탐색 |
| [mmoollee101-lab/remote-cli](https://github.com/mmoollee101-lab/remote-cli) | 자율 실행 | ★0 개인 프로젝트, 텔레그램 채널은 Project Odin 기지 영역과 중복 |
| [claude-code-scheduler](https://github.com/biosphere-labs/claude-code-scheduler) | 자율 실행 | ★0 하루짜리 개인 도구 — '구독 기반 headless 스케줄' 아이디어만 기억 |

</details>

## 미검증 94건 (검증 상한 초과로 잘림)

검증 에이전트를 거치지 않은 후보들 — URL 실재·활성 여부 미확인. 펼쳐서 구제(→검증 승격)하거나 버릴 수 있다.

<details markdown="1">
<summary>하네스 점검 — 미검증 23건</summary>

| 이름 | 지역 | 한 줄 |
|------|------|------|
| [효율적인 CLAUDE.md 관리·컨텍스트 최적화 (한컴테크)](https://tech.hancom.com/claude-md-context-optimization/) | KR | 컨텍스트 부패(context rot) 현상과 JIT 전략·메모리 계층 — 부패 판단 기준 참고 |
| [Claude Code 컨텍스트 최적화 가이드 (InfoGrab)](https://insight.infograb.net/blog/2026/01/14/claudecode-context/) | KR | rules 충돌·노후 지시 정기 검토 실무 가이드 |
| [Claude Code Hooks — 코드로 정책 강제 (InfoGrab)](https://insight.infograb.net/blog/2026/03/18/claude-code-hooks/) | KR | 훅 정책 강제 패턴 + 중앙 정책 서버·알림 연동 |
| [Claude Code 리뷰 자동화 — 실패 학습 루프 (Mimul)](https://www.mimul.com/blog/claude-code-review/) | KR | 실패 사례를 CLAUDE.md에 되먹임하는 하네스 갱신 루프 |
| [CLAUDE.md 4가지 역할 해부 (YouTube)](https://www.youtube.com/watch?v=8-gia4oJYAo) | KR | CLAUDE.md 계층(글로벌/프로젝트/로컬)별 역할 강의 |
| [CLAUDE.md 작성 가이드 (Dale Seo)](https://daleseo.com/claude-code-claude-md/) | KR | 최소 규칙·지속 다듬기 원칙 — lint 기준 참고 |
| [Ask HN: CLAUDE.md/AGENTS.md 유지보수 아직 하나?](https://news.ycombinator.com/item?id=48160604) | US | 실무자들의 유지 전략·포기 사유 — **페인 포인트 1차 수요 근거** |
| [Harness engineering (martinfowler.com)](https://martinfowler.com/articles/harness-engineering.html) | US | 하네스 엔지니어링 개론 — '좋은 하네스' 이론 베이스라인 |
| [awesome-harness-engineering](https://github.com/walkinglabs/awesome-harness-engineering) | US | 하네스 도구·가이드 큐레이션 허브 |
| [Claude Code memory 튜토리얼 (YouTube)](https://www.youtube.com/watch?v=bMe8hokixKE) | US | CLAUDE.md 메모리 구성 실사용 워크플로 |
| [cclint](https://github.com/felixgeelhaar/cclint) | CN | CLAUDE.md 검증·최적화 TypeScript linter |
| [skill-lint](https://github.com/himself65/skill-lint) | CN | SKILL.md 규격(이름·description·frontmatter) 검증 linter |
| [claude-code-config-manage-gui](https://github.com/ronghuaxueleng/claude-code-config-manage-gui) | CN | Windows용 Claude Code 설정 GUI — 동일 OS 환경 구현 사례 |
| [万字详解 CLAUDE.md 最佳实践 (知乎)](https://zhuanlan.zhihu.com/p/2055667183229969105) | CN | CLAUDE.md 내용·분할(.claude/rules/) 기준 장문 가이드 |
| [AGENTS.md 深度解析 (知乎)](https://zhuanlan.zhihu.com/p/2046987814852638252) | CN | '설정 문서를 코드와 함께 갱신' 원칙 — 부패 감지 트리거 설계 |
| [Claude Code 从 0 到 1 全攻略 (bilibili)](https://www.bilibili.com/video/BV14rzQB9EJj/) | CN | MCP·서브에이전트·스킬·훅 전반 튜토리얼 |
| [agentlint — .claude 정적 검증 (SIOS)](https://tech-lab.sios.jp/archives/53730) | JP | .claude/ 하위 skills·commands·hooks 정적 검증 linter 제작기 |
| [agents-lint 실사용 검증기 (Qiita)](https://qiita.com/kai_kou/items/a1781faa823fac4d998c) | JP | lint 도구 오탐 처리·점수 해석 실전 교훈 |
| [CLAUDE.md 3층 구조로 83% 경량화 (Zenn, pepabo)](https://zenn.dev/pepabo/articles/claude-code-rules-skills-split) | JP | 비대 CLAUDE.md 분할 리팩토링 실측 기록 — **리팩토링 목표 구조** |
| [7가지 지시면과 컨텍스트 부채 (Zenn)](https://zenn.dev/suwash/articles/claude-code-steering-surfaces_20260622) | JP | '무엇을 어디에 두나' 판정 체크리스트 — 그대로 차용 가능 |
| [작업 환경 재점검 실천 가이드 (Zenn)](https://zenn.dev/135yshr/articles/05db71175c4746) | JP | 하네스 정기 재점검 절차 사례 |
| [chezmoi+Bats+Actions dotfiles 테스트 (shunk031)](https://github.com/shunk031/zenn-contents/blob/main/articles/testable-dotfiles-management-with-chezmoi.md) | JP | '설정도 테스트·CI로 부패 감지' 패턴 |
| [CLAUDE.md 몇 행이 정답? (YouTube Shorts)](https://www.youtube.com/shorts/JkRPOnVFgcg) | JP | CLAUDE.md 길이 임계값(~100행) 대중 가이드라인 |

</details>

<details markdown="1">
<summary>진행 추적·브리핑 — 미검증 22건</summary>

| 이름 | 지역 | 한 줄 |
|------|------|------|
| [텔레그램으로 Claude Code 부려먹기 (wikidocs)](https://wikidocs.net/blog/@hyeong/21224/) | KR | 텔레그램 롱폴링 + subprocess로 headless 실행·회신 — 구조 거의 동일 |
| [비개발자의 Daily Routine 자동화 (GPTers)](https://www.gpters.org/nocode/post/daily-routine-automation-system-PztbVeOTFP6Fe8u) | KR | Claude Code만으로 데일리 루틴 운영한 후기 |
| [GitHub API 대시보드 만들기 (Choo)](https://choo.oopy.io/f2aefdd3-b05f-42b7-8261-9a63a3fb6c72) | KR | repo 활동 데이터 수집·가공 |
| [epilande/repos](https://github.com/epilande/repos) | KR | 멀티 로컬 repo 상태 일괄 확인 인터랙티브 CLI |
| [사내 슬랙봇 앙몬드 개발기 (카카오페이)](https://tech.kakaopay.com/post/slack-angmondbot/) | KR | 정기 알림 봇이 정착하는 메시지 설계·운영 |
| [노션 AI 플래너 가이드 (시리얼)](https://sireal.co/blog/how-to/notion-ai-planner-2026-weekly-automation-guide) | KR | AI 주간 계획·리뷰 자동화 프롬프트 구성 |
| [git-standup](https://github.com/kamranahmedse/git-standup) | US | 멀티 repo 재귀 순회 '내 커밋 회상' CLI — **사실상 표준, ★7천+** |
| [gita](https://github.com/nosarthur/gita) | US | 멀티 repo 상태 나란히 보기 + 일괄 명령 (★2천+) |
| [Claude Code Scheduled Agents로 Slack 브리핑 (Medium)](https://medium.com/@yunjeongiya/automating-daily-slack-briefings-with-claude-code-scheduled-agents-b093e138cc4f) | US | **MVP 접근과 거의 동일한 선행 사례** (cron 9시 → 커밋 분석 → 브리핑) |
| [Morgen AI Planner](https://www.morgen.so/ai-planner) | US | 할 일+캘린더 → 현실적 하루 일정 자동 생성 SaaS — UX 벤치마크 |
| [24/7 AI 에이전트 + 모닝 브리핑 (YouTube)](https://www.youtube.com/watch?v=pFMDLj_ztiw) | US | 서버+cron+메모리+메신저 엔드투엔드 튜토리얼 |
| [Agent Skill로 주보 자동 생성 (博客园)](https://www.cnblogs.com/forzhaokang/p/19847939) | CN | 로컬 전체 repo 커밋 스캔 → 주보 — '스킬+스케줄, 앱 없음' 동일 아키텍처 |
| [MGit (baidu)](https://github.com/baidu/m-git) | CN | 멀티 repo 배치 명령의 안전장치 설계 |
| [일보·주보 생성기 소개 (知乎)](https://zhuanlan.zhihu.com/p/2048448939842712800) | CN | 보고서 길이·톤 조절 UX 아이디어 |
| [git 데이터 분석 도구 8종 (知乎)](https://zhuanlan.zhihu.com/p/99390582) | CN | 활동 지표·시각화 도구 후보 목록 |
| [Claude×Git 일보 자동 생성 (Qiita)](https://qiita.com/htanaka0828/items/418e76be9449fd022f28) | JP | 활동 수집 → LLM 요약 → 메신저 최소 구현 |
| [n8n GitHub+Slack 개발 일보 (Zenn)](https://zenn.dev/webook/articles/73f4af99d86286) | JP | 일보 데이터 흐름 노코드 설계 |
| [커밋+Slack 일보 Go CLI (Qiita)](https://qiita.com/MasatoraAtarashi/items/863b004eab96367bd9fb) | JP | 멀티 repo 하루 활동 수집 CLI |
| [Claude Code×Gmail×Slack 아침 브리핑 (note)](https://note.com/nobu_0215/n/n7e711b1737c9) | JP | 발송 시각·브리핑 포맷(중요 메일 톱3/일정/태스크) 설계 |
| [Claude Code 스케줄러 키우기 (Zenn, dely)](https://zenn.dev/dely_jp/articles/cf19634b63015b) | JP | 정기 태스크를 스케줄러에 늘려가는 기업 운영 노하우 |
| [Claude Code 정기 실행 수단 비교 (Zenn)](https://zenn.dev/linkedge/articles/claude-code-scheduled-execution) | JP | **로컬 cron vs Routines vs 클라우드 비교** — 스케줄 방식 선택 자료 |
| [GitHub Issue 일보 자동화 (soudai)](https://soudai.hatenablog.com/entry/2023/11/02/215019) | JP | 브리핑을 '매일 자동 생성 이슈'로 남기는 최경량 패턴 |

</details>

<details markdown="1">
<summary>문서·위키 건강 — 미검증 25건</summary>

| 이름 | 지역 | 한 줄 |
|------|------|------|
| [당근마켓 digital-garden](https://github.com/daangn/digital-garden) | KR | 지식을 정원처럼 가꾸는 운영 규칙 국내 사례 |
| [LINE 문서 엔지니어링](https://engineering.linecorp.com/ko/blog/document-engineering-api-documentation) | KR | 문서를 코드처럼 관리·검증하는 국내 대표 사례 |
| [토스페이먼츠 테크니컬 라이터](https://toss.tech/article/tech-writer-1) | KR | 사람 라이터의 유지보수 업무 목록 = 자동화할 태스크 원형 |
| [GitLab Vale 문서 테스트 (한글)](https://gitlab-docs.infograb.net/ee/development/documentation/testing/vale.html) | KR | Vale CI 구성 구체 예시 |
| [Docs as Code 한국어 해설](https://medium.com/@Danpatpang/docs-as-code-298802a691d1) | KR | docs-as-code 기본 프레임 |
| [LY Technical Documentation Day 후기](https://techblog.lycorp.co.jp/ko/internal-event-for-technical-writing-and-document-engineering) | KR | 사내 위키 관리 조직 노하우 |
| [Fiberplane drift — 문서 부패 linter](https://fiberplane.com/blog/drift-documentation-linter/) | US | **문서-코드 앵커링** — LLM 없이 결정론적 stale 판정 |
| [Ask HN: 낡은 문서 문제](https://news.ycombinator.com/item?id=43690841) | US | 문서 부패 실패 패턴·성공 관행 수집 |
| [digital-gardeners (Maggie Appleton)](https://github.com/MaggieAppleton/digital-gardeners) | US | gardening 철학(성숙도 단계·가지치기) 대표 큐레이션 |
| [lint-md](https://github.com/lint-md/lint-md) | CN | 중국어 Markdown AST 기반 lint CLI |
| [AutoCorrect](https://github.com/huacnlee/autocorrect) | CN | CJK-영문 혼용 공백·문장부호 **자동 교정**(diff 제안) Rust linter |
| [zhlint](https://github.com/zhlint-project) | CN | 언어·프로젝트 컨벤션 커스텀 lint 사례 |
| [AI 코드 문서 도구 비교 (CSDN)](https://blog.csdn.net/adcwa/article/details/156169016) | CN | 코드-문서 동기화 도구 지형(Swimm 등) |
| [Docs Like Code 심층 해설 (知乎)](https://zhuanlan.zhihu.com/p/364911980) | CN | docs-as-code 방법론 근거 |
| [文档代码化 (Phodal)](https://cloud-dev.phodal.com/docs/as-code/document-as-code.html) | CN | 문서 과시(stale) 문제의 도구·프로세스 해법 |
| [oldwinter/knowledge-garden](https://github.com/oldwinter/knowledge-garden) | CN | Obsidian 이중 링크 개인 디지털 가든 실사례 |
| [markdownlint 입문·심화 (중국어)](https://lruihao.cn/posts/markdownlint/) | CN | markdownlint+AutoCorrect 상시 검사 훅 레시피 |
| [lychee-action](https://github.com/lycheeverse/lychee-action) | JP | lychee CI판 — 깨진 링크 발견 시 이슈 자동 생성 |
| [gh-aw 문서 갱신 누락 자동 PR PoC](https://thundermiracle.com/blog/2026-02-11-gh-aw-docs-sync) | JP | **코드 변경 → 문서 stale 감지 → 자동 갱신 PR/noop** 최신 사례 |
| [문서가 썩는 3대 원인 (note)](https://note.com/agexworks/n/nefc7e1647094) | JP | 부패 원인 분류 + doc-lint.yml 운용 |
| [GitHub Wiki 자동 동기화 (Zenn)](https://zenn.dev/bltsdc/articles/cf65b441c62908) | JP | 장기 미갱신 문서 감지 → 리뷰 촉구 메커니즘 |
| [textlint 기업 사례·룰 모음 (Zenn)](https://zenn.dev/kgsi/articles/a88273d293abe07c5acb) | JP | 프로젝트별 lint 룰셋 커스터마이즈 카탈로그 |
| [PR 시 TODO·FIXME 자동 검지 (Zenn, dely)](https://zenn.dev/dely_jp/articles/c7668aa6422b6e) | JP | 묵은 TODO 검출 트리거 설계 |
| [TODO→issue 승격 Go 도구 (Qiita)](https://qiita.com/masibw/items/39d81c64b871bb836027) | JP | TODO를 보이는 작업 항목으로 승격 |
| [AI 문서 주도 개발 (Zenn)](https://zenn.dev/koyabase/articles/5b6e871c5c9244) | JP | Claude Code 스킬로 문서 SSoT 정합성 유지 — 스킬 설계 레벨 근접 참고 |

</details>

<details markdown="1">
<summary>자율 업무 실행 — 미검증 24건</summary>

| 이름 | 지역 | 한 줄 |
|------|------|------|
| [GeekNews — Claude Code Routines 토론](https://news.hada.io/topic?id=27690) | KR | 클라우드 cron 실행 기능 소개·커뮤니티 반응 |
| [Claude Code GitHub Actions 사용법 (DaleSeo)](https://daleseo.com/claude-code-action/) | KR | 이슈→수정→PR 자동화 한국어 가이드 |
| [텔레그램으로 클로드코드 조종하기 (브런치)](https://brunch.co.kr/@9cf629983e9d473/33) | KR | 자율 실행(에러 자가 복구 후 결과만 보고) 개인 실전기 |
| [Renovate 도입 가이드 (Joe Brothers)](https://blog.joe-brothers.com/using-renovate/) | KR | **minor/patch 자동, major 수동** — 자동/수동 경계선 설계 |
| [Renovate 의존성 자동화 후기 (JHyeok)](https://jhyeok.com/renovate-bot/) | KR | 방치→breaking 누적 문제와 봇 도입 효과 |
| [회사 업무 80% 자동화 (YouTube)](https://www.youtube.com/watch?v=Gx6DmUrmg6g) | KR | 자율 실행 범위·위임 패턴 국내 영상 |
| [Claude Code Routines (공식)](https://claude.com/blog/introducing-routines-in-claude-code) | US | **클라우드 cron·API·GitHub 이벤트 트리거 공식 기능** — 실행 기반 1순위 검토 대상 |
| [Renovate](https://github.com/renovatebot/renovate) | US | 스케줄 유지보수 봇의 원형 — 자동 머지 조건·스케줄 윈도·그룹핑 정책 |
| [OpenHands GitHub Resolver](https://www.openhands.dev/blog/open-source-coding-agents-in-your-github-fixing-your-issues) | US | 라벨 트리거 → 분석·수정·테스트·PR 완결 루프 오픈소스 |
| [야간 무인 에이전트 운영기 (petieclark)](https://blog.petieclark.com/i-do-run-ai-agents-overnight-heres-what-actually-matters/) | US | **측정 가능한 성공 기준·파일 스코프 제한·되돌릴 수 있는 작업만** — 가드레일 원칙 |
| [Claude Code 24/7 직원 만들기 (YouTube)](https://www.youtube.com/watch?v=xIjUdWMgzbM) | US | routines 출시 직후 무인 운용 튜토리얼 |
| [Claude Code 밤새 무인 실행 가이드 (唐巧)](https://blog.devtang.com/2026/04/15/claude-code-autonomous-guide-zh/) | CN | headless·권한·루프 모드·장시간 세션 안전장치 |
| [Claude 클라우드 정시 작업 해설 (知乎)](https://zhuanlan.zhihu.com/p/2019834556744737825) | CN | Routines 3종 트리거 구조 해설 |
| [OpenClaw 정시 작업 튜토리얼 (知乎)](https://zhuanlan.zhihu.com/p/2015384869325275312) | CN | **Heartbeat(주기 점검)+Cron(정시) 이중 스케줄** + 워크스페이스 구조 — 이식 후보 패턴 |
| [OpenClaw 정시 작업 종합 (Aliyun)](https://developer.aliyun.com/article/1718611) | CN | 시나리오별(일보·모니터링·주간 요약) cron 편성 사례 |
| [/schedule·Routines·/loop 3방식 비교 (claudecode.xyz)](https://www.claudecode.xyz/articles/claude-code-scheduleroutines-loop-mox268ua) | CN | **클라우드는 로컬 파일 접근 불가** 등 제약 비교 — 핵심 판단 자료 |
| [Renovate 자동 머지 설정기 (chensoul)](https://blog.chensoul.cc/posts/2025/09/28/config-renovate-in-github/) | CN | 조건부 자동 머지 설정 패턴 |
| [Claude Code cron 매일 아침 실행 (Zenn)](https://zenn.dev/techquant/articles/claude-code-cron-automation) | JP | cron 환경변수 등 **실운용 함정** 포함 구축기 |
| [claude -p headless 실전 패턴집 (Qiita)](https://qiita.com/takish/items/ddb73b8473081fc969b9) | JP | headless 호출·구조화 출력·fan-out 구현 패턴 |
| [Claude Code×Actions 자율 에이전트 함정 (Qiita)](https://qiita.com/Gaakuu/items/532e133838786f185acf) | JP | 무인 에이전트 배드 케이스·가드레일용 실패 사례 |
| [Issue→PR 작성·리뷰·수정 자동화 (DevelopersIO)](https://dev.classmethod.jp/articles/issue-to-pr-review-fixes-automation-claude-code-github-actions/) | JP | 완전 자동 파이프라인 단계별 검증 글 |
| [Renovate 94% 자동화 (Qiita)](https://qiita.com/ham0215/items/5f6ec0623448154feb19) | JP | 자동 머지 조건 설계의 정량 성과 사례 |
| [주말 Renovate 운용법 (Qiita)](https://qiita.com/yamadashy/items/539f3da34f955a0b466a) | JP | **개인 프로젝트 다수**에 맞는 스케줄드 유지보수 노하우 |
| [Devin 도입 2.5개월 177 PR (Zenn)](https://zenn.dev/levtech/articles/9c869303820844) | JP | 자율 에이전트에 맡길 업무 분류 기준(소규모 버그·리팩토링·테스트) |

</details>
