# -*- coding: utf-8 -*-
"""자막제거는 영상 1편당 **한 번만** 나가야 한다 (2026-08-27).

★사고: 사장님 "이사람은 그냥 장면도 안바꾸고 클릭만 처음부터 끝까지 한번씩해서 한다는데"
  그런데 실측하니 **편당 VMake 2콜**(= 100크레딧)이 나갔다.

    job 1e6c1e1c8b28
      11:58 clean  → final_clean_b2b36f3d842a914b.mp4   (1콜)
      12:05 render → final_clean_73ab50effdc65f34.mp4   (또 1콜)
      그 사이 사용자 조작·다른 작업 0. 3개 job 전부 청소본이 2개씩 남았다.

  뿌리: _synthesize_beats가 TTS 실측 발화초로 beat["target_seconds"]를 덮어쓰는데
  (mix_pipeline:552), 편성 서명(_plan_signature)이 그 값을 본다. 자막제거가 TTS 확정보다
  **먼저**라 렌더 직전에 서명이 반드시 한 번 바뀌었다 → 캐시 무효 → 재청소.
  자막제거를 쓰는 **모든 고객**이 2배로 소모하고 있었다.

  고침: 청소 전에 TTS를 확정한다(어차피 다음 단계에서 필요하다).
"""
import pytest

from shopping_shorts import mix_pipeline as mp


def _plan(t0=7.0, t1=3.0):
    return {"beats": [
        {"beat_idx": 0, "target_seconds": t0,
         "primary": {"video_id": "s0", "start": 1.0, "end": 5.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": t1,
         "primary": {"video_id": "s1", "start": 0.0, "end": 3.0}, "alternates": []},
    ]}


class Test서명이_TTS에_흔들린다:
    def test_target_seconds가_바뀌면_서명도_바뀐다(self):
        """★이 성질 자체는 옳다 — 컷 길이가 달라지면 완성본이 달라지니 다시 청소해야 한다.
        문제는 '청소 뒤에' 바뀌던 순서였다. 이 테스트는 성질을 못 박아 둔다."""
        assert mp._plan_signature(_plan(7.0)) != mp._plan_signature(_plan(7.3))

    def test_같은_편성이면_서명도_같다(self):
        assert mp._plan_signature(_plan()) == mp._plan_signature(_plan())


class Test청소_전에_TTS를_확정한다:
    def test_run_clean_sources가_TTS를_먼저_돌린다(self):
        """★순서가 뒤집히면 편당 2콜로 되돌아간다."""
        import inspect
        src = inspect.getsource(mp.run_clean_sources)
        i_tts = src.find("_synthesize_beats(")
        i_clean = src.find("_final_clean_fn(")
        assert i_tts > 0, "청소 전 TTS 확정이 사라졌다 — 편당 2콜로 되돌아간다"
        assert i_clean > 0
        assert i_tts < i_clean, "TTS 확정이 청소보다 뒤다 — 서명이 또 바뀐다"

    def test_확정한_편성을_저장한다(self):
        """저장 안 하면 렌더가 옛 편성을 읽어 또 갱신한다."""
        import inspect
        src = inspect.getsource(mp.run_clean_sources)
        assert "update_mix_job(job_id, edit_plan=" in src, \
            "TTS로 갱신한 편성을 저장하지 않는다"

    def test_렌더와_같은_형태로_부른다(self):
        """★호출 형태가 갈리면 서명이 어긋난다(0순위-B). skip_existing=True가 핵심."""
        import inspect
        for fn in (mp.run_clean_sources, mp.run_render):
            src = inspect.getsource(fn)
            i = src.find("_synthesize_beats(")
            assert i > 0, f"{fn.__name__}에 TTS 보장이 없다"
            window = src[i:i + 400]
            assert "skip_existing=True" in window, f"{fn.__name__}: skip_existing이 다르다"
            assert "voice=" in window, f"{fn.__name__}: voice를 안 넘긴다"
            assert "global_pron=" in window, f"{fn.__name__}: 발음교정을 안 넘긴다"

    def test_TTS_실패가_자막제거를_막지_않는다(self):
        """음성이 안 나와도 청소는 되어야 한다 — 여기서 막으면 기능이 통째로 죽는다."""
        import inspect
        src = inspect.getsource(mp.run_clean_sources)
        i = src.find("_synthesize_beats(")
        assert "except Exception" in src[i:i + 900], "TTS 실패를 삼키지 않는다"
