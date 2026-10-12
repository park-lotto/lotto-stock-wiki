# 130 · 칸별 성우 소실: 전체 재합성(_synthesize_beats)이 칸별 성우(voice_override)를 무시

- 쉬운 설명: 고객이 칸마다 바꾼 성우가 전체 다시 만들기 후 원래 성우로 돌아가는 문제
- 상태: 등록
- 등록: 2026-10-05 20:27
- 제보: Claude(관제128 조사)
- 판단 주인: shopping_shorts/mix_pipeline.py:voice_for_beat
- 분배: 
- 됐다의 기준: 칸 하나 성우 바꾼 뒤 대본 수정으로 전체 재합성해도 그 칸 성우 유지(완성 영상 칸별 성우 대조)
- 검사: 
- 승인 필요: 예
- 승인: 
- 병합: 
- 서버 반영: 
- 라이브 실측: 
- 재발: 

## 요청

2026-10-05 대화형대본 조사 중 발견: 단일 칸 재생성(app.py:8487·mix_pipeline.resynth_one_beat)은 voice_override를 쓰지만 _synthesize_beats(582)·_try_joined(529)는 작업 기본 성우만 써서, resynth_tts_job 등 전체 재합성 때 고객이 칸별로 바꾼 성우가 사라진다(0순위-B 두 벌).

## 이력

- 2026-10-05 20:27 등록
