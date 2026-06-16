# 카카오+클로드 EP1 — 에셋 맵

> 이 파일이 진실의 원천. 영상 만들기 전 여기서 체크.
> MP4 파일은 gitignore — 로컬에만 존재.

---

## 📁 productions/kakao_ep1/

```
kakao_ep1/
│
├── ASSET_MAP.md                    ← 이 파일 (전체 체크리스트)
│
├── 01_veo/                         🟦 Veo AI여자 클립 + Remotion 오버레이 (씬 2개)
│   ├── intro/                      ── 씬1: AI여자 인트로 (4클립 × 8초 = 32초)
│   │   ├── veo_intro_1.mp4         [ ] "방금 이 카톡, 제가 보낸 거 아니에요..."     → 카카오 메시지 목업 슬라이드인
│   │   ├── veo_intro_2.mp4         [ ] "요즘 주식 좀 한다는 분들, GPT 잘 안 써요..." → GPT ✗ → Claude ✓ 전환
│   │   ├── veo_intro_3.mp4         [ ] "딱 10분만 투자하면 내일 아침부터..."         → "10분" 타이머 + 체크 3개
│   │   └── veo_intro_4.mp4         [ ] "방금까지 설명한 저, 사실 클로드가 만든 AI예요..." → "AI GENERATED" 리빌 + 글리치
│   └── outro/                      ── 씬2: AI여자 아웃트로 (4클립 × 8초 = 32초)
│       ├── veo_outro_a.mp4         [ ] "방금 보신 이 카톡 브리핑..."                 → 카카오 브리핑 재등장 (수미상관)
│       ├── veo_outro_b.mp4         [ ] "한 번 만들어두면 내일도 모레도..."            → 자동 반복 루프 아이콘
│       ├── veo_outro_c.mp4         [ ] "진짜 핵심은 다음 편이에요..."                → "EP.2 COMING" 예고 배너
│       └── veo_outro_d.mp4         [ ] "근데 그건 오늘 이 기본편을 세팅해둬야..."    → 구독 버튼 펄스 애니메이션
│   (TSX: KK_Veo_Intro.tsx / KK_Veo_Outro.tsx — 오푸스 설계 필요)
│
├── 02_face/                        🟡 발표자 얼굴 녹화 (네 카메라)
│   ├── s02_face.mp4                [ ] S2 페인포인트 나레이션 (~22초)
│   └── s03_face.mp4                [ ] S3 철학 나레이션 (~40초)
│
├── 03_screen/                      🟢 화면 녹화 (OBS or 캡컷)
│   ├── cold_open.mp4               [ ] 콜드오픈: 폰에 카톡 브리핑 오는 화면 (2초, 무음)
│   ├── s05_screen.mp4              [ ] S5 Claude 설치 과정
│   ├── s07_screen.mp4              [ ] S7 PlayMCP 연동
│   ├── s08_screen.mp4              [ ] S8 프롬프트 입력
│   ├── s09_screen.mp4              [ ] S9 플러그인 패키징
│   └── s10_screen.mp4              [ ] S10 예약 작업 설정
│
├── 04_remotion/                    🔴 Remotion 렌더 결과 (자동 생성)
│   ├── s04_roadmap.mp4             [ ] S4 5단계 로드맵 (미제작)
│   ├── s06_mcp.mp4                 [✓] S6 MCP 개념 ← KK_S6_MCP.tsx 완성
│   ├── s11_apply.mp4               [ ] S11 응용 (미제작)
│   ├── transition_ai2me.mp4        [ ] 전환컷 0.7s AI→나 (오푸스 설계 필요)
│   └── transition_me2ai.mp4        [ ] 전환컷 0.7s 나→AI (오푸스 설계 필요)
│
├── 05_audio/                       🎤 Whisper 전사 결과
│   ├── s02_whisper.json            [ ] s02_face.mp4 Whisper 후 생성
│   ├── s03_whisper.json            [ ] s03_face.mp4 Whisper 후 생성
│   ├── s05_whisper.json            [ ] s05_screen.mp4 Whisper 후 생성
│   ├── s07_whisper.json            [ ]
│   ├── s08_whisper.json            [ ]
│   ├── s09_whisper.json            [ ]
│   └── s10_whisper.json            [ ]
│
└── 06_final/                       🎬 최종 합본
    ├── concat.txt                  [ ] ffmpeg 입력 목록 (렌더 직전 소넷이 작성)
    └── kakao_ep1_final.mp4         [ ] 완성본
```

