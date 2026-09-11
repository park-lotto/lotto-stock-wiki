---
name: silent-fallback-pipeline-undo
description: "믹스 \"쳇바퀴\" 뿌리 패턴 — 조용한 폴백 + 뒷단계가 앞단계 되돌림. 개선이 안 먹히면 먼저 \"어느 경로가 실제로 돌았나\" 실측"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7ce7ffe1-2a07-4052-a7e6-9e49296ff07c
  modified: 2026-07-24T02:21:12.600Z
---

쇼핑쇼츠 믹스에서 "고쳤는데 또 그대로" 재발의 공통 뿌리(2026-07-24 실측 확정, 4건 전부 같은 모양):

1. **조용한 폴백**: scene_first가 Gemini 503에 죽으면 재시도 없이 옛 build_edit_plan로 몰래 폴백 → 개선(30초·7~8컷·대화)이 통째로 안 탄 결과가 나옴. 사용자는 "강제가 안 되나"로 인식.
2. **뒷단계가 앞단계 되돌림**: dedup은 plan에서 돌았는데 TTS후 _refill_beats_to_tts의 fill이 비트내 중복만 봐서 반복 부활([[freeze-whackamole-root]]와 동형).
3. **결정성 없는 렌더**: TTS seed None → 설정 그대로인데 렌더마다 딴 목소리.
4. **falsy 가드가 기능 통째로 죽임**: `if category`가 빈 문자열에 스파인 pick 자체를 스킵 → 승인 스파인 4개가 조용히 사장.

**Why**: 파이프라인이 다단계·다경로인데 실패·우회·역전이 전부 조용해서, 유효한 수정이 "안 탄 경로"에 가려짐.

**How to apply**:
- "개선이 안 먹혔다" 제보 → 코드 더 고치기 전에 **그 job이 실제 탄 경로부터 실측**(candidates_json 유무, 서버 로그의 폴백/503, voice_json 스냅샷).
- 구조 처방: ①조용한 폴백 금지(생성기 배지·실패 명시 노출) ②렌더 직전 최종 plan 불변식 게이트(전역반복 0·비트수·길이) — 2026-07-24 P1/P2로 제안, 사장님 승인 대기.
- 일시 에러(503/UNAVAILABLE)는 모든 Gemini 콜에서 재시도해야 함 — 한 곳(_vault_call)만 고치면 다른 콜에서 같은 병 재발.
