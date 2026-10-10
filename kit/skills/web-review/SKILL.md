---
name: web-review
description: 화면 코드(HTML·CSS·JS·JSX·TSX)를 아래 고정 점검표로 검사해 파일:줄로 보고한다. 사용자가 화면 점검·접근성 점검·UI 리뷰를 요청할 때 쓴다. 코드는 고치지 않는다.
---

<!--
  출처: vercel-labs/web-interface-guidelines 의 command.md, 커밋 4ecfb9fb8d1d3b7009674869b3aaee2f904042e1 (2026-10-05).
  원본 Vercel 스킬(web-design-guidelines)은 실행할 때마다 main 가지의 규칙을 받아 와 내용이 예고 없이 바뀐다.
  이 사본은 한 판으로 고정하고(외부 통신 없음), 한국어 화면·우리 규칙에 맞지 않는 항목을 뺀 뒤 우리말로 옮겼다.
  뺀 것: 영어 문구 규칙(Title Case, 둥근 따옴표, &, 2인칭), 결과의 체크 표시, CDN·폰트 미리 불러오기,
  동영상·GIF 성능, 노치 안전 영역, 언어 감지. 원본 라이선스: LICENSE-vercel (MIT, Copyright (c) 2025 Vercel Labs).
  상태: 환경 세팅 재료 후보 — 화면 프로젝트 하나에 시험해 쓸모를 확인하기 전(ohmyPM docs/references.md).
-->

# 화면 코드 점검

검사 대상: 사용자가 지정한 파일. 지정이 없으면 어떤 파일을 볼지 먼저 묻는다.

파일을 읽고 아래 규칙에 비춰 본다. 실제로 걸리는 것만, 줄 번호를 다시 읽어 확인한 뒤 적는다.
화면에 그려진 결과(색 대비, 겹침)는 코드만으로 판단하지 말고 "확인 못 함"으로 남긴다.

## 규칙

### 접근성
- 아이콘만 있는 버튼에는 `aria-label`
- 입력칸에는 `<label>` 또는 `aria-label`
- 동작은 `<button>`, 이동은 `<a>`(또는 라우터 링크). `<div onclick>` 금지
- 클릭되는 요소는 키보드(Tab, Enter·Space)로도 쓸 수 있어야 한다
- 이미지에는 `alt`(꾸밈용이면 `alt=""`), 꾸밈 아이콘에는 `aria-hidden="true"`
- 비동기로 바뀌는 알림(토스트, 검증 오류)에는 `aria-live="polite"`
- ARIA보다 의미 있는 태그(`<button>`, `<a>`, `<label>`, `<table>`)를 먼저
- 제목은 `<h1>`~`<h6>` 순서대로, 본문 바로가기 링크

### 포커스
- 조작 요소에는 눈에 보이는 포커스 표시. `outline: none`만 하고 대체 표시가 없으면 안 된다
- `:focus`보다 `:focus-visible`(클릭할 때는 테두리가 안 생기게)
- 여러 부품이 묶인 조작은 `:focus-within`
- 고정 머리글·바닥글·덮개가 포커스된 요소를 가리면 안 된다

### 입력 양식
- 알맞은 `type`(`email`, `tel`, `url`, `number`)과 `name`, 필요하면 `autocomplete`
- 붙여넣기를 막지 않는다
- 제출 버튼은 요청이 시작될 때까지 눌리는 상태로, 요청 중에는 진행 표시
- 오류는 해당 칸 옆에, 제출 때 첫 오류 칸으로 포커스
- 저장 안 한 내용이 있으면 화면을 떠나기 전에 묻는다

### 움직임
- `prefers-reduced-motion`(움직임 줄이기 설정)을 따른다
- 애니메이션은 `transform`·`opacity`만, `transition: all` 금지

### 글자와 내용
- 불러오는 중 문구는 `…`로 끝낸다("불러오는 중…")
- 숫자를 비교하는 열에는 `font-variant-numeric: tabular-nums`
- 긴 글이 들어와도 깨지지 않게(말줄임, 줄바꿈), flex 자식에는 `min-width: 0`
- 빈 목록·빈 문자열일 때 깨진 화면 대신 빈 화면 안내
- 오류 문구에는 문제와 함께 다음에 할 일을 적는다
- 버튼 이름은 구체적으로("확인"보다 "API 키 저장")

### 상태와 이동
- 지우기처럼 되돌릴 수 없는 동작은 확인 창이나 되돌리기 시간 없이 바로 실행하지 않는다
- 이동은 링크로 해서 Ctrl+클릭·가운데 클릭으로 새 탭이 열리게
- 필터·탭·페이지 같은 상태는 주소(URL)에 반영

### 성능과 배치
- 50개가 넘는 긴 목록은 보이는 부분만 그리거나(`content-visibility: auto`) 나눠 그린다
- 그리는 도중 배치 값 읽기(`getBoundingClientRect`, `offsetHeight`, `scrollTop`)를 섞지 않는다
- `<img>`에는 `width`·`height`를 정해 화면이 밀리지 않게
- 배치는 JS 측정보다 flex·grid로

### 마우스와 터치
- 버튼·링크에는 마우스 올림 상태
- 마우스 올림·누름·포커스 상태는 평소보다 눈에 띄게
- 창·서랍 안에는 `overscroll-behavior: contain`
- 끌기·밀기 같은 몸짓만으로 되는 동작에는 클릭과 키보드 대안

### 다크 모드
- 다크 테마에는 `<html>`에 `color-scheme: dark`
- `<select>`에는 배경색과 글자색을 직접 지정(Windows 다크 모드)

### React·Next.js를 쓰는 프로젝트만
- `value`를 준 입력칸에는 `onChange`(아니면 `defaultValue`)
- 날짜·시간을 그릴 때 서버와 브라우저 결과가 달라지지 않게(하이드레이션 불일치)

### 바로 지적할 것
- `user-scalable=no`, `maximum-scale=1`(확대 막기)
- 크기 없는 이미지, 이름표 없는 입력칸, `aria-label` 없는 아이콘 버튼
- 이유 없는 `autoFocus`
- 날짜·숫자를 손으로 형식화(가능하면 `Intl.DateTimeFormat`·`Intl.NumberFormat`)

## 결과 형식

파일별로 묶고 `파일:줄 - 문제` 한 줄씩. 고치는 법이 뻔하지 않을 때만 짧게 덧붙인다. 머리말 없이.
이모지와 체크 표시 같은 장식 기호는 쓰지 않는다.

```text
## src/Button.tsx

src/Button.tsx:42 - 아이콘 버튼에 aria-label 없음
src/Button.tsx:67 - transition: all → 바뀌는 속성만 적기

## src/Card.tsx

이상 없음
```

끝에 "확인 못 함:" 한 줄 — 코드만으로는 판단할 수 없었던 것(실제 대비, 겹침, 포커스 순서).
