---
name: llmwiki
description: 프로젝트 docs/를 LLM이 유지하는 위키로 만든다(카파시 LLM 위키 패턴). 발동 — 새 프로젝트 docs/ 초기화·위키 하네스 설치(init, 킥오프 마무리 포함); "docs 정리/점검", 위키 건강 점검·다이어트(lint). 상시 기록과 보류 안건 재부상은 스킬 발동이 아니라 init이 설치하는 CLAUDE.md 규칙+훅이 담당한다.
---

# llmwiki — LLM이 유지하는 프로젝트 위키

매번 원본을 다시 뒤지는 대신, 위키가 지식을 누적한다.
역할 분담: **위키는 LLM이 쓰고 사람은 읽는다. 기록은 작업의 부산물로 쌓인다 — 명령을 기다리는 순간 유지가 끊긴다.**

그래서 이 스킬은 두 번만 발동한다: **init**(위키와 상시 기록 하네스를 까는 설치)과 **lint**(주기 점검).
일상의 기록(ingest)·조회(query)·보류 안건 재부상은 init이 프로젝트에 심는 CLAUDE.md 스키마 블록과 훅이 알아서 굴린다.

## 구조

```
docs/
  raw/         원본 — 회의록·외부 자료·스크린샷. 들어온 뒤에는 그대로 둔다
  *.md         위키 페이지 — LLM이 생성·갱신
  index.md     전 페이지 목록 + 한 줄 요약, 카테고리별
  log.md       append-only 작업 기록: `## [YYYY-MM-DD] <작업> | <제목>`
  status.md    작업 보드 — 진행 중 / 미해결 / 최근 완료. 착수 전 먼저 읽는다
  mistakes.md  실수 연대기 — 날짜·내용·비용·항체(재발 방지 장치)·반복 패턴
  pending.md   보류 안건 대장: | 안건 | 보류 이유 | 재검토 시점(날짜 또는 조건) | 배경 링크 |
  conventions-wiki.md  위키 상세 규약 — raw 보존·asserted/inferred·다이어트 기준 (필요할 때 로드)
.claude/hooks/
  llmwiki-sessionstart.ps1  재검토 시점 도래한 보류 안건을 세션 시작 때 재부상시키는 훅
                            (Windows용 — macOS/Linux는 .sh 버전, 아래 init 3단계)
```

**상시 지시 예산**: 이 스킬이 호스트 CLAUDE.md에 남기는 블록은 **10줄 이하**다. 모든 상시 지시는
매 턴 주의력을 지불한다 — 매 턴 필요한 규칙만 블록에, 상세는 conventions-wiki.md(검색 가능)로.

(Stop 훅으로 매 턴 기록을 강제하는 방식은 2026-08-19 폐기 — 턴의 마지막 사고가 작업 검증이 아니라
기록 점검으로 끝나 작업 품질이 떨어졌다. 기록은 CLAUDE.md의 "작업 매듭" 규칙이 담당한다.)

## init — 위키와 하네스 설치

**문서 체계가 이미 있는 프로젝트면 표준 구조를 강요하지 않는다** — 인덱스·실수 장부·작업 보드 같은
기존 문서가 있으면 스키마 블록에서 그 문서들로 역할을 매핑하고, 없는 조각(log·pending·raw·훅)만
신설한다. 같은 역할의 문서를 두 개 만들면 단일 출처가 깨진다.
(예: 인덱스 역할을 CLAUDE.md의 문서 표가, 실수 장부를 mistakes.md가, 작업 보드를 status.md가
이미 하고 있으면 새로 만들지 말고 그 문서들로 매핑한다)

1. `docs/raw/` 생성, `index.md`·`log.md`·`status.md`·`mistakes.md`·`pending.md`를 빈 뼈대로 생성 (기존 문서가 대신하는 것은 건너뛴다). [conventions-wiki-template.md](conventions-wiki-template.md)를 `docs/conventions-wiki.md`로 복사한다
2. [schema-template.md](schema-template.md)의 블록을 프로젝트 CLAUDE.md에 추가한다 — 10줄 예산을 지킨다. 이 블록이 상시 기록·보류 규칙의 본체고, 상세는 conventions-wiki.md가 소유한다
3. **OS에 맞는** 훅 스크립트를 프로젝트 `.claude/hooks/`에 복사하고 `.claude/settings.json`에 등록한다 — Windows는 [sessionstart-hook.ps1](sessionstart-hook.ps1)을 `llmwiki-sessionstart.ps1`로, macOS/Linux는 [sessionstart-hook.sh](sessionstart-hook.sh)를 `llmwiki-sessionstart.sh`로 (두 스크립트는 동일 동작):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/llmwiki-sessionstart.ps1",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

macOS/Linux는 위 `command`만 바꾼다: `"command": "bash .claude/hooks/llmwiki-sessionstart.sh"`

4. `docs/`에 기존 문서가 있으면 각각을 위키 페이지로 소화하고 index에 올린다

완료 기준: `index.md`·`log.md`·`pending.md`·훅 스크립트가 존재하고, 프로젝트 CLAUDE.md에 스키마 블록, settings.json에 SessionStart 훅 등록, 기존 문서 전부가 index에 올라 있다.

## lint — 주기 점검·다이어트

아래를 전부 훑고, 발견 항목마다 처리(수정 / 플래그 / 사용자 확인)까지 끝내야 완료:

- 페이지 간 모순 — 기존 `⚠️ 모순` 플래그 해소 포함
- 고아 페이지 — 어디서도 링크되지 않는 페이지는 링크를 걸거나 아카이브
- `index.md`와 실제 파일의 불일치, 깨진 링크
- 중복 페이지 통합
- **보류 안건 점검** — `pending.md`의 조건형 안건(날짜 없는 것)은 조건 충족 여부를 확인하고,
  충족됐으면 재검토 미팅을 제안한다. 날짜형은 SessionStart 훅이 잡지만 여기서도 이중 확인
- **작업 보드 정리** — `status.md`의 오래된 완료 항목을 지우고, 움직임 없는 진행 항목은
  실제로 살아 있는지 사용자에게 확인한다
- **살아있는 것만 남긴다 (다이어트)** — 반영이 끝난 결정·검토 페이지는 흡수처(규칙·스킬·코드)를
  확인한 뒤 **삭제**하고 출처 장부(provenance)나 log에 한 줄만 남긴다 — 경위는 git 이력이 보존한다.
  실험·조사 계열은 종료 시 결과 1장으로 접는다. 위키는 쓰기만 하면 단조 증가한다 —
  살아있어야 하는 것은 status·pending(각 한 화면 이내)과 버그 항체뿐이다
- 규모 관리 — `index.md`가 ~100줄을 넘으면 카테고리별 서브 인덱스(`index-<카테고리>.md`)로 분할.
  소화가 끝난 오래된 원본은 `raw/archive/`로 이동하고 페이지의 출처 경로를 갱신
- **기계 점검 우선** — 프로젝트에 doctor 스크립트(예: kickoff_pack `pack-doctor.ps1`)가 있으면
  먼저 실행하고 그 결과부터 처리한다. 깨진 링크·고아 페이지·상시 지시 예산 초과 같은 검사 가능한
  항목은 눈이 아니라 스크립트가 잡는다 — 반복 실패는 지침이 아니라 스크립트로 승격
- **CLAUDE.md 위키 블록 예산 점검** — 호스트 CLAUDE.md의 위키 블록이 10줄을 넘게 자랐으면
  초과분을 conventions-wiki.md로 내리고 블록을 되돌린다

lint를 마치면 `log.md`에 `## [날짜] lint | <처리 요약>` 한 줄을 남긴다.
