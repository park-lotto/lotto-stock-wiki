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


def test_한_소스_안에서는_시간순으로_세운다():
    """★2026-08-17 사장님 지시로 규칙이 바뀌었다 — 예전엔 'AI가 고른 순서를 지킨다'였다.

    "1번 영상 시간순 / 2번 영상 시간순 마킹하고 뒤죽박죽 되지 않게 해줘야
     조리 시간순 배열을 할 때도 이상함을 못 느낀다."
    모델은 후보 목록을 훑는 순서로 답하기 쉬워 시간 흐름과 무관하다. 그대로 쓰면
    '완성 접시 → 반죽 치대기'처럼 **거꾸로 된 조리 순서**가 화면에 나간다.
    """
    call, _ = _stub([{"seg_id": "s1-3", "fit": 4},      # 6.0s (완성)
                     {"seg_id": "s1-1", "fit": 4}])     # 0.0s (반죽)
    out = edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, list(SEGS), call=call)
    assert [p["seg_id"] for p in out] == ["s1-1", "s1-3"], "시간순으로 세워야 한다"


def test_소스는_뭉치고_소스순서는_먼저_고른쪽():
    """소스가 섞이면 영상이 왔다갔다 한다 — 소스 단위로 뭉친다.
    어느 소스를 앞에 둘지는 AI가 먼저 고른 쪽(그 칸의 주된 소스)을 존중한다."""
    segs = dict(SEGS)
    segs["s2-1"] = {"seg_id": "s2-1", "video_id": "v2", "start": 1.0, "end": 3.0,
                    "scene_desc": "다른 영상 앞부분", "label": "", "text": ""}
    segs["s2-2"] = {"seg_id": "s2-2", "video_id": "v2", "start": 5.0, "end": 7.0,
                    "scene_desc": "다른 영상 뒷부분", "label": "", "text": ""}
    # AI가 v2를 먼저 골랐다 → v2 묶음이 앞, 각 묶음 안은 시간순
    call, _ = _stub([{"seg_id": "s2-2", "fit": 4},
                     {"seg_id": "s1-3", "fit": 4},
                     {"seg_id": "s2-1", "fit": 4},
                     {"seg_id": "s1-1", "fit": 4}])
    out = edit_plan.fill_beat_scenes("멘트", 8.0, segs, list(segs), call=call)
    assert [p["seg_id"] for p in out] == ["s2-1", "s2-2", "s1-1", "s1-3"]


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


def test_이미_나온_화면을_설명까지_알려준다():
    """소스가 여러 개면 같은 장면이 소스마다 있다(seg_id는 다르다). 후보에서 빼는 것만으론
    막을 수 없어, 이미 나온 화면을 **설명과 함께** 알려준다(2026-08-16 사장님 제보)."""
    call, seen = _stub([])
    edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, ["s1-1"],
                               taken_ids=["s1-2", "s1-3"], call=call)
    p = seen["prompt"]
    assert "이미 이 영상에 나오는 화면" in p
    assert "오븐에서 꺼내기" in p                       # 담긴 것의 이름
    assert "노릇하게 구워진 빵을 오븐에서" in p          # 담긴 것의 화면 묘사
    assert "소스가 달라도 같은 장면이면 안 된다" in p


def test_담긴게_없으면_그_블록은_안_붙는다():
    call, seen = _stub([])
    edit_plan.fill_beat_scenes("멘트", 4.0, SEGS, list(SEGS), taken_ids=[], call=call)
    assert "이미 이 영상에 나오는 화면" not in seen["prompt"]
