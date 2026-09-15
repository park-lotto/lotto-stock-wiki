"""자막 줄 나누기가 바뀌면 청소본 서명도 바뀐다 (2026-09-11 고객 실사고).

줄 수 = 컷 수(_plan_phrase_clips)라 줄만 바꿔도 화면 컷이 달라지는데, 서명이 자막을 빼서
옛 컷으로 만든 final_clean_{sig}.mp4가 재사용됐다. caption_lines가 없으면(자동) 서명은 옛 그대로.
"""
from shopping_shorts import mix_pipeline as mp


def _plan(lines=None):
    b = {"primary": {"video_id": "s0", "start": 1.0, "end": 4.0}, "target_seconds": 3.0,
         "narration": "옷장은 좁고 옷이랑 이불 정리 해야되서 고민이었는데"}
    if lines is not None:
        b["caption_lines"] = lines
    return {"beats": [b]}


def test_줄을_바꾸면_서명이_바뀐다():
    two = mp._plan_signature(_plan(["옷장은 좁고 옷이랑 이불", "정리 해야되서 고민이었는데"]))
    four = mp._plan_signature(_plan(["옷장은 좁고", "옷이랑 이불", "정리 해야되서", "고민이었는데"]))
    assert two != four


def test_줄_지정이_없으면_옛_서명_그대로():
    assert mp._plan_signature(_plan()) == mp._plan_signature(_plan(None))
    assert mp._plan_signature(_plan([])) == mp._plan_signature(_plan())
