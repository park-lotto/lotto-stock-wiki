# 카카오EP1 — Opus TSX 제작 브리프
> 작성: 소넷 | 고도화: 오푸스 (2026-06-19) | 목적: 전체 TSX 제작 지시서

---

# ★ v2 — 오푸스 디자인 바이블 (확정)

## A. 비주얼 아이덴티티 (전 씬 통일)

| 요소 | 값 |
|------|-----|
| 캔버스 | 1920×1080 · 30fps |
| 배경 | 순수 검정 `#000` |
| 1차 강조 | LIME `#AAFF00` + 글로우 |
| 대비/경고 | RED `#FF4455` |
| 카드 | `rgba(0,0,0,0.84)` + LIME 보더 `rgba(170,255,0,0.45)` |
| 한글 폰트 | `'Noto Sans KR'` (700/900) — load-font.ts에 로드됨 |
| 모노 | `'Roboto Mono'`/`'Courier New'` (라벨·코드·키커) |
| 자막바 | SceneBase 내장 — 하단 17%, 등장 시 rise+fade 애니 |

## B. 모션 어휘 (kakao/fx.tsx 공통 헬퍼)

| 이름 | 용도 | 스펙 |
|------|------|------|
| `pop(f,start)` | 카드·아이콘 등장 | spring damping9 stiff260 |
| `riseFade(f,start)` | 텍스트 줄 등장 | y 18→0, opacity 0→1, 14f |
| `zoomPunch(f,start)` | 핵심 단어 강조 | scale 1→1.08→1, 10f |
| `shake(f,start,dur)` | 경고·임팩트 | translate ±amp 감쇠 |
| `flashAt(f,start)` | 컷 전환 플래시 | 흰 화면 6f |
| `glitchX(f,a,b)` | 글리치 흔들림 | sin 기반 x 오프셋 |
| `typeReveal(txt,f,start,cps)` | 타이핑 | 글자수 기반 substring |

## C. 전환·돋보임 효과 (기존 자산 재사용)

- **DocHighlight** (`scenes/DocumentHighlightScene`) — 화면녹화 특정 영역 형광펜+줌 → S5·S7·S8
- **FocusZoom** (`scenes/FocusZoomScene`) — 블러 배경+카드 확대 → S3·S8·S11
- **ClickPulse** (fx.tsx 신규) — 클릭 위치 빨간 ripple → PiP 씬 전부
- **StepProgress** (fx.tsx 신규) — 상단 단계 진행바 → S7
- **채널스팅** — 씬군 사이 0.7s 글리치 로고 플래시

## D. SFX 매니페스트 (`public/sfx/` · ffmpeg 생성 완료)

| 파일 | 용도 | 기본 볼륨 |
|------|------|----------|
| `sting_hit.mp3` | 스팅 로고 임팩트 | 0.5 |
| `sting_whoosh.mp3` | 스팅 진입/퇴장 | 0.4 |
| `transition_swipe.mp3` | 씬 전환 | 0.4 |
| `pop_appear.mp3` | 카드·텍스트 팝업 | 0.35 |
| `tick.mp3` | 체크·타이핑·스텝 | 0.3 |
| `impact.mp3` | 핵심 단어·경고 | 0.45 |
| `kakao_ding.mp3` | 카톡 알림 (cold open·S7·S9) | 0.5 |
| `chime_up.mp3` | 완료·성공 | 0.45 |
| `end_whoosh.mp3` | 마무리 페이드 | 0.4 |

> SFX는 ffmpeg 합성 플레이스홀더 — 추후 고품질 음원으로 교체 가능 (파일명만 유지).
> 사용법: `<Sfx at={frame} file="pop_appear.mp3" vol={0.35} />` (fx.tsx)

## E. 길이 확정표 (durationInFrames)