---

## 📁 remotion-stock/public/kakao/ep1/   (Remotion이 읽는 경로)

```
kakao/ep1/
├── s02_face.mp4                    [ ] ← 02_face/s02_face.mp4 복사
├── s03_face.mp4                    [ ] ← 02_face/s03_face.mp4 복사
├── s05_screen.mp4                  [ ] ← 03_screen/s05_screen.mp4 복사
├── s06_bg.mp4                      [ ] S6 배경 (선택 — 없으면 검정)
├── s07_screen.mp4                  [ ] ← 03_screen/s07_screen.mp4 복사
├── s08_screen.mp4                  [ ] ← 03_screen/s08_screen.mp4 복사
├── s09_screen.mp4                  [ ] ← 03_screen/s09_screen.mp4 복사
└── s10_screen.mp4                  [ ] ← 03_screen/s10_screen.mp4 복사
```

> 💡 productions/kakao_ep1/ = 원본 보관 창고
>    remotion-stock/public/kakao/ep1/ = Remotion 작업장 (같은 파일 복사)

---

## 📋 TSX 현황 (Remotion 코드)

| 씬 | TSX 파일 | 상태 | 읽는 영상 |
|---|---|---|---|
| **Veo 인트로** | KK_Veo_Intro.tsx | ❌ 오푸스 설계 필요 | ep1/veo_intro_1~4.mp4 |
| **Veo 아웃트로** | KK_Veo_Outro.tsx | ❌ 오푸스 설계 필요 | ep1/veo_outro_a~d.mp4 |
| **전환컷** | KK_Transition.tsx | ❌ 오푸스 설계 필요 | 없음 (순수 그래픽) |
| S2 페인포인트 | KK_S2_L30.tsx | ✓ 완성 (SUBS 재싱크 필요) | ep1/s02_face.mp4 |
| S3 철학 | KK_S3_L30.tsx | ✓ 완성 (SUBS 재싱크 필요) | ep1/s03_face.mp4 |
| S4 로드맵 | — | ❌ 미제작 | 없음 (순수 그래픽) |
| S5 PiP | KK_S5_PiP.tsx | ✓ 완성 (SUBS 재싱크 필요) | ep1/s05_screen.mp4 |
| S6 MCP | KK_S6_MCP.tsx | ✓ 완성 (SUBS 재싱크 필요) | ep1/s06_bg.mp4 |
| S7 PlayMCP | — | ❌ 미제작 | ep1/s07_screen.mp4 |
| S8 프롬프트 | — | ❌ 미제작 | ep1/s08_screen.mp4 |
| S9 플러그인 | — | ❌ 미제작 | ep1/s09_screen.mp4 |
| S10 스케줄 | — | ❌ 미제작 | ep1/s10_screen.mp4 |
| S11 응용 | — | ❌ 미제작 | 없음 (순수 그래픽) |

---

## 🚀 작업 순서

```
1. 네가 녹화       → 02_face/, 03_screen/ 채우기
2. Veo 생성        → 01_veo/ 채우기
3. Whisper 실행    → 05_audio/ 채우기
4. TSX SUBS 업데이트 → 소넷이 처리
5. Remotion 렌더   → 04_remotion/ 채우기 + kakao/ep1/ 복사
6. ffmpeg concat   → 06_final/ 완성
```
