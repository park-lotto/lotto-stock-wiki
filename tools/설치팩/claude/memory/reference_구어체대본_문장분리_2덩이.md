---
name: reference-2
description: 한국어 구어체 대본은 마침표가 거의 없다 — 마침표 기준 문장분리는 8칸 대본을 2덩이로 뭉쳐 칸에 꽂는다
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0adb7c8d-6c08-4041-8cd0-3df6efc019b1
  modified: 2026-08-20T08:51:31.352Z
---

2026-08-20 실사고 (job 087e03b69dc2, 제작소 미리보기 "자막·TTS 안 맞고 끝나면 반복").

**뿌리**: 전날 들어온 `enforce_scripted_narration`(edit_plan.py)이 "대본에 없는 문장"을
원본 대본 문장으로 되돌리는데, 문장 분리기가 `[.!?。！？]`만 봤다. 스파인이 뽑는 구어체
8칸 대본은 칸 사이가 **종결어미로만** 끊긴다("사오세요 / 스트레스였거든요 / 거예요") —
마침표가 딱 1개라 **141자·131자 2덩이로만** 잘렸고, 그게 2.9초·3.6초짜리 칸에 통째로 꽂혔다.

→ 존댓말 종결어미(요/죠)+공백도 경계로. 실증 2조각 → 8조각(원본 스파인 8칸과 일치).
→ 2차 방어: 칸 예산(`target × 5.7 × 2`)을 넘는 조각은 안 꽂고 `narration_invented` 표시.

**2차 결함(같은 사고에서 드러남)**: `mix_pipeline.resynth_one_beat`이 재합성 후
`target_seconds`를 안 고쳤다. 렌더 경로 `_conform_beats`는 하는데 대본수정 경로는 안 했다
→ 미리보기는 mp3 실길이를, 편성·화면예산은 옛 초를 따라가 **초가 두 벌**([[reference_말속도_상수_4벌]]과 같은 병).
화면이 5배 모자라 앞 장면을 되풀이 = 사장님이 본 "끝나고 계속 반복".

## 다음에 같은 제보를 받으면
- "자막이 안 맞는다 / 끝나고 반복된다" → 재생기 코드 말고 **그 job의 대본 글자수 vs mp3 실길이
  vs target_seconds 셋을 먼저 대조**하라. 셋이 어긋나 있으면 대본 쪽 사고다.
- 서버 실측 경로: DB는 `data/reference.db`(app.db 아님), 원본 대본은
  `produce_works.state_json`의 `s2.drafts[].beats`(칸별 text가 그대로 남아 있다).
- 라이브 DB 직접 쓰기는 권한 정책에 막힌다 — 사장님이 앱에서 대본수정으로 고치는 게 정상 경로.

관련: [[reference_prompt_says_but_nobody_checks]] · [[reference_freeze_whackamole_root]]
