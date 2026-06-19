# ⚡ NEXT SESSION — 카카오EP1 리모션 LIFE 3.0 재설계

> 날짜: 2026-06-19 / PC: 회사PC / 다음: 집PC에서 이어서

## 🎯 지금 하는 일
카카오×클로드 EP1 영상의 Remotion을 **LIFE 3.0 PICTURES 스타일**로 전면 재설계 중.
레퍼런스: `C:\Users\TheRose\Desktop\레퍼런스` (11장) — 검정 무대 + Claude 오렌지 + STOCKBRAIN 라임.

## 📐 기준 문서 (집PC에서 먼저 읽기)
- `productions/kakao_ep1/DESIGN.md` ← **전체 디자인 시스템 (단일 기준)**
- `remotion-stock/src/kakao/life.tsx` ← LIFE 3.0 공용 컴포넌트 (Stage/Kicker/BrowserFrame/StepBar/MarginCallout/LifeSubBar/ClaudeIcon 등)

## 3가지 씬 모드 (DESIGN.md §1)
- 🟠 모드A AI영상: 호스트 얼굴 안 가림 + 모서리 플로팅 카드
- 🔵 모드B 튜토리얼: 화면녹화 위 그래픽 금지 + 밝게. **풀스크린 액션줌 방식 채택**
- ⚫ 모드C 리모션단독: 검정 무대 + 큰 Claude CI 그래픽

## ✅ 완료 (확정)
- **인트로** `KK_Veo_Intro.tsx` (917f) — Whisper 15세그 자막 + 음성정렬 카드 4클립. 확정 ✅
- **아웃트로** `KK_Veo_Outro.tsx` (920f) — Whisper 14세그 자막 + 결과/자동반복/다음편예고/구독CTA. 확정 ✅
- **S5 튜토리얼** `KK_S5_PiP.tsx` (2545f) — **풀스크린 액션줌 v3**. Whisper 23세그 1:1 싱크 + 단계전환컷 + $19카드.
  - 렌더 결과: `out/s5_actionzoom.mp4` (집PC에서 보고 줌세기/포커스 확정 필요)
- Whisper 신규 추출: `_audio/INTRO_timestamps.json`, `OUTRO_timestamps.json`
- 샘플 3종(A/B/C): `src/kakao/samples/` — 디자인 방향 컨펌용

## ⏭ 다음 할 일 (집PC)
1. **S5 액션줌 최종 컨펌** — 줌 세기(현 1.3~1.55배)·포커스 위치(특히 코워크탭 좌상단) 조정
2. **나머지 튜토리얼 씬에 액션줌 적용**: S7(4295f)·S8(1585f)·S9(1412f)·S10(1308f)·S2(1191f)
   - 각 씬 Whisper JSON(`_audio/S0X_timestamps.json`)에 자막 1:1 싱크 필수 (의역·병합 금지)
   - 줌 키프레임(KF/FX/FY/SC) + 단계전환컷 패턴은 KK_S5_PiP.tsx 복제
3. **모드C 리모션단독 재설계**: S3(철학)·S6(MCP)·S11(응용) + 채널스팅 — life.tsx Stage 기반
4. 전체 합본 `KK_EP1_Full` 점검 → ffmpeg concat

## ⚠️ 중요 메모
- **자막 = Whisper JSON 1:1**. 절대 의역/병합 금지 (S5에서 누락사고 있었음 → 원문 복원함)
- 채널명 = **STOCKBRAIN** (로또의 주식인사이트 전부 교체 완료)
- 카드는 **실제 음성 프레임**에 맞춰야 함 (먼저 뜨고 먼저 사라지는 문제 주의)
- 녹화 MP4는 git 제외(로컬 전용). 집PC에 아래 파일 있어야 렌더 가능:
  - `remotion-stock/public/kakao/ep1/`: intro.mp4, outro.mp4, s02~s11 (bg/audio)
  - 없으면 `productions/kakao_ep1/{씬}/`에서 복사 후 각 TSX의 BG/audio 경로 확인

## 미리보기
- Studio: `cd remotion-stock && npx remotion studio` → KKEP1-VeoIntro / VeoOutro / S5
- 샘플: KKEP1-SAMPLE-A-AI / B-TUT / C-SOLO
