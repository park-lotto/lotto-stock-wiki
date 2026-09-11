---
name: reference_freeze_whackamole_root
description: "제작소 영상 '화면 멈춤(프리즈)'이 반복 재발하는 이유 — 증상(채우는 방법)만 바꿔온 두더지잡기. 뿌리=나레이션>영상조각 틈"
metadata: 
  node_type: memory
  type: reference
  originSessionId: e26b6f80-358b-46da-bd39-3cd7903d10a0
  modified: 2026-07-21T12:41:28.128Z
---

제작소 믹스 영상의 **화면 멈춤/프리즈**는 여러 번 "고쳤는데" 계속 재발했다. 이유: 매번 뿌리가 아니라 **틈을 채우는 방법**만 다른 코드 자리에서 바꿨기 때문(두더지잡기).

**뿌리 = 한 비트의 나레이션이 그 비트에 쓸 영상 조각보다 길다.** 남는 시간을 뭘로든 채워야 하고, 그 "채우는 방법"을 바꿀 때마다 새 경로에서 정지가 다시 튀어나온다:
- 07-19: 무제한 슬로우 → 상한 1.15배+정지(freeze). 크롤 없앴지만 정지 생김.
- 07-20: 정지 대신 릴 실프레임 재생(1순위). 릴 끝이 정지샷이면 또 멈춰 보임.
- 07-20: 릴 짧으면 다른 조각 루프(2순위). 반복 생김.
- 07-21: 2순위 루프가 채운 짧은 클립을 `_plan_beat_clips` min_clip 흡수(276줄)가 이웃 out_dur만 부풀려 **정지로 되돌림**(b3 CTA 0.97초). → 흡수를 실프레임 연장/유지로 바꿔 정지 0.97s→0s(`_MIN_CLIP_KEEP` 0.5, e1096c9b9).

**두더지잡기를 끝내는 진짜 fix(미구현)**: 렌더에서 채우기(정지/슬로우/루프)를 손보지 말고 **애초에 틈이 안 생기게**:
1. `fill_clips_to_cover`가 추정(글자÷5.7=narration_seconds)이 아니라 **실 TTS 길이**만큼 varied 조각으로 채우게(TTS 후 재보정). 지금은 fill=plan시점 추정, 렌더=실 tts_dur라 어긋난다.
2. 조각이 정말 부족하면 그 비트 **나레이션을 화면 길이에 맞춰 줄이기** — `conform`이 이미 있으나 "넘칠 때(over budget)"만 돎. "모자랄 때"도 대칭 적용 필요.
3. 근본은 [[project_scene_spine_2track]]·[[feedback_anchor_to_real_goal_backbone_interleave]]의 "비트당 서로 다른 B롤 충분히" — 소스/서브영상 다양성.

**교훈**: "프리즈 고쳤다"는 보고를 조심할 것 — 채우는 경로 하나 막은 것일 뿐 틈은 그대로면 다음 경로에서 재발. 검증은 실 job 재현(_plan_beat_clips + _speed_and_freeze로 비트별 정지초 계산)으로. 관련: [[reference_local_tts_silent_mock_trap]](길이검증 함정).
