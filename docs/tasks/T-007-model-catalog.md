# T-007 모델 동향 전문가(r2) 구현

- 상태: 구현·자동 검증·실제 4/4 소스 수집 완료. 제출(submit) 완료, pl 판정 대기
- 승인 spec: `.git/ohmypm/tasks/T-007/r2/spec.md` (digest 21f15cd0…9)
- 작성: work, 2026-09-28
- pl 역할 대행: pl(Codex)이 사용량 한도로 막혀, 사용자 지시로 main 세션(term_a8d11c0f…)이
  코드 검토·기준별 검증·verdict를 대행한다(`.git/ohmypm/tasks/T-007/r2/user-pl-exception-decision.md`).
  이 work는 그 세션의 검증을 기다리지 않고 submit까지 마친다.

## 1. 구현 요약

`src/cc/model_catalog.py`가 공식 출처 4개(Claude 모델·릴리스, Codex 모델·changelog)를 httpx로
직접 수집해 `docs/experts/models.md`를 유지한다. LLM(`claude -p`, 도구 없음)은 마지막 반영본과
달라진 절만 받아 구조화 JSON(name/날짜/diff/impact/impact_type/source_url/related)으로 요약하고,
코드가 필수 필드·`https://` 출처를 검증한 뒤 임시 파일 + `os.replace` 원자적 교체로 위키를 쓴다.
검증 실패 시 반영하지 않고 마지막 정상 위키를 보존한다.

상태(소스별 확인/반영 시각·해시, 최근 변화, 월별 요약)는 git 미추적 `data/model_updates/`에만
남는다. 배치 id(`hash(source+applied_hash)`)로 중복 반영을 막아 중단 후 재실행에도 안전하다.
같은 로컬 파일 잠금(`data/model_updates/.lock`, O_CREAT|O_EXCL, 10분 stale 회수)으로
CLI/API/collect_all 쓰기를 직렬화한다.

`src/cc/expert.py`: `models` 도메인 등록. `collect_all()`이 모델동향을 먼저 갱신한 뒤 나머지
도메인을 수집하고, `collect_knowledge()`/`consult()`는 다른 도메인(models 제외) 호출 시
`[최신 모델 동향 요약]` 블록을 기존 위키 앞에 주입한다(상태 없으면 무주입 — 기존 동작 보존).

`src/web/routers/api.py`: `POST /api/experts/models/collect`가 `collect_all_sources()`를 호출.
`src/web/routers/pages.py`: 위키 렌더러(`md()`)에 안전한 링크 지원 추가(`https://` 외부,
`#/experts/...` 내부만 `<a>`로, 그 외는 텍스트만 — 기존 escape 유지, XSS 방지).
`scripts/collect_models.py`: CLI(`--fetch-only`, `--source`).

## 2. 완료 기준별 검증

| ID | 결과 | 근거 |
|---|---|---|
| C1 | 통과 | `tests/test_model_catalog.py::TestSnapshot` — 동일 본문 재실행 LLM 0회, nav/script 변경 무시 |
| C2 | 통과(대역+실제) | `TestChange` + 실제: claude-models 실제 수집·실제 LLM 1회로 5건 생성, 출처·asserted 태그 포함(§4) |
| C3 | 통과 | `TestRetry` — fetch-only→실행, LLM 실패→재시도, 동일자 복수 변경, 24,000자 분할 2회 호출 모두 누락/중복 없음 |
| C4 | 통과 | `TestFailure` — 네트워크/추출/빈 본문 오류, 동시 실행(스레드 4개) state.json 무결성, 위키 쓰기 중단 시뮬레이션에서 원본 보존 |
| C5 | 통과(실제) | 실제 4/4 소스 모두 반영 완료(§4) — 최근 변화 20건, 전부 출처 링크·asserted/inferred/none 태그 포함. 원문 대조는 pl 몫 |
| C6 | 통과(실제, 브라우저 제외) | 독립 포트(64103)에서 서버 기동, `/api/experts`에 models 노출, 실제 질문 1건 실답 확인(§4) — 실제 브라우저 클릭 검수만 pl 몫 |
| C7 | 통과 | `TestInject` — 상태 없으면 프롬프트 불변, 있으면 harness/llm-apps 수집·자문 입력에 확인시각+변경요약 주입, models 자신은 미주입 |
| C8 | 통과 | `uv run --no-sync pytest -q` 78 passed(기존 56+신규 22). ruff — 이 작업이 건드린 파일은 0 오류(저장소 기존 위반 246건은 무관 파일, 손대지 않음). 새 의존성 없음(httpx 기존) |

## 3. 소유 경로 준수

`src/cc/model_catalog.py`(신규), `src/cc/expert.py`, `src/cc/prompts.py`,
`prompts/model_catalog_update.md`(신규), `src/web/routers/api.py`, `src/web/routers/pages.py`,
`scripts/collect_models.py`(신규), `tests/test_model_catalog.py`(신규),
`docs/tasks/T-007-model-catalog.md`(이 문서) — spec §7 소유 경로와 정확히 일치.

## 4. 실제 수집·자문 증거 (2026-09-28, work 환경)

