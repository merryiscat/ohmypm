# Claude-Video(영상 보기 플러그인) 실사용 평가와 ohmyPM·랩실 쓸모

기준일 2026-10-10 · 핵심 근거: [bradautomates/claude-video 저장소](https://github.com/bradautomates/claude-video)

## 핵심 요약

**원본은 bradautomates/claude-video가 맞습니다. 인기도 가장 많습니다. 다만 우리 환경(한국어 윈도우, 헤드리스 호출 40개 프로젝트)에서는 사용자 범위로 설치하지 않는 게 맞습니다. 랩실에는 '자막만 받아 읽는' 가벼운 방식이면 충분해 보입니다.**

- Claude는 지금도 영상을 직접 보지 못합니다. 이 플러그인들은 모두 같은 방식입니다. 영상을 정지 사진(프레임) 몇십 장과 자막·받아쓰기 글로 바꿔서 Claude에게 넘깁니다.
- 원본 플러그인은 0.3.0부터 Gemini 엔진이 생겼습니다. `GEMINI_API_KEY`가 환경에 있으면 기본값으로 **영상 전체를 구글로 보냅니다.**
- 10분 영상 하나의 비용: 기본 설정이면 사진 약 1만~2만 토큰에 자막 약 5천 토큰이 더해집니다. 고해상도로 켜면 8만 토큰 가까이까지 늘어납니다. 토큰은 모델이 글과 그림을 읽는 단위입니다.
- 원본 저장소에는 열린 이슈가 50개 있습니다. 그중 상당수가 프레임 추출 고장과 윈도우 문제입니다. 한국어 윈도우 글자 처리(cp949) 충돌도 보고되어 있습니다.
- 유튜브 약관은 허락 없는 다운로드와 자동화된 접근을 금지합니다. 개인 조사용이라도 이 위험은 사라지지 않습니다.

## 정체 확정

### 원본과 이름이 비슷한 것들

- **원본**: github.com/bradautomates/claude-video. 저장소 안에서 플러그인 이름은 `watch`이고, `/watch` 명령으로 씁니다. 첫 커밋은 2026-04-24("Initial commit: /watch skill v0.1.0")입니다. 별 1.83만, 포크(복제본) 1.9천, MIT 라이선스입니다. [출처](https://github.com/bradautomates/claude-video) [출처](https://github.com/bradautomates/claude-video/commits/main)
- **mathiaschu/watch**: 원본의 포크라고 스스로 밝히고 있습니다. 받아쓰기를 유료 API 대신 로컬(mlx-whisper·openai-whisper)로 돌리고, 브라우저 쿠키를 지원합니다. [출처](https://claudepluginhub.com/plugins/mathiaschu-watch)
- **mdc159/watch**: 플러그인 모음 사이트에 올라와 있었습니다. 지금은 페이지가 사라졌습니다(HTTP 410). 정체는 확인하지 못했습니다. [출처](https://www.claudepluginhub.com/plugins/mdc159-watch)
- instagit.com, graphify.net 같은 곳의 'claude-video 가이드'는 자동 생성 요약 페이지로 보입니다. 이번 확인에서 악성 사칭 저장소는 찾지 못했습니다.

### 대안 두 개

- **claude-video-vision**: github.com/jordanrendric/claude-video-vision. 별 1.4천, MIT 라이선스입니다. [출처](https://github.com/jordanrendric/claude-video-vision)
- **claude-real-video**: github.com/HUANGCHIHHUNGLeo/claude-real-video. 짧은 이름은 `crv`이고 별 2.2천, MIT 라이선스입니다. 유료 확장판(crv Pro)이 따로 있습니다. [출처](https://github.com/HUANGCHIHHUNGLeo/claude-real-video)

### 반대 방향: 영상을 만드는 도구

- **digitalsamba/claude-code-video-toolkit**은 영상을 '보는' 도구가 아니라 '만드는' 작업 공간입니다. 원고, AI 음성 해설, 음악, 화면을 만들어 MP4로 뽑습니다. 만든 회사가 원래 쓰던 용도는 스프린트(짧은 개발 주기) 리뷰 영상 제작입니다. [출처](https://cdn.jsdelivr.net/gh/digitalsamba/claude-code-video-toolkit@main/README.md)
- 우리 기존 문서 'HyperFrames — HTML로 영상 만들기'와 같은 갈래이므로 여기서는 더 다루지 않습니다.

## 동작 구조

### 원본(bradautomates/claude-video)

엔진이 두 가지입니다. [출처](https://github.com/bradautomates/claude-video)

- **Gemini 엔진(클라우드)**: `GEMINI_API_KEY`가 있으면 기본으로 이쪽을 씁니다(`WATCH_ENGINE=auto`).
  - 영상의 그림과 소리를 통째로 구글 영상 모델(`gemini-3.7-flash`)에 보냅니다. 구글이 시간 표시가 붙은 답을 돌려줍니다.
  - 유튜브 주소는 구글에 주소를 그대로 넘깁니다. 다른 주소는 내려받은 뒤 구글 파일 저장소(Files API)에 올리고, 답을 받은 뒤 지웁니다.
  - 이 경우 영상을 '보는' 것은 Claude가 아니라 Gemini입니다. Claude는 Gemini가 쓴 요약을 읽을 뿐입니다.
- **로컬 엔진**: 구글에 접속하지 않습니다.
  - 프레임 추출: ffmpeg(영상·음성 처리 프로그램)
  - 다운로드: yt-dlp(유튜브 등 50곳 이상의 사이트에서 영상을 받는 프로그램)
  - 자막: 영상에 원래 달린 자막을 먼저 씁니다. 자막이 없을 때만 받아쓰기를 합니다.
  - 받아쓰기 선택지: WhisperX(로컬, 키 없음, 권장), Groq(클라우드 whisper-large-v3), OpenAI(클라우드 whisper-1), 자막만 쓰기. Whisper는 OpenAI가 만든 음성 인식 모델입니다.
- Gemini 쪽이 실패해도 로컬로 저절로 넘어가지 않습니다. 알려 주고 사용자가 고르게 합니다.

프레임은 '상세도'로 고릅니다. [출처](https://github.com/bradautomates/claude-video)

| 상세도 | 고르는 방식 | 기본 상한 |
|---|---|---|
| transcript | 사진 없음(글만) | 없음 |
| efficient | 핵심 프레임(키프레임) | 50장 |
| balanced | 장면이 바뀌는 지점 | 100장 |
| token-burner | 장면 전환, 상한 없음 | 무제한(250장 넘으면 경고) |

- 기본 사진 크기는 가로 최대 512픽셀입니다. 화면 속 글자를 읽어야 할 때는 `--resolution 1024`를 씁니다.
- 거의 같은 사진은 16×16 축소본을 비교해 걸러냅니다.

### claude-video-vision

- MCP 서버 방식입니다. MCP는 Claude에 외부 도구를 붙이는 표준 연결 방식입니다. Node.js로 된 서버가 `video_watch` 등 도구 6개를 제공합니다. [출처](https://github.com/jordanrendric/claude-video-vision)
- 프레임은 ffmpeg로 뽑습니다. 초당 장수, 구간, 해상도는 질문에 맞춰 Claude가 정합니다.
- 받아쓰기는 Gemini API, 로컬 Whisper(whisper.cpp·openai-whisper), OpenAI API 중에서 고릅니다. 유튜브는 yt-dlp로 받고 자막을 먼저 씁니다.

### claude-real-video

- 파이썬 명령줄 도구이고, MCP 서버(`crv-mcp`)도 함께 있습니다. [출처](https://github.com/HUANGCHIHHUNGLeo/claude-real-video)
- 프레임은 ffmpeg를 한 번 돌려 장면 전환 지점을 잡습니다. 최소 초당 1장을 보장합니다. 최근 4장과 비교해 8% 넘게 달라진 사진만 남깁니다.
- 받아쓰기는 자막을 먼저 씁니다. 없으면 로컬 Whisper(whisper, faster-whisper, mlx-whisper)를 씁니다. 클라우드 받아쓰기는 설명되어 있지 않습니다.

### 유튜브 약관

- 유튜브 약관은 명시적 허락이나 사전 서면 승인 없이 콘텐츠에 접근하거나 다운로드하는 것을 금지합니다. 로봇이나 스크래퍼 같은 자동화된 수단으로 접근하는 것도 금지합니다. 예외는 robots.txt를 따르는 공개 검색엔진뿐입니다. [출처](https://www.youtube.com/t/terms)
- 유튜브 최고경영자도 영상이나 자막을 내려받는 것은 명백한 약관 위반이라고 말했습니다. [출처](https://www.theregister.com/2024/07/17/youtube_video_subtitles_ai/)
- 세 도구 모두 yt-dlp로 유튜브에 접근합니다. 원본 플러그인의 Gemini 엔진은 구글 쪽에 유튜브 주소를 넘기므로 이 문제가 덜할 수 있습니다. 하지만 이 점을 다룬 공식 근거는 찾지 못했습니다.

## 설치 영향

### 원본(bradautomates/claude-video)

설치하면 다음을 건드립니다. [출처](https://github.com/bradautomates/claude-video)

- **필요한 프로그램**: Python 3.10 이상, ffmpeg·ffprobe, 최신 yt-dlp, 자바스크립트 실행기(Deno, 유튜브 대응용)
- **WhisperX를 고르면**: 따로 Python 3.12 환경을 만들고 모델을 내려받습니다. 디스크 약 3GB, 메모리 8GB 이상이 필요합니다. 검증된 환경은 애플 실리콘 맥뿐이고, **윈도우는 테스트되지 않았습니다.**
- **API 키**: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`. 찾는 순서는 환경변수 → `~/.config/watch/.env` → 현재 폴더의 `.env`입니다.
  - 주의: 어떤 프로젝트 폴더의 `.env`에 Gemini 키가 들어 있으면, 그 폴더에서 실행할 때 Gemini 엔진이 자동으로 켜집니다. 이 부분은 문서 내용으로 추론한 것입니다.
- **설정 파일**: `~/.config/watch/.env`
- **훅**: 훅은 특정 시점에 자동으로 실행되는 명령입니다. 이 플러그인은 `SessionStart` 훅(세션이 시작될 때마다 실행)을 등록합니다. 조건 없이 모든 세션에서 `check-setup.sh`를 최대 5초 동안 돌립니다. [출처](https://raw.githubusercontent.com/bradautomates/claude-video/main/hooks/hooks.json)
  - 이 스크립트는 `setup.py --check`를 돌립니다. 문제가 있을 때만 한 줄 안내를 출력합니다. 스크립트 자체는 네트워크 접속이나 파일 수정을 하지 않습니다. 다만 `setup.py --check` 안쪽은 확인하지 못했습니다. [출처](https://raw.githubusercontent.com/bradautomates/claude-video/main/hooks/scripts/check-setup.sh)
- **외부로 나가는 데이터**: Gemini 엔진이면 영상 전체가 구글로 갑니다. Groq나 OpenAI 받아쓰기를 고르면 음성이 그쪽으로 갑니다. 로컬 엔진에 WhisperX나 자막만 쓰면 다운로드 말고는 밖으로 나가는 것이 없습니다.

### claude-video-vision

- Node.js 24 이상과 ffmpeg가 필요합니다. yt-dlp는 유튜브를 볼 때만 필요합니다. [출처](https://github.com/jordanrendric/claude-video-vision)
- MCP 서버는 처음 쓸 때 npm(자바스크립트 패키지 저장소)에서 `npx`로 자동 설치됩니다. 외부 코드를 실행할 때 받아 오는 구조라는 뜻입니다.
- 설정은 `~/.claude-video-vision/config.json`에, Whisper 모델은 `~/.claude-video-vision/models/`에 저장됩니다. 훅은 문서에 언급이 없습니다.

### claude-real-video

- `pip install "claude-real-video[whisper]"`로 설치합니다. ffmpeg는 따로 깔아야 합니다. [출처](https://github.com/HUANGCHIHHUNGLeo/claude-real-video)
- 기본 기능에 API 키가 필요하다는 말은 없습니다. 키가 언급되는 것은 유료판의 AI 보고서 기능뿐입니다. 훅 언급도 없습니다.

## 비용

### 계산 근거

- Anthropic 공식 문서 기준으로, 사진 한 장의 토큰 수는 28×28픽셀 조각의 개수입니다. 계산식은 `올림(가로/28) × 올림(세로/28)`입니다. [출처](https://platform.claude.com/docs/en/build-with-claude/vision)
- 원본 플러그인의 기본 사진(가로 512, 16:9 비율이면 512×288)은 19×11, 약 **209토큰**입니다. 1024×576이면 37×21, 약 **777토큰**입니다. 이 두 값은 계산식으로 우리가 직접 낸 것입니다.
- 원본 저장소 자료를 옮긴 글에 실측치가 있습니다. 49분 영상에서 efficient 50장이 약 9.8천, balanced 100장이 약 1.97만, 자막만은 약 2.66만 토큰이었습니다. 계산치와 거의 맞습니다. [출처](https://www.besthub.dev/articles/how-a-single-watch-command-lets-claude-actually-see-video-f4fdf78f9fa9)

### 10분 영상 하나(추정)

| 설정 | 사진 | 자막·받아쓰기 | 합계(대략) |
|---|---|---|---|
| transcript(글만) | 0 | 약 5천 | 약 5천 |
| efficient(50장) | 약 1만 | 약 5천 | 약 1.5만 |
| balanced(최대 100장) | 약 2만 | 약 5천 | 약 2.5만 |
| balanced + 1024해상도 | 약 7.8만 | 약 5천 | 약 8만 |

- 자막 토큰은 위 49분 실측을 10분으로 나눈 값입니다. 한국어 영상은 이보다 많을 수 있지만 확인하지 못했습니다.
- 감을 잡자면, 기본 설정 한 편(약 2.5만)은 큰 소스 파일 몇 개를 읽는 정도입니다. 고해상도 한 편(약 8만)은 대화 컨텍스트(모델이 한 번에 붙들고 있는 대화 내용)를 눈에 띄게 차지합니다.
- 사진은 한 번 들어오면 그 대화가 끝날 때까지 남습니다. 질문을 이어서 할 때마다 다시 계산에 들어갑니다. 캐시(이미 읽은 내용을 재사용하는 기능)가 적용되면 비용은 줄지만 컨텍스트 자리는 그대로 차지합니다.
- 맥스 요금제 세션 한도가 토큰으로 몇 개인지는 공식 수치를 찾지 못했습니다. 그래서 '한도의 몇 %'로는 말할 수 없습니다.
- 참고로 claude.ai 채팅은 한 메시지에 사진 20장까지만 받습니다. API는 한 요청에 사진이 20장을 넘으면 장당 크기 제한이 더 엄격해집니다(한 변 2000픽셀). 512픽셀 사진이면 문제없습니다. [출처](https://platform.claude.com/docs/en/build-with-claude/vision)

## 사용자 평가

### 독립 후기와 홍보

- 해커뉴스나 레딧에서 원본을 다룬 토론 글은 찾지 못했습니다.
- 찾은 글은 대부분 저장소 README를 옮겨 적은 소개글이나 자동 생성 요약이었습니다. Medium, Towards AI, CSDN, knightli 등이 그렇습니다. [출처](https://medium.com/@slakhyani20/claude-can-finally-watch-videos-bc022d2441d7) [출처](https://knightli.com/2026/07/08/claude-video-watch-video-transcript-frames-skill/)
- besthub 글은 이해관계를 밝히지 않은 우호적 요약입니다. 그래도 몇 가지 한계는 짚었습니다. 영상이 10분을 넘으면 프레임이 듬성듬성해지고, 사진 비교 방식이 터미널 화면 스크롤 같은 작은 변화를 잘 구분하지 못한다는 점입니다. [출처](https://www.besthub.dev/articles/how-a-single-watch-command-lets-claude-actually-see-video-f4fdf78f9fa9)
- 별 수는 출처마다 다릅니다(832, 약 2,500, 7,800 이상, 1.83만). 집계 시점이 다르기 때문으로 보입니다. 2026-10-10에 저장소 화면에서 확인한 값은 1.83만입니다.

### 원본 저장소 상태

- 최근 커밋은 2026-09-25(0.3.2 출시)입니다. 9월에 Gemini 엔진, WhisperX 연동, ffmpeg 9 대응을 넣었습니다. [출처](https://github.com/bradautomates/claude-video/commits/main)
- 열린 이슈 50개 중 눈여겨볼 것들: [출처](https://github.com/bradautomates/claude-video/issues)
  - **프레임 추출 고장**: ffmpeg 7~9에서 `-vsync` 옵션이 없어져 실패한다는 보고가 10건 넘게 열려 있습니다(#141~#246). 변경 기록에는 0.3.0에서 고쳤다고 적혀 있습니다. 그런데 그 뒤인 9-25에도 같은 신고(#246)가 열렸습니다. [출처](https://raw.githubusercontent.com/bradautomates/claude-video/main/CHANGELOG.md)
  - **윈도우**: 출력 중 글자 처리 오류로 멈춤(#150), 한글 같은 비영어 경로에서 멈춤(#238), **cp949(한국어 윈도우 글자 체계) 충돌**(#240), 윈도우에서 유튜브 403 오류(#156)
  - **언어**: 영어가 아닌 영상에 원래 자막 대신 영어 자동번역 자막이 들어온다는 보고(#153·#144·#240), 더빙 영상에 다른 언어 자막이 붙는다는 보고(#247)
  - **엉뚱한 결과**: 말이 없는 영상에서 Whisper가 대사를 지어내고, 그것이 정상 받아쓰기처럼 표시된다는 보고(#222)
  - **비용 위험**: Gemini 엔진이 503 오류를 받아도 재시도 횟수 제한이 없다는 보고(#250)
- 보안이나 키 유출을 다룬 이슈는 첫 페이지 25개에는 없었습니다. 나머지 25개는 보지 못했습니다.

## 대안 비교

| 항목 | claude-video(원본) | claude-video-vision | claude-real-video |
|---|---|---|---|
| 형태 | 스킬+훅(플러그인) | MCP 서버(Node.js) | 파이썬 명령줄 도구+MCP |
| 받아쓰기 | 자막 우선 → WhisperX(로컬)/Groq/OpenAI. 또는 Gemini가 영상 통째 처리 | 자막 우선 → Gemini/로컬 Whisper/OpenAI | 자막 우선 → 로컬 Whisper만 |
| 프레임 고르기 | 상세도 4단계(키프레임·장면 전환), 상한 50/100 | Claude가 질문에 맞춰 초당 장수·구간 지정 | 장면 전환 + 최소 초당 1장 + 최근 4장과 비교해 걸러냄 |
| 외부 전송 | Gemini 키가 있으면 기본으로 구글 전송 | 고른 받아쓰기 방식에 따라 다름 | 다운로드 말고는 없음(문서 기준) |
| 비용 | 도구 무료. Claude 토큰 + 쓰는 API 요금 | 도구 무료. Gemini 무료 등급 언급 | 무료. Pro 29달러(한 번 결제) |
| 별 | 1.83만 | 1.4천 | 2.2천 |
| 최근 커밋 | 2026-09-25 | 2026-10-06(v1.4.0) | 2026-07-03(커밋 화면 기준) |
| 열린 이슈 | 50 | 2 | 0 |
| 윈도우 | 문제 보고 여럿 | 자동 테스트(CI)는 우분투·맥만 | 윈도우 설치 명령 안내 있음, 실사용 보고 없음 |

출처: [원본](https://github.com/bradautomates/claude-video) · [video-vision](https://github.com/jordanrendric/claude-video-vision) · [video-vision 커밋](https://github.com/jordanrendric/claude-video-vision/commits/main) · [real-video](https://github.com/HUANGCHIHHUNGLeo/claude-real-video) · [real-video 커밋](https://github.com/HUANGCHIHHUNGLeo/claude-real-video/commits/main)

## 공식 기능

- Claude API가 받는 그림 형식은 JPEG·PNG·GIF·WebP 정지 사진뿐입니다. GIF 움직임도 첫 장만 씁니다. [출처](https://platform.claude.com/docs/en/build-with-claude/vision)
- claude.ai 업로드 안내에도 문서와 사진 형식만 있습니다. 영상과 음성은 없습니다. [출처](https://support.claude.com/en/articles/8241126)
- Claude Code에 영상 입력을 넣어 달라는 요청(#12676, 2025-11-29)은 아직 열려 있고, Anthropic 답변은 없습니다. [출처](https://claudeissues.com/issue/12676-feature-video-input-support-in-claude-code)
- 결론적으로 2026-10-10 현재 공식 영상 보기 기능은 없고, 이 플러그인들과 겹치지 않습니다. 원본 플러그인 문서도 Claude 채팅과 Cowork는 지원하지 않는다고 적고 있습니다. [출처](https://github.com/bradautomates/claude-video)

## 우리 쪽 적용

**아래는 제안일 뿐 결정이 아닙니다.**

### 판단: 사용자 범위 설치는 하지 않는 게 맞습니다

이유는 세 가지입니다.

- **헤드리스 호출 전체에 부담이 생깁니다.** 원본 플러그인을 사용자 범위(~/.claude)에 깔면, ohmyPM이 40개 프로젝트에서 Claude Code를 부를 때마다 SessionStart 훅이 파이썬 점검을 돌립니다(최대 5초). 스킬 설명도 매번 컨텍스트에 실립니다. 헤드리스 호출은 화면 없이 자동으로 Claude Code를 실행하는 방식입니다. claude-video-vision도 MCP 도구 6개가 모든 세션에 붙습니다.
- **모르는 사이에 영상이 구글로 갈 수 있습니다.** 어떤 프로젝트 `.env`에 Gemini 키가 있으면 그 폴더에서는 영상이 구글로 나갑니다. 40개 프로젝트 각각의 `.env` 상태를 계속 관리하기는 어렵습니다.
- **우리 환경에서 깨질 가능성이 큽니다.** 한국어 윈도우(cp949), 한글 경로, 최신 ffmpeg 쪽 고장 보고가 원본에 몰려 있습니다.

### 랩실에는 '글만' 방식이면 충분해 보입니다

- 랩실이 보고 싶은 영상은 대부분 발표나 튜토리얼입니다. 내용의 대부분은 말에 있습니다. 슬라이드나 코드 화면이 꼭 필요한 경우는 드물 것입니다.
- 그렇다면 사진 없이 자막만 읽는 방식(약 5천 토큰/10분)으로 쓸모의 대부분을 얻습니다. 사진은 "이 화면의 코드가 뭔지" 같은 질문이 생길 때만 구간을 정해 몇 장 보면 됩니다.
- 해 볼 만한 순서:
  1. **아이디어만 참고(가장 먼저 권함)**: 랩실 연구원 지침에 "영상 자료는 영상 설명란, 발표 슬라이드, 블로그 정리본, 논문을 먼저 찾는다"를 넣습니다. 많은 발표 영상은 같은 내용의 글이 따로 있습니다. 설치도, 약관 위험도 없습니다.
  2. **필요할 때만 프로젝트 범위로 시험**: 랩실 작업 폴더에만 claude-real-video(로컬 전용, 키 불필요, 이슈 0개)나 원본 플러그인을 깔고 transcript 모드로 써 봅니다. 이때 Gemini 키는 두지 않습니다. 단, 유튜브 주소로 쓰면 약관 위험이 남습니다. 본인 파일이나 내려받기가 허락된 영상부터 시험하는 게 안전합니다.
  3. **사용자 범위 설치**: 권하지 않습니다.
- 다른 프로젝트 중 youtube_ssalmuk(유튜브 자동 운영)은 영상을 '만드는' 쪽입니다. 업로드 전에 완성 영상을 Claude에게 검수시키는 용도라면 본인 파일이므로 약관 문제가 없습니다. 이 경우 프로젝트 범위 설치를 검토할 만합니다. CrisperWhisper_merry는 받아쓰기 모델 자체를 다루는 프로젝트라 이 플러그인과 직접 관계는 없습니다.

### 버리는 안건의 재검토 시점(정해 두기를 제안)

- **사용자 범위 설치**: Anthropic이 Claude Code에 공식 영상 입력을 넣었다는 발표가 나오면 그때 다시 봅니다. 그 전에는 재검토하지 않습니다.
- **프로젝트 범위 시험**: 랩실 조사에서 "글 정리본이 없는 영상이라 못 봤다"는 일이 한 달에 3번 이상 쌓이면 시험을 시작합니다. 세는 방법과 기록할 곳은 사용자와 함께 정해야 합니다.

## 확인 못 한 것

- 원본 `setup.py --check`가 네트워크에 접속하거나 파일을 쓰는지는 확인하지 못했습니다.
- ffmpeg `-vsync` 고장이 0.3.0에서 정말 고쳐졌는지 확인하지 못했습니다. 변경 기록은 고쳤다고 하는데, 그 뒤에도 같은 이슈가 열렸습니다. 출처끼리 엇갈립니다.
- 원본 열린 이슈의 둘째 페이지 25개는 보지 못했습니다.
- 맥스 요금제 세션 한도의 토큰 수는 공식 수치가 없어 비율로 환산하지 못했습니다.
- 한국어 영상의 자막 토큰 수는 실측하지 못했습니다(위 표는 영어 영상 기준을 옮긴 것).
- claude-real-video의 최근 커밋은 커밋 화면에서 2026-07-03까지만 보였습니다. 이후 활동이 다른 브랜치에 있는지는 확인하지 못했습니다.
- claude-video-vision의 'Gemini 무료 하루 1500회'는 저장소 설명에 있는 값입니다. 현재 구글 요금표로 확인하지 않았습니다.
- mdc159/watch의 정체는 페이지가 사라져서 확인하지 못했습니다.
- 원본의 Gemini 엔진이 유튜브 주소를 구글에 넘길 때 유튜브 약관상 문제가 덜한지에 대한 공식 근거는 찾지 못했습니다.
- 세 도구 모두 실제 사용자가 정확도를 평가한 독립 후기는 찾지 못했습니다.