| 씬 | 프레임 | 근거 |
|----|--------|------|
| ChannelSting | 21 | 0.7s 스팅 |
| EndSting | 110 | 3.7s 엔딩 |
| Veo_Intro | 916 | intro.mp4 실측 |
| ColdOpen | 60 | 2s 훅 |
| S2 | 1191 | 영상 39.7s (무음·수동 타임라인) |
| S3 | 2404 | Whisper |
| S4 | 322 | Whisper |
| S5 | 2545 | Whisper |
| S6 | 1952 | Whisper |
| S7 | 4295 | Whisper |
| S8 | 1585 | Whisper |
| S9 | 1412 | Whisper |
| S10 | 1308 | Whisper |
| S11 | 744 | Whisper |
| Veo_Outro | 920 | outro.mp4 실측 |

## F. 실제 에셋 반영 정정사항

- S2·S3 = 발표자/녹음 영상 배경 / S5·S7·S8·S9·S10 = **화면녹화(음성포함) 영상 배경**
  → 별도 얼굴 PiP 캠 없음. "화면녹화 배경 + 그래픽 오버레이" 방식으로 통일.
- 파일명은 브리프 유지(`KK_S5_PiP` 등)하되 **구현은 풀스크린 배경 + 오버레이**.
- 영상 에셋은 `public/kakao/ep1/sXX_bg.mp4` 경로 참조 (소넷이 복사). 미존재 시 SceneBase가 플레이스홀더 배경 표시.

---

## 핵심 원칙

- **Whisper JSON 기준이 진실** — 모든 FRAMES 값은 `_audio/{SCENE}_timestamps.json`의 `total_frames` 사용
- **기존 TSX(S2·S3·S5·S6) 전부 버리고 새로 짠다** — 추정치로 만들어져서 실제 녹화와 안 맞음
- **SceneBase + theme.ts 인프라 그대로 활용** — 새 컴포넌트 만들지 말 것
- **자막(SUBS)은 Whisper JSON의 start_frame/end_frame 그대로** — 수동 추정 금지
- **참고 파일**: `remotion-stock/src/kakao/KK_S6_MCP.tsx` (가장 완성된 예시)
- **템플릿**: `remotion-stock/src/kakao/KK_S6_TEMPLATE.tsx`

---

## 인프라 (건드리지 말 것)

```
remotion-stock/src/kakao/
├── SceneBase.tsx   ← video + subs + children(f) 패턴
├── theme.ts        ← LIME·CARD·BORDER·ci·sp·panelOp·slideX
├── KK_S6_MCP.tsx   ← 레퍼런스
└── KK_S6_TEMPLATE.tsx ← 시작 템플릿
```

