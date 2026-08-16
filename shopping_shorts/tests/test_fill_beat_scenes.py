"""칸 채우기(대사↔화면 매칭) — edit_plan.fill_beat_scenes.

★진짜 함수를 부른다. Gemini 호출만 스텁으로 갈아끼워(call=…) 과금 없이 계약을 본다.
  프롬프트에 무엇이 실리는지까지 확인한다 — 태깅을 안 실으면 "대본이랑 태깅 보고 매칭"이
  말뿐이 되기 때문이다(2026-08-16 사장님 지시).
"""
from shopping_shorts import edit_plan


SEGS = {
    "s1-1": {"seg_id": "s1-1", "video_id": "v1", "start": 0.0, "end": 3.0,
             "label": "반죽 치대기", "use_point": "과정 보여줄 때",
             "scene_desc": "손으로 반죽을 치대는 장면", "change": "매끈해진다",
             "text": "이렇게 치대면"},
    "s1-2": {"seg_id": "s1-2", "video_id": "v1", "start": 3.0, "end": 6.0,
             "label": "오븐에서 꺼내기", "use_point": "결과 보여줄 때",
             "scene_desc": "노릇하게 구워진 빵을 오븐에서 꺼낸다", "change": "부풀어 오른다",
             "text": ""},
    "s1-3": {"seg_id": "s1-3", "video_id": "v1", "start": 6.0, "end": 9.0,
             "label": "완성 접시", "use_point": "훅·CTA용",
             "scene_desc": "완성된 빵이 접시에 담겨 있다", "change": "", "text": ""},
}


def _stub(picks):
    """Gemini 대신 정해진 답을 돌려주고, 받은 프롬프트를 기록한다."""
    seen = {}

    def call(prompt, schema, **kw):
        seen["prompt"] = prompt
        seen["schema"] = schema
        return {"picks": picks}

    return call, seen


def test_대사와_태깅이_프롬프트에_실린다():
    call, seen = _stub([{"seg_id": "s1-2", "fit": 5, "why": "결과가 보인다"}])
    edit_plan.fill_beat_scenes("노릇하게 구워집니다", 3.8, SEGS, list(SEGS), call=call)
    p = seen["prompt"]
    assert "노릇하게 구워집니다" in p                 # 대사
    assert "오븐에서 꺼내기" in p                     # 장면 이름(label)
    assert "결과 보여줄 때" in p                      # 쓸모(use_point)
    assert "부풀어 오른다" in p                       # 변화(change)
    assert "노릇하게 구워진 빵을 오븐에서" in p        # 화면 묘사(scene_desc)


def test_필요_장수를_컷상한으로_알려준다():
    call, seen = _stub([])
    # 3.8초 / 한 컷 2.2초 → 2장
    edit_plan.fill_beat_scenes("멘트", 3.8, SEGS, list(SEGS), call=call)
    assert "2장 정도" in seen["prompt"]
    # 6.6초 → 3장
    edit_plan.fill_beat_scenes("멘트", 6.6, SEGS, list(SEGS), call=call)
    assert "3장 정도" in seen["prompt"]


def test_고른_순서를_지킨다():
    call, _ = _stub([{"seg_id": "s1-3", "fit": 4},
                     {"seg_id": "s1-1", "fit": 4}])
    out = edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, list(SEGS), call=call)
    assert [p["seg_id"] for p in out] == ["s1-3", "s1-1"]


def test_후보밖_중복_저품질은_버린다():
    call, _ = _stub([
        {"seg_id": "s1-1", "fit": 5},
        {"seg_id": "s1-1", "fit": 5},      # 같은 것 두 번 → 하나만
        {"seg_id": "없는거", "fit": 5},     # 인벤토리에 없음
        {"seg_id": "s1-2", "fit": 1},      # fit이 낮음(min_fit 미만)
        {"seg_id": "s1-3", "fit": 4},
    ])
    out = edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, list(SEGS), call=call)
    assert [p["seg_id"] for p in out] == ["s1-1", "s1-3"]


def test_이미_담긴것은_후보에서_빠진다():
    call, seen = _stub([])
    edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, ["s1-2", "s1-3"], call=call)
    assert "s1-1" not in seen["prompt"]
    assert "s1-2" in seen["prompt"]


def test_실패하면_빈목록_fail_open():
    # 모델이 죽거나(None) 모양이 틀리면 빈 목록 → 화면은 규칙 기반으로 내려간다
    assert edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, list(SEGS),
                                      call=lambda p, s, **k: None) == []
    assert edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, list(SEGS),
                                      call=lambda p, s, **k: {"nope": 1}) == []


def test_재료가_없으면_모델을_안_부른다():
    """대사·인벤토리·후보 중 하나라도 비면 호출 자체를 안 한다(과금 0)."""
    called = []

    def call(p, s, **k):
        called.append(1)
        return {"picks": []}

    assert edit_plan.fill_beat_scenes("", 4.0, SEGS, list(SEGS), call=call) == []
    assert edit_plan.fill_beat_scenes("멘트", 4.0, {}, list(SEGS), call=call) == []
    assert edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, [], call=call) == []
    assert not called
