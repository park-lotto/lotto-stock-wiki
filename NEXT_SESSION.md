# NEXT_SESSION
날짜: 2026-06-16 | PC: 집PC (오푸스 세션 → 소넷 이어받기)

## 세션 요약
카카오클로드 영상 제작 구조 전면 재설계 + v7 대본 확정.
1) theme.ts + SceneBase.tsx 공통 인프라 생성 → 신규 씬 350줄→80줄
2) KK_S6_MCP.tsx (MCP 개념 설명, 900f) 완성
3) KK_S6_TEMPLATE.tsx (신규 씬 스타터 템플릿) 생성
4) v7 대본 확정: 3레인 구조 + Veo 8초 클립 공식 + 북엔드 AI여자 앵커

## ✅ 완료
- `remotion-stock/src/kakao/theme.ts` — 공통 컬러 + 애니메이션 헬퍼
- `remotion-stock/src/kakao/SceneBase.tsx` — 공통 베이스 래퍼 (비디오+그래디언트+자막바)
- `remotion-stock/src/kakao/KK_S6_MCP.tsx` — S6 MCP 개념 씬 (900f, 4페이즈)
- `remotion-stock/src/kakao/KK_S6_TEMPLATE.tsx` — 재사용 템플릿
- `remotion-stock/src/Root.tsx` — Kakao-S6-MCP 컴포지션 등록
- `channel/yt/yt_카카오클로드_대본_v7.md` — **최종 확정 대본**
  - 콜드오픈(2초 무음) + 인트로 Veo 4클립(32s) + 본론 S2~S11 + 아웃트로 Veo 4클립(32s)
  - 음절 공식: 한국어 5음절/초 → 8초 클립 = 최대 43음절
  - Clip 4 AI 리빌: "방금까지 설명한 저, 사실 클로드가 만든 AI예요. 이제 클로드가 만드는 주식 자동화, 그 첫 단계 들어보세요."
  - 아웃트로 구독 명분: "다음 편이 진짜인데 오늘 걸 세팅해둬야 따라온다" (선행조건+FOMO)
- 레퍼런스 영상 분석 완료: Claude Code × HyperFrames 구조 확인

## ❌ 미완료 / 다음 할 것

### 🧑 사용자가 해야 할 것 (이게 먼저)
1. **콜드오픈 소재** — 폰에 브리핑 카톡 오는 화면 2초 녹화
2. **Veo 클립 8개** — v7 대본 그대로 각 8초 (인트로 1·2·3·4 / 아웃트로 A·B·C·D)
3. **화면 녹화 5개** — S5(설치)·S7(연동)·S8(프롬프트)·S9(플러그인)·S10(스케줄)

### 🔴 오푸스 1회 창의 작업 (소넷 못하는 것)
1. **전환컷(0.7s) "룩" 디자인** — AI여자 → 사용자 화면 전환 컴포넌트
2. **AI여자 라벨/오버레이 컨셉** — "STOCK BRAIN AI" 배지 디자인

### ⚙️ 소넷 반복 작업 (이어서 바로 시작 가능)
1. 본론 S2~S11 대사 최종 다듬기 (v7 톤 기준)
2. S6 씬 렌더 확인 (s6scene.mp4 필요 — 녹화 후)
3. Veo·녹화본 Whisper 싱크 → SUBS 배열 교체
4. S4 로드맵 씬 (KK_S6_TEMPLATE.tsx 복제 + 데이터 채우기)
5. Root.tsx 신규 컴포지션 등록
6. 렌더 + ffmpeg concat

## 관련 파일
- `channel/yt/yt_카카오클로드_대본_v7.md` — **최종 대본 (소넷 레퍼런스)**
- `remotion-stock/src/kakao/theme.ts` — 공통 인프라
- `remotion-stock/src/kakao/SceneBase.tsx` — 공통 베이스
- `remotion-stock/src/kakao/KK_S6_MCP.tsx` — S6 완성본
- `remotion-stock/src/kakao/KK_S6_TEMPLATE.tsx` — 신규 씬 템플릿
- `remotion-stock/src/Root.tsx` — 컴포지션 등록

## 3레인 구조 요약 (빠른 참고)
| 레인 | 방식 | 목소리 | 씬 |
|---|---|---|---|
| 🟦 AI | Veo 8초 클립 | AI여자(앵커) | 인트로·아웃트로 |
| 🟡 오버레이 | 네 영상+리모션 | 너 | S2·S3 |
| 🟢 화면녹화 | 실화면+PiP | 너 | S5·S7·S8·S9·S10 |
| 🔴 리모션 | 순수 그래픽 | 너/무음 | S4·S6·S11·전환컷 |