**색상 팔레트**: 검정 배경 + LIME(#AAFF00) 강조 + 흰 텍스트  
**자막바**: SceneBase 내장 — subs 배열만 넣으면 자동 렌더  

---

## 씬별 제작 지시

---

### 00_cold_open — KK_ColdOpen.tsx

- **타입**: 순수 Remotion (실제 녹화 아직 없음 → Remotion으로 구현)
- **길이**: 60f (2초)
- **대본**: 나레이션 없음. 폰 화면 클로즈업 → 카톡 알림 '딩' → 아침 브리핑 메시지 촤르륵
- **Whisper**: 없음 (무음)
- **연출 지시**:
  - 검정 배경 → 폰 실루엣 페이드인
  - 카톡 알림 팝업 바운스 등장 (LIME 테두리)
  - 텍스트: "📱 아침 브리핑 도착" → 자르르 타이핑 효과
  - 훅용 — 시청자 손가락 멈춰야 함. 임팩트 최우선.

---

### S02 — KK_S2_PiP.tsx (기존 KK_S2_L30 교체)

- **타입**: 무음 화면녹화 배경 + Remotion 텍스트 오버레이
- **길이**: 1191f (39.7초 × 30)
- **대본**: 아래 텍스트를 10~12초 간격으로 순차 등장
  ```
  매일 아침 주식러의 하루
  폰부터 잡는다 → 야간선물 확인 → 미국장 체크 → 종목뉴스 뒤지기
  → 텔레그램·유튜브 보다 보면 어느새 8시
  → 장 열릴 땐 이미 지쳐 있다
  → 결국 뇌동매매로 하루 시작
  해결책: 이걸 클로드한테 통째로 맡긴다
  ```
- **Whisper**: 없음 (무음 화면녹화)
- **연출 지시**:
  - 배경: OffthreadVideo `kakao/ep1/s02_screen.mp4` (화면녹화)
  - 각 카드 슬라이드인 → 일정 시간 유지 → 페이드아웃
  - 마지막 카드만 LIME 강조

---

### S03 — KK_S3_L30.tsx (기존 교체)

- **타입**: 발표자 얼굴 배경 + Remotion 텍스트 그래픽 오버레이
- **길이**: **2404f** (`_audio/S03_timestamps.json` → total_frames)
- **Whisper 세그 25개** → `_audio/S03_timestamps.json`에서 SUBS 그대로 복사
- **대본 키포인트**:
  - AI가 타점 잡아준다는 환상 → 파괴
  - AI가 1% 부족한 인간의 도움이 필요
  - 주식 = 살아있는 생물, 인간의 광기
  - 내가 하는 것 = 정보수집·요약 자동화
  - 핵심: 오늘 주도섹터·돈의 흐름에만 집중하자
- **연출 지시**:
  - 배경: OffthreadVideo `kakao/ep1/s03_bg.mp4` (발표자 얼굴)
  - Phase 1 (~800f): AI 환상 파괴 카드 (빨간 X 아이콘 포함)
  - Phase 2 (800f~1800f): "내가 자동화하는 것" 리스트 등장
  - Phase 3 (1800f~2404f): "이제 집중할 것" 임팩트 텍스트

---

### S04 — KK_S4_Roadmap.tsx

- **타입**: 순수 Remotion
- **길이**: **322f** (`_audio/S04_timestamps.json`)
- **Whisper 세그 3개** → SUBS 복사
  ```
  f0~   오늘 할 거 딱 5단계입니다.
  f?~   길게 안 끌고 10분 안에 끝내드릴게요.
  f?~   코딩 같은 거 한 줄도 없으니까 편하게 따라오세요.
  ```
- **연출 지시**:
  - 5단계 스텝 카드가 순서대로 등장 (스텝별 2~3초 간격)
  - 각 스텝 번호 크게, 설명 작게
  - 5단계 내용:
    1. Claude 데스크탑 설치
    2. PlayMCP 연결
    3. 프롬프트 작성
    4. 플러그인 패키징
    5. 예약 자동화
  - 마지막에 5개 전부 동시에 보이는 완성형 화면

---

### S05 — KK_S5_PiP.tsx (기존 교체)

- **타입**: PiP (왼쪽 = 화면녹화, 오른쪽 = 발표자 얼굴)
- **길이**: **2545f** (`_audio/S05_timestamps.json`)
- **Whisper 세그 23개** → SUBS 복사
- **대본 키포인트**:
  - Claude 데스크탑 구글 검색 → 다운로드 → 설치
  - 좌측 상단 코워크 탭 확인
  - 무료엔 자동화 없음 → 월 19달러(3만원) 필요
  - "주식 손실에 비하면 3만원은 아무것도 아니다"
- **연출 지시**:
  - 배경 좌측 60%: `kakao/ep1/s05_screen.mp4` (화면녹화)
  - 우측 40%: `kakao/ep1/s05_face.mp4` (발표자) — 없으면 placeholder
  - 화면 특정 구간에 빨간 동그라미/화살표 오버레이 (클릭 위치 표시)
  - "월 3만원" 구간에서 LIME 강조 카드 팝업

---

### S06 — KK_S6_MCP.tsx (Whisper 교체만)

- **타입**: 순수 Remotion (기존 TSX 구조 유지, SUBS·FRAMES만 교체)
- **길이**: **1952f** (`_audio/S06_timestamps.json`)
- **Whisper 세그 8개** → SUBS 교체
- **기존 KK_S6_MCP.tsx 그래픽 구조(충전기→USB-C→PlayMCP) 그대로** — SUBS와 FRAMES만 실제값으로 바꿈

---

### S07 — KK_S7_PiP.tsx

- **타입**: PiP (왼쪽 화면녹화 + 오른쪽 발표자)
- **길이**: **4295f** (`_audio/S07_timestamps.json`) ← 가장 긴 씬 (143초)
- **Whisper 세그 44개** → SUBS 복사
- **대본 키포인트**:
  - PlayMCP 구글 검색 → 카카오 로그인
  - 카카오 나채팅방 MCP + 네이버 MCP 도구함 추가
  - 코워크 → 플러스 → 커넥터 → PlayMCP 검색 → 연결
  - 테스트: "오늘 주식 이슈 정리해서 카톡으로 보내줘"
  - 허용 버튼 → 카톡 수신 확인
- **연출 지시**:
  - 44세그라 Phase를 5~6개로 나눠서 단계별 진행 표시 상단 Progress Bar
  - 각 단계 완료 시 체크마크 등장
  - 마지막 "카톡 왔어요!" 임팩트 카드

---

### S08 — KK_S8_PiP.tsx

- **타입**: PiP + 자막
- **길이**: **1585f** (`_audio/S08_timestamps.json`)
- **Whisper 세그 8개** → SUBS 복사
- **대본 키포인트**:
  - 프롬프트 = AI 업무 지시서
  - 종목명 적으면 기관 리포트 + 핵심뉴스 카톡 전송
  - 고정댓글에 템플릿 있음
- **연출 지시**:
  - 프롬프트 텍스트 타이핑 시각화 (모노스페이스 폰트)
  - `[종목명]` 부분 LIME 강조
  - CTA 구간: "고정댓글 확인하세요" 배너

---

### S09 — KK_S9_PiP.tsx

- **타입**: PiP + 자막
- **길이**: **1412f** (`_audio/S09_timestamps.json`)
- **Whisper 세그 7개** → SUBS 복사
- **대본 키포인트**:
  - 매일 반복 명령 → 플러그인으로 패키징
  - "브리핑이라고 만들어줘" → `/브리핑` 한 줄로 실행
- **연출 지시**:
  - Before: 긴 프롬프트 전체 → After: `/브리핑` 한 줄
  - 극적인 대비 (왼쪽 복잡 / 오른쪽 단순)

---

### S10 — KK_S10_PiP.tsx

- **타입**: PiP + 자막
- **길이**: **1308f** (`_audio/S10_timestamps.json`)
- **Whisper 세그 6개** → SUBS 복사
- **대본 키포인트**:
  - "매일 오전 7시에 아침 브리핑으로 실행해줘" 한 줄
  - 컴퓨터 켜져 있어야 함
  - 절전모드 끄기 → 화면만 꺼지게 → 전기세 걱정 없음
- **연출 지시**:
  - 예약 완료 카드 (시계 아이콘 + 오전 7:00 LIME)
  - 전기세 걱정 → 안심 카드

---

### S11 — KK_S11_Apply.tsx

- **타입**: 순수 Remotion
- **길이**: **744f** (`_audio/S11_timestamps.json`)
- **Whisper 세그 4개** → SUBS 복사
- **대본 키포인트**:
  - "이 구조만 익히면 응용은 무궁무진"
  - 4가지 응용: 아침브리핑 / 개별종목브리핑 / 주간핵심일정 / 장중매시간브리핑
  - 고정댓글에 프롬프트 4개 올려둠
  - 잘 활용해 보세요. 감사합니다.
- **연출 지시**:
  - 4가지 카드 순차 등장 (각 카드에 아이콘 + 제목)
  - 마지막: 전체 4개 동시 + "고정댓글 ↓" CTA
  - 엔딩 느낌 — 따뜻하고 마무리 감 있게

---

## Whisper JSON 경로

```
productions/kakao_ep1/_audio/
├── S03_timestamps.json   (2404f / 25세그)
├── S04_timestamps.json   (322f  /  3세그)
├── S05_timestamps.json   (2545f / 23세그)
├── S06_timestamps.json   (1952f /  8세그)
├── S07_timestamps.json   (4295f / 44세그)
├── S08_timestamps.json   (1585f /  8세그)
├── S09_timestamps.json   (1412f /  7세그)
├── S10_timestamps.json   (1308f /  6세그)
└── S11_timestamps.json   (744f  /  4세그)
```

JSON 포맷:
```json
{
  "total_frames": 2404,
  "segments": [
    { "index": 1, "text": "...", "start_frame": 0, "end_frame": 118 },
    ...
  ]
}
```

## 전체 영상 구조 (최종 확정)

```
① KK_ChannelSting.tsx     ← 오프닝 스팅 (채널 로고 임팩트)
② KK_Veo_Intro.tsx        ← AI 영상 (Veo 인트로 4클립 + 오버레이)
③ KK_ChannelSting.tsx     ← 중간 전환 스팅 (AI→사람)
④ KK_ColdOpen.tsx         ← 사람 영상 시작 (카톡 알림 2초)
   KK_S2_PiP.tsx
   KK_S3_L30.tsx
   KK_S4_Roadmap.tsx
   KK_S5_PiP.tsx
   KK_S6_MCP.tsx
   KK_S7_PiP.tsx
   KK_S8_PiP.tsx
   KK_S9_PiP.tsx
   KK_S10_PiP.tsx
   KK_S11_Apply.tsx        ← 사람 영상 끝
⑤ KK_ChannelSting.tsx     ← 전환 스팅 (사람→AI)
⑥ KK_Veo_Outro.tsx        ← AI 영상 (Veo 아웃트로 4클립 + 오버레이)
⑦ KK_EndSting.tsx         ← 마무리 스팅 (구독CTA + 엔딩)
```

> KK_ChannelSting은 ①③⑤ 총 3회 재사용.  
> KK_EndSting은 마무리 전용 — 채널스팅보다 길고 CTA 포함.

---

## 전환컷 & 스팅 (신규 추가)

---

### KK_ChannelSting.tsx — 채널 로고 스팅 (3회 재사용)

- **타입**: 순수 Remotion
- **길이**: 21f (0.7초)
- **컨셉**: TechFeed 채널이 중간에 로고 플래시 넣는 것과 동일. 짧고 강렬하게.
- **연출 지시**:
  - 검정 → 채널 로고+이름 번쩍 → 검정 컷
  - 로고: `ClaudeLogo` + "로또의 주식인사이트"
  - 효과: 글리치 or 스캔라인 플래시 (StockBrainIntro.tsx 스타일 참고)
  - 색: 검정 배경 + LIME 글로우
- **재사용**: ①오프닝 ③AI→사람 전환 ⑤사람→AI 전환

---

### KK_EndSting.tsx — 마무리 스팅 (엔딩 전용)

- **타입**: 순수 Remotion
- **길이**: 90~120f (3~4초)
- **컨셉**: 채널스팅보다 길고 CTA 포함. 영상 마지막 인상.
- **연출 지시**:
  - 채널 로고 + "로또의 주식인사이트" 풀 등장 (채널스팅보다 크고 느리게)
  - "구독" + "좋아요" + "고정댓글 확인" 3가지 CTA 순차 등장
  - 아웃트로 느낌 — 페이드아웃으로 마무리
- **삽입 위치**: Veo 아웃트로 영상 다음, 영상 맨 끝

---

### KK_Veo_Intro.tsx — Veo 인트로 오버레이

- **타입**: OffthreadVideo(intro.mp4) + Remotion 오버레이
- **길이**: intro.mp4 전체 길이에 맞춤
- **에셋**: `productions/kakao_ep1/01_veo_intro/intro.mp4` (4클립 합본, ✅ 완성)
- **연출 지시**:
  - Veo AI 영상 위에 채널명·타이틀 텍스트 오버레이
  - 하단 자막바 스타일로 "로또의 주식인사이트" 페이드인
  - 마지막 2~3초: 타이틀 카드 등장 준비

---

### KK_Veo_Outro.tsx — Veo 아웃트로 오버레이

- **타입**: OffthreadVideo(outro.mp4) + Remotion 오버레이
- **길이**: outro.mp4 전체 길이에 맞춤
- **에셋**: `productions/kakao_ep1/99_veo_outro/outro.mp4` (4클립 합본, ✅ 완성)
- **연출 지시**:
  - 구독·좋아요 CTA 오버레이 (우측 하단 고정)
  - "고정댓글에 프롬프트 4개 있어요" 텍스트 등장
  - 채널 로고 엔딩

---

## 완성 TSX 저장 위치

```
remotion-stock/src/kakao/
├── KK_ChannelSting.tsx   ← 신규 (3회 재사용)
├── KK_Veo_Intro.tsx      ← 신규
├── KK_ColdOpen.tsx       ← 신규
├── KK_S2_PiP.tsx         ← 교체
├── KK_S3_L30.tsx         ← 교체
├── KK_S4_Roadmap.tsx     ← 신규
├── KK_S5_PiP.tsx         ← 교체
├── KK_S6_MCP.tsx         ← SUBS·FRAMES만 교체
├── KK_S7_PiP.tsx         ← 신규
├── KK_S8_PiP.tsx         ← 신규
├── KK_S9_PiP.tsx         ← 신규
├── KK_S10_PiP.tsx        ← 신규
├── KK_S11_Apply.tsx      ← 신규
├── KK_Veo_Outro.tsx      ← 신규
└── KK_EndSting.tsx       ← 신규 (마무리 전용)
```

---

## 영상 에셋 경로 (remotion-stock/public/kakao/ep1/)

| 씬 | 에셋 | 상태 |
|----|------|------|
| S02 | s02_screen.mp4 | 복사 필요 |
| S03 | s03_bg.mp4 | 복사 필요 |
| S05 | s05_screen.mp4 + s05_face.mp4 | PiP용 분리 필요 |
| S07 | s07_screen.mp4 | 복사 필요 |
| S08 | s08_screen.mp4 | 복사 필요 |
| S09 | s09_screen.mp4 | 복사 필요 |
| S10 | s10_screen.mp4 | 복사 필요 |

> 🔴 에셋 복사 작업은 소넷이 별도 진행. Opus는 TSX만 집중.

---

---

## 음향·시각 효과

> **Opus가 직접 설계** — 사용자와 대화하며 씬별 효과 결정  
> Remotion Audio: `<Audio src={staticFile('sfx/파일명')} />`  
> SFX 파일 위치: `remotion-stock/public/sfx/`  
> 기존 구현된 효과: DocHighlight / FocusZoom / TechFeed (`channel/strategy/remotion_효과_레퍼런스.md` 참고)

---

## 작업 순서 권장

1. KK_ColdOpen.tsx (짧고 독립적)
2. KK_S4_Roadmap.tsx (짧고 순수 Remotion)
3. KK_S11_Apply.tsx (짧고 순수 Remotion)
4. KK_S6_MCP.tsx SUBS 교체 (기존 구조 활용)
5. KK_S2_PiP.tsx (무음이라 자막 없이 그래픽만)
6. KK_S3_L30.tsx (긴 씬)
7. PiP 씬 5개 (S05·S07·S08·S09·S10) — 구조 동일하니 하나 만들고 복제
