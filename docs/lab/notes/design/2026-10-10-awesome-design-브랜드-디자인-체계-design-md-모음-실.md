# Awesome Design(DESIGN.md 모음) 평가와 ohmyPM 쓸모

기준 2026-10-10 · 핵심 근거: [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md), [Google DESIGN.md 공식 규격](https://github.com/google-labs-code/design.md)

## 핵심 요약

**ohmyPM에 남의 브랜드를 입힐 이유는 없다. 이 모음에서 쓸 것은 DESIGN.md라는 '형식'이다. 우리 화면의 색·글꼴 값을 그 형식으로 정리한 한 장이면 충분하다.**

- 원본은 VoltAgent/awesome-design-md가 맞다. 별 약 12만 개다. 다만 VoltAgent는 회사이고 유료 사이트 getdesign.md를 함께 운영하는 홍보성 저장소다. 파일을 어떻게 만드는지(자동인지 수작업인지)는 공개하지 않았다.
- 정확도를 검증한 독립 시험은 찾지 못했다. 파일 스스로 "공개 웹페이지를 분석해 해석한 것"이라고 밝힌다. 섞여 들어간 엉뚱한 글자, 다크 모드 누락 같은 오류 제보도 열려 있다.
- 상표·저작권: 웹사이트의 전체적인 '느낌'은 미국에서 트레이드 드레스(제품의 전체 외관을 보호하는 상표법 개념)로 보호될 수 있다. 다만 우리처럼 외부에 내보이지 않는 내부 도구라면 실제 위험은 낮다.
- 기존 Taste 금지 목록과 부딪히는 지점이 있다. 일부 브랜드 파일이 Inter 글꼴이나 보라 계열 주색을 권하는데, 이것이 Taste의 'AI 티' 항목과 겹친다.

## 원본과 구조

### awesome-design-md (본체)
- 소유자는 VoltAgent다. 커밋 대부분은 Necati Özmen 한 사람이 했다. 별 약 12만, 포크 약 1.3만, 라이선스는 MIT. 포크나 사칭 저장소는 아니다. [출처](https://github.com/VoltAgent/awesome-design-md)
- 브랜드 73개가 들어 있다. 브랜드마다 `DESIGN.md` 하나와 미리보기 HTML 2개(밝은 화면·어두운 화면)가 있다. 설치라고 할 것도 없이 파일을 프로젝트 맨 위 폴더에 복사하고 에이전트에게 "이걸 따라라"라고 말하면 된다. 훅·설정 변경·텔레메트리(사용 기록 자동 전송)는 없다. 그냥 마크다운 파일이다. [출처](https://github.com/VoltAgent/awesome-design-md)
- 최근 커밋은 2026-10-05인데 배지 추가 같은 문서 수정이다. 새 브랜드 추가는 2026-06-08(Nintendo)이 마지막이다. [출처](https://api.github.com/repos/VoltAgent/awesome-design-md/commits?per_page=8)
- DESIGN.md 새 파일은 외부 기여를 받지 않는다("품질 유지를 위해"). [출처](https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/CONTRIBUTING.md)
- 형식 자체는 Google Stitch가 2026-04-21 공개한 DESIGN.md 규격을 따른다. 정확한 값은 YAML(설정용 텍스트 형식)로, 그 값을 고른 이유는 글로 적는 구조다. [출처](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/)

### 홍보와 독립 후기 구분
- getdesign.md는 "VoltAgent 팀이 운영"한다고 적혀 있다. 분석 550개 이상을 내세우고 유료 카탈로그 이용권, 맞춤 제작 의뢰, 제휴 프로그램을 판다. 저장소 README도 이 사이트로 사람을 보내는 역할을 한다. [출처](https://getdesign.md)
- 비판적 후기로는 remio.ai 글(2026-09-02)이 가장 자세하다. 다만 이 글도 자기 제품을 홍보하는 회사 블로그다. 요지: "별과 인기 순위는 관심을 잴 뿐 화면 품질을 재지 않는다", "브랜드를 그대로 복제하는 것이 가장 약한 쓰임새다". [출처](https://www.remio.ai/post/voltagent-awesome-goes-viral-but-design-md-tests-a-bigger-promise)
- 나머지 후기는 "Stripe 파일을 넣었더니 Claude가 잘 따랐다" 같은 개인 경험담이다. 같은 조건에서 넣은 경우와 안 넣은 경우를 비교한 시험은 찾지 못했다. [출처](https://uxplanet.org/my-top-5-favorite-ways-of-using-design-md-in-claude-code-d1b52fd49cea)

### 열린 이슈 중 눈여겨볼 것
- #408(2026-05): "하위 폴더 README가 getdesign.md로 넘기는 안내문뿐이라 로컬 에이전트가 내용을 못 얻는다"는 제보다. 실제로 확인해 보니 `linear.app/README.md`는 안내문뿐이었다. 반면 같은 폴더의 `DESIGN.md`에는 내용이 다 들어 있다(약 350줄). 즉 README가 아니라 DESIGN.md 파일을 직접 받으면 된다. [출처](https://github.com/VoltAgent/awesome-design-md/issues/408)
- #469(2026-09): Vercel 파일의 글자 규격 항목에 관계없는 터키어 문장이 섞여 있다. [출처](https://api.github.com/repos/VoltAgent/awesome-design-md/issues?state=open&per_page=40)
- #443: Figma 파일에 다크 모드가 빠져 있다. #470(2026-09-30): getdesign.md가 접속되지 않는다는 제보.
- 열린 이슈는 300개가 넘는다(2026-09 기준). 대부분 "이 브랜드도 만들어 달라"는 요청이다. 보안 문제 제보는 보이지 않았다. [출처](https://www.remio.ai/post/voltagent-awesome-goes-viral-but-design-md-tests-a-bigger-promise)

## 정확도

- 파일을 직접 열어 봤다. Linear 파일은 주색 `#5e6ad2`, 바탕 `#010102`에 글꼴은 Linear 전용 서체로 되어 있고, 대신 쓸 무료 글꼴로 Inter·Geist를 제안한다. 마지막에 '알려진 빈틈' 절이 있다. [출처](https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/linear.app/DESIGN.md)
- Stripe 파일은 이름을 "Stripi-Inspired"로 바꿔 적었다. 스스로를 "영감을 받은 해석"이라고 부르고, 글꼴 Söhne가 유료 서체라는 점도 밝힌다. 주색은 `#533afd`. [출처](https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/stripe/DESIGN.md)
- 파일 모두 공개 마케팅 페이지를 분석한 것이다. 그래서 실제 앱 안의 표·입력 양식·오류 상태 같은 부분은 빠지기 쉽다. [출처](https://www.remio.ai/post/voltagent-awesome-goes-viral-but-design-md-tests-a-bigger-promise)
- 정리하면 "그 브랜드처럼 보이는 출발점"이지 공식 디자인 체계가 아니다. 공식 체계를 옮긴 것이라는 근거는 없다.

## 상표·저작권

- 미국 기준으로 웹페이지의 일반적인 배치는 저작권 보호를 받지 않는다. CSS 코드, 이미지, 글은 보호될 수 있다. [출처](https://www.nolo.com/legal-encyclopedia/what-trade-dress.html)
- 색·글꼴·배치를 묶은 전체 외관은 트레이드 드레스로 보호될 수 있다. Ingrid & Isabel v. Baby Be Mine(2014) 판결이 예다. 성립하려면 세 조건이 필요하다: 그 브랜드만의 독특함, 기능과 무관한 장식일 것, 소비자가 헷갈릴 가능성. [출처](https://www.pillsburylaw.com/images/content/9/7/v2/977/EcommerceLawReports-GhajarLevineNovDec2014.pdf)
- 저장소 쪽 입장은 "어떤 사이트의 시각 정체성도 우리 것이라 주장하지 않는다" 한 줄뿐이다. MIT 라이선스는 이 저장소 자료에만 적용된다. 브랜드 상표·글꼴 사용권까지 주지는 않는다. [출처](https://github.com/VoltAgent/awesome-design-md)
- 유료 글꼴(Söhne, Linear 전용 서체 등)은 파일에 이름만 적혀 있다. 글꼴 파일 자체는 들어 있지 않다. 실제로 쓰려면 별도 구매가 필요하다.
- 우리 경우: ohmyPM은 외부에 공개하지 않는 혼자 쓰는 관리 화면이다. 소비자 혼동이 생길 여지가 거의 없으므로 법적 위험은 낮다고 본다. 다만 이 판단은 법률 자문이 아니다. 같은 파일을 외부에 공개하는 프로젝트에 쓸 때는 따로 따져야 한다.

## 이웃 프로젝트

| 항목 | awesome-design-md | awesome-design-html | awesome-design-skills |
|---|---|---|---|
| 소유 | VoltAgent(회사) | yzfly(개인) | Bergside(TypeUI 운영) |
| 별 | 약 12만 | 159 | 약 3,100 |
| 내용 | 브랜드 73개, 마크다운 | 브랜드별 완성 HTML 약 115개 | 스타일 스킬 67개(유리 질감, 브루탈리즘 등) |
| 설치 방식 | 파일 복사 | `~/.claude/skills/`에 통째로 내려받기 | `npx typeui.sh` 명령 도구로 받기 |
| 최근 커밋 | 2026-10-05 | 2026-06-14 | 2026-06-28 |

- awesome-design-html은 본체의 웹 규격을 가져와 HTML로 다시 만든 것이다. 설치 개수가 116·115·117로 저장소 안에서도 엇갈린다. 각 HTML은 구글 폰트를 외부 서버에서 불러온다. [출처](https://github.com/yzfly/awesome-design-html)
- 권장 설치 위치가 사용자 범위(`~/.claude/skills/`)다. 그러면 ohmyPM이 헤드리스(화면 없이 자동 실행)로 부르는 모든 프로젝트에 이 스킬이 실린다. 브랜드 이름만 나와도 자동으로 켜진다고 저장소가 설명한다.
- awesome-design-skills는 브랜드 흉내가 아니라 스타일 묶음이다. 받으려면 TypeUI 명령 도구, 즉 남이 만든 실행 코드를 돌려야 한다. 이 도구가 사용 기록을 보내는지는 확인하지 못했다. 저장소 자체가 자사 제품과 광고 자리 홍보를 겸한다. [출처](https://github.com/bergside/awesome-design-skills)

## Taste 대조

이미 정리한 Taste 문서를 되풀이하지 않고, 새로 보인 충돌만 적는다.

- **부딪힘**: Linear 파일은 무료 대체 글꼴로 Inter를 권하고, Stripe 파일은 보라 계열(`#533afd`)을 주색으로 쓴다. Inter와 보라·남색 계열은 흔히 'AI 티'의 대표 사례로 꼽힌다. 두 규칙을 함께 실으면 에이전트가 어느 쪽을 따를지 정해지지 않는다.
- **겹침**: 브랜드 파일마다 '하지 말 것' 절이 있다. 이 절은 Taste의 금지 목록과 같은 역할을 한다. 둘 다 실으면 규칙이 중복된다.
- **보완**: Google 공식 명령 도구의 `lint`(규격 검사)에는 글자색과 배경색 대비가 WCAG AA 기준 4.5:1보다 낮으면 경고하는 규칙이 있다. WCAG는 웹 접근성 국제 기준이다. 이 검사는 우리 대비 규칙과 그대로 맞아떨어진다. [출처](https://github.com/google-labs-code/design.md)

## 우리 화면 현황

- ohmyPM 화면(`src/web/routers/pages.py:27`)에는 이미 색 변수 9개가 `:root`에 정리되어 있다(`--bg`, `--ink`, `--muted`, `--green`, `--red`, `--amber` 등). 글꼴은 시스템 기본 글꼴이다(`pages.py:29`).
- 즉 DESIGN.md의 '값' 부분은 사실상 이미 있다. 빠진 것은 "왜 이 값인지"와 "하지 말 것"을 적은 글뿐이다.

## 우리 쪽 적용

제안일 뿐 결정이 아니다.

1. **브랜드 파일은 설치하지 않는다.** 이유는 셋이다. 내부 관리 화면에는 브랜드 개성이 필요 없다. 마케팅 페이지 분석이라 표·목록·상태 표시처럼 ohmyPM에 정작 필요한 부분이 약하다. 그리고 Taste 규칙과 부딪힌다.
2. **우리만의 `DESIGN.md` 한 장을 만든다.** `pages.py`의 색 변수를 Google 규격 형식으로 옮기고, 이모지 금지·WCAG 대비 같은 기존 화면 규칙을 '하지 말 것' 절에 넣는다. 위치는 ohmyPM 저장소 안이다. Google 명령 도구의 `lint`로 대비를 검사하면 화면 규칙 점검을 일부 자동화할 수 있다. 이 명령 도구는 알파(시험 단계) 버전이다.
3. **사용자 범위 설치(awesome-design-html 방식)는 하지 않는다.** 40개 프로젝트의 헤드리스 호출 전부에 실리고, 브랜드 이름만 나와도 켜진다. 비용도 동작도 예측하기 어려워진다.
4. **외부 공개 화면이 있는 프로젝트**(예: 블로그·유튜브 관련 프로젝트)에서 분위기 참고가 필요하면, 그때 해당 브랜드의 `DESIGN.md` 하나만 읽어서 아이디어를 얻는다. 복사해 넣기보다 참고 용도로 쓰고, 브랜드 이름과 고유 색은 우리 것으로 바꾼다.
5. 버리는 안건(브랜드 파일 설치, awesome-design-skills 도입)의 재검토 조건: "외부에 공개되는 화면을 새로 만드는 프로젝트가 생길 때". 이 조건은 ohmyPM `docs/`에 기록해 두기를 권한다.

## 확인 못 한 것

- DESIGN.md를 사람이 썼는지, 도구나 AI로 자동 추출했는지 확인하지 못했다. 저장소도 getdesign.md도 밝히지 않는다. 터키어가 섞이는 오류(#469)를 보면 반자동 공정일 가능성이 있다. 하지만 추측일 뿐이다.
- Stripe의 실제 주색이 `#533afd`인지 실제 사이트와 대조하지 않았다. Linear의 `#5e6ad2`는 널리 알려진 값과 일치하지만, 이것도 공식 자료로는 확인하지 못했다.
- Stripe 파일이 브랜드 이름을 "Stripi"로 바꿔 적은 이유를 모른다. 상표 회피 목적인지, 단순 오타인지 확인하지 못했다.
- 정확도와 품질 향상을 잰 통제 실험은 찾지 못했다. 독립 후기는 모두 개인 경험담이다.
- 별 수가 출처마다 다르다(약 11.2만~12만). 이번에 직접 본 값은 약 12.01만이다. 브랜드 수도 출처에 따라 55개와 73개로 엇갈리는데, 지금 저장소 기준은 73개다.
- TypeUI 명령 도구(`npx typeui.sh`)가 사용 기록을 보내는지, 무엇을 어디에 쓰는지 코드로 확인하지 않았다.
- getdesign.md의 개인정보·쿠키 정책 내용과 유료 상품 가격은 확인하지 못했다.
- 한국 법에서 웹사이트 외관 모방이 어떻게 다뤄지는지는 조사하지 않았다. 위 법률 내용은 미국 사례 기준이다.
