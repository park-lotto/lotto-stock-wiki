# ⚡ NEXT SESSION — 카카오EP1 리모션 LIFE 3.0 재설계

> 날짜: 2026-06-20 / PC: 집PC / 다음: 이어서

## 🎯 지금 하는 일
카카오×클로드 EP1 영상의 Remotion을 **LIFE 3.0 PICTURES 스타일**로 전면 재설계 중.
레퍼런스: `C:\Users\TheRose\Desktop\레퍼런스` (11장) — 검정 무대 + Claude 오렌지 + STOCKBRAIN 라임.

## 📐 기준 문서
- `productions/kakao_ep1/DESIGN.md` ← 전체 디자인 시스템 (단일 기준)
- `remotion-stock/src/kakao/life.tsx` ← LIFE 3.0 공용 컴포넌트

## 3가지 씬 모드 (DESIGN.md §1)
- 🟠 모드A AI영상: 호스트 얼굴 안 가림 + 모서리 플로팅 카드
- 🔵 모드B 튜토리얼: 화면녹화 위 그래픽 금지 + 밝게. **풀스크린 액션줌 방식 채택**
- ⚫ 모드C 리모션단독: 검정 무대 + 큰 Claude CI 그래픽

## ✅ 완료 (확정)
- **인트로** `KK_Veo_Intro.tsx` (917f) ✅
- **아웃트로** `KK_Veo_Outro.tsx` (920f) ✅
- **S5 튜토리얼** `KK_S5_PiP.tsx` (2545f) — 액션줌 v3. 오늘 버그픽스:
  - 화면 짤림 수정: fy 0.42→0.52, SC 1.32→1.22 (상단 여유 확보)
  - 떨림 제거: `Math.sin` 사인파 삭제, 펀치 damping 9로 강화

## ⏭ 다음 할 일
1. **S5 Studio에서 최종 컨펌** — 줌 세기·포커스 위치 확인 (버그픽스 후 미확인)
2. **나머지 튜토리얼 씬 액션줌 적용**: S7(4295f)·S8(1585f)·S9(1412f)·S10(1308f)·S2(1191f)
   - 각 씬 Whisper JSON(`_audio/S0X_timestamps.json`)에 자막 1:1 싱크 필수
   - 줌 키프레임(KF/FX/FY/SC) + 단계전환컷 패턴은 KK_S5_PiP.tsx 복제
3. **모드C 리모션단독 재설계**: S3(철학)·S6(MCP)·S11(응용) + 채널스팅 — life.tsx Stage 기반
4. 전체 합본 `KK_EP1_Full` 점검 → ffmpeg concat

## ⚠️ 중요 메모
- **S5 줌 수치 (오늘 수정 후)**: SC=[1.22,1.26,1.30,1.22,1.48,1.35,1.06,1.06], FY=[0.52,0.54,0.55,0.58,0.12,0.12,0.5,0.5]
- **자막 = Whisper JSON 1:1**. 절대 의역/병합 금지
- 채널명 = **STOCKBRAIN**
- 녹화 MP4는 git 제외(로컬 전용). `remotion-stock/public/kakao/ep1/`에 있어야 렌더 가능

## 미리보기
- Studio: `cd remotion-stock && npx remotion studio` → KKEP1-S5
