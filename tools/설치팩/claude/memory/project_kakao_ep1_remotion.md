---
name: project_kakao_ep1_remotion
description: 카카오EP1 Remotion LIFE 3.0 재설계 — 3씬모드·life.tsx·액션줌 튜토리얼
metadata: 
  node_type: memory
  type: project
  originSessionId: 6ee19e17-5c9b-4033-a8f4-65342e11106f
---

카카오×클로드 EP1 영상 Remotion을 **LIFE 3.0 PICTURES 스타일**로 재설계 중 (2026-06-19 시작, 회사PC→집PC).

**기준 문서**: `productions/kakao_ep1/DESIGN.md` (단일 기준) + `remotion-stock/src/kakao/life.tsx` (공용 컴포넌트).

**3가지 씬 모드**:
- 🟠 모드A AI영상(인트로/아웃트로): 호스트 얼굴 안 가림 + 모서리 플로팅 카드
- 🔵 모드B 튜토리얼(화면녹화): 화면 위 그래픽 금지 + 밝게. **풀스크린 액션줌** 채택 (단계별 줌인 + 전환컷)
- ⚫ 모드C 리모션단독: 검정 무대 + 큰 Claude CI(오렌지 #D97757) 그래픽

**컬러**: Claude 오렌지 #D97757(제품·신뢰) + STOCKBRAIN 라임 #AAFF00(데이터·강조) + 검정 무대 + 레드 #FF4455 베이스라인.

**완료**: 인트로·아웃트로·S5·**S7·S8·S9·S10·S2 액션줌**(튜토리얼 전부) + **S3 모드C 골든레퍼런스**(KK_S3_L30 2404f).
**다음(집PC)**: S3 Studio 톤확정 → S4·S6·S11·ColdOpen·ChannelSting·EndSting 모드C(S3 패턴 복제).

**모드C 규칙 (S3에서 확립, 사용자 피드백)**:
- **WireGlobe(지구본) 금지** — 베낀 느낌. 추상 ambient(FlowField=흐르는 흐름선+부유광점)로.
- **대사 이탈 0** — 자막 한 줄마다 중앙 그래픽 호응, 빈 구간 없게 비트 세분.
- **카드는 자막 프레임 싱크** + **내용 계속 추가** + 역동(정적 금지).

**철칙**:
- 자막은 Whisper JSON에 **1:1 정렬**. 의역·병합 금지. (긴 세그만 프레임비례 분할 OK)
- `shake()`는 `{x,y}` 반환 → `translate(x,y)`로 써야 (translateX에 객체째 넣으면 무효, S8/S9/S2 버그였음).
- S2 영상 실제 1752f (기존 1191f는 오류였음). 자막 비면 Whisper medium+word_timestamps 재전사(Sonnet 위임).
- 채널명 = **STOCKBRAIN**. 녹화 MP4는 git 제외.

상세 진행상황은 항상 `NEXT_SESSION.md` 참조. [[feedback_remotion_style]] [[project_remotion_effects]]