- `uv run --no-sync python scripts/collect_models.py --fetch-only` — 4소스 전부 실제 httpx 수집 성공
  (claude 두 문서·codex models.md·codex changelog HTML 추출 모두 200/추출 성공).
- `--source claude-models` 실제 LLM 실행 — 5건 생성, 전부 `[asserted]`(원문이 직접 밝힌 사실),
  출처 링크 `https://platform.claude.com/docs/en/models/overview.md` 정확. `docs/experts/models.md`에
  반영 확인.
- `--source codex-models` 실제 LLM 실행 — 6건 생성, 반영 확인.
- `--source claude-releases` 첫 실행은 90일 기준선 필터 후 청크 처리 중 한 청크가 LLM 검증
  실패(`llm_failed`) → 코드가 반영을 보류하고 기존 위키 보존(설계대로 동작). **재실행**(코드
  변경 없이 동일 명령 재호출)에서 같은 diff를 재시도해 성공 — 재시도 안전성(C3)이 실제
  사례로도 확인됐다.
- `--source codex-changelog` 실제 LLM 실행 — 90일 필터로 청크 1개까지 줄어 1회 호출로 반영 완료.
- 4/4 소스 반영 후 `--fetch-only` 재실행 — 전부 `changed=False, llm_called=False`(불필요한 LLM
  호출 없음, C1 실제 확인). 최종 `docs/experts/models.md` 44,472자, 최근 변화 20건.
- 독립 검증 서버(127.0.0.1:64103, 운영 8123 미교체)에서 `/api/experts`에 `models` 도메인 노출,
  `/api/experts/models/wiki` 실제 내용 확인, `/api/experts/models/ask`에 실제 질문
  "Claude Opus 5.5의 기본 effort는 뭐야?" → 위키 근거 기반 정답("medium", 출처 링크 포함) 확인.

## 5. 검증·머지 (2026-09-28, pl 대행 세션)

- verdict 통과(기준 8개 전부 pass, 증거 `.git/ohmypm/tasks/T-007/r2/implementation/pl-evidence/`),
  main ff 머지(b7c7b9f), 워크트리 회수. 자동 check 1차는 Windows 경로 길이(하네스 TMP 깊이)로
  실패 → `LongPathsEnabled=1` 후 2차 전부 통과. 상세는 log 09-28.

## 6. 후속 R-010 — 벤더별 탭 분리·모델별 상세·플랫폼 제외·미수집 탭 제거 (2026-09-28)

사용자 피드백(원문 `.git/ohmypm/requests/R-010/user-direct-exception.md`): "하나로 퉁 치지 말고
각 모델별로", "모델별로 더 디테일하게 — 어떻게 쓰는지·하네스를 어떻게 바꿔야 하는지",
"모델과 무관한 플랫폼·API는 왜 수집했나", "수집하지 않은 탭들은 버려". pl(Codex) 한도로
이 세션이 직접 구현.

**바뀐 것**
- 탭(도메인)이 벤더별 둘: `models-claude`(Claude 모델 동향)·`models-codex`(Codex 모델 동향).
  각 벤더는 자기 출처(2개씩)만 수집하고 상태 `data/model_updates/<vendor>/`·위키
  `docs/experts/models-<vendor>.md`를 따로 갖는다. `VENDORS` 한 항목 추가로 새 벤더 확장.
- 위키는 **모델별 절**: 개요 → 스펙(API ID·가격·컨텍스트·추론 설정·컷오프·제공 범위·은퇴) →
  잘 쓰는 법 → 하네스 조정 → 주의 → 변화 이력(모델별 최근 12건, 초과분은 한 줄 요약).
  라인업 전체 정책은 '라인업 공통' 절. 모델 프로필은 바뀐 모델마다 LLM 1회
  (`prompts/model_profile.md`: 원문 발췌 + 누적 변경 기록 → 상세 JSON, 코드 검증).
- 변경 항목 JSON에 `model`(정식 이름)·`usage_tips[]`·`harness_changes[]` 추가. 프롬프트가
  **모델과 무관한 플랫폼·API·SDK·앱 기능은 담지 않도록** 지시하고, `model`이 빈 항목은
  코드가 배치째 거부한다.
- 첫 수집 90일 기준선이 영문 월 이름 날짜("September 24, 2026")를 못 읽어 릴리스 노트 전체
  이력이 들어오던 결함 수정(`_parse_date`) — 날짜 없는 하위 절은 직전 날짜를 물려받는다.
- 전문가 명부에서 한 번도 수집되지 않은 4개(하네스·LLM 앱·프로덕트·디자인) 제거. 명부는
  `VENDORS`에서 자동 생성. 담당 전문가(전문가개업) 자문에는 벤더별 동향 요약을 주입.
- 기존 단일 위키·상태는 `data/model_updates/_archive-20260928-r2/`에 보관하고 재수집.

**검증**: `tests/test_model_catalog.py` 28개(snapshot/change/retry/profile/failure/vendor/inject/parse)
통과, ruff 신규·수정 파일 0오류(기존 위반 제외). 실제 재수집 결과는 log 09-28.
