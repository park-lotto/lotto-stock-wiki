# NEXT_SESSION — 카카오EP1 Remotion LIFE 3.0

> 2026-06-20 · 회사PC 마감 → 집PC에서 이어서
> 기준: `productions/kakao_ep1/DESIGN.md` + `remotion-stock/src/kakao/life.tsx`

---

## ✅ 이번 세션 완료

- **S7** 카톡창 줌 수정: 2분10초(f3980~) 카카오톡 팝업 좌상단 → 화면 중앙. `transformOrigin`만으론 이동 불가 → **translate+scale** 방식(`KAKAO_CX/CY/SC`). 단, 좌표는 Studio 미세조정 필요.
- **S8/S9/S10** 액션줌 전면 재작성 (옛 SceneBase+dim 폐기): 풀스크린 줌 + 화면밖 자막 1:1 + STEP 전환카드 + 클라이맥스. 자막 ASR 교정 반영.
- **S2** Whisper medium 재전사(Sonnet 위임) → **1752f**(기존 1191f 오류 정정, 영상 실제 58.4초). 액션줌 재작성. ASR 교정: 스탑→스탁브레인, 종배→종가배팅.
- **shake 버그 수정**: `shake()`는 `{x,y}` 반환인데 S8/S9/S2가 `translateX(${shake}px)`로 객체째 넣어 무효였음 → `translate(x,y)`로 수정. (S7은 원래 정상)
- **S3 모드C 전면 재설계 = 골든 레퍼런스** (KK_S3_L30.tsx, 2404f). 컴파일 에러 0. → **집PC에서 Studio 톤 확정 먼저 받을 것**

## 🔴 미완료 (집PC에서)

### 1. S3 Studio 톤 확정 (최우선)
`KKEP1-S3` 미리보기 → FlowField·9비트·거대타이포 OK 확인. 조정 있으면 반영 후 나머지로.

### 2. 나머지 모드C 6개 재작성 (S3 패턴 그대로 복제)
순서 추천: **S4 로드맵 → S6 MCP → S11 응용 → ColdOpen → ChannelSting → EndSting**
- 모두 옛 구조(`SceneBase`/`theme`) → `life.tsx` 기반 모드C로
- 각 씬: 배경 audio/null 확인 → 자막 Whisper 1:1 → **대사 한 줄마다 비트 호응** → 거대타이포 → 역동

### 3. 튜토리얼 줌 포커스 Studio 확인
S7(카톡 중앙), S8(허용팝업/결과텍스트), S9(채팅창 FY0.55), S10(예약화면) — 화면 짤림/포커스 미세조정.

### 4. 전체 `KK_EP1_Full` concat 점검 → 최종 렌더

---

## ⚑ S3에서 확립한 모드C 규칙 (반드시 적용)

1. **지구본(WireGlobe) 금지** — 베낀 느낌. 추상 ambient(FlowField=흐르는 흐름선) 사용.
2. **대사 이탈 0** — 자막 한 줄마다 중앙 그래픽이 바뀐다. 빈 구간 없음.
3. **카드는 자막 프레임에 싱크** — 먼저 뜨거나 먼저 사라지면 안 됨.
4. **내용 계속 추가 + 역동** — 정적 3초+ 금지. shake/zoomPunch/riseFade(40)/pulse/플래시.
5. 거대 타이포: 헤드 80~110px, 수치 140~200px (40px 이하 금지).
6. 시그니처: `Stage`+`Kicker`+`Watermark`+레드베이스라인+`ClaudeIcon`. 채널명 STOCKBRAIN.
7. `shake()`는 `{x,y}` → `translate(x,y)`로 사용.

## 파일 경로
- 씬: `remotion-stock/src/kakao/KK_*.tsx` / 마스터: `KK_EP1_Full.tsx`
- 자막: `productions/kakao_ep1/_audio/S0X_timestamps.json` (+ S02/S07 `_SUBS_final.json`)
- 컴포넌트: `life.tsx`(LIFE3.0) / `fx.tsx`(모션헬퍼)
