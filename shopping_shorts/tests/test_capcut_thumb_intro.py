"""🖼 캡컷 썸네일 인트로 — 맨 앞 1.2초 사진 + **나머지 전부 그만큼 밀림**.

왜 이 테스트가 중요한가: 인트로를 넣으면 영상·TTS·자막·효과음·틀·머리카피·워터마크가
**전부 같은 만큼** 밀려야 한다. 한 트랙이라도 안 밀리면 **소리와 화면이 어긋난다**
— 캡컷을 열어봐야 보이는 종류라 여기서 수치로 못박는다.

★`source_timerange`는 밀면 안 된다(소스 파일 안에서 어디부터 읽을지지 타임라인 위치가 아니다).
"""
import shopping_shorts.capcut_draft as cd
from shopping_shorts.tests.test_capcut_draft import _PLAN, _TIMELINE, _SRC, _TTS, _ASSET


INTRO = {"path": "C:/cap/CapCut Drafts/p/thumb_intro.png", "seconds": 1.2}
INTRO_US = 1_200_000


def _build(intro=None, **kw):
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="p",
                              intro=intro, **kw)
    return draft


def _starts(draft, ttype):
    return [s["target_timerange"]["start"]
            for t in draft["tracks"] if t["type"] == ttype for s in t["segments"]]


def _shape(d):
    """id(매번 새 UUID)를 뺀 **뜻이 있는 모양**만 뽑는다 — 두 번 만든 draft를 비교하려면 필요하다."""
    return {"duration": d["duration"],
            "tracks": [{"type": t["type"],
                        "segs": [(s["target_timerange"], s.get("source_timerange"),
                                  s.get("track_render_index"), s.get("volume"))
                                 for s in t["segments"]]}
                       for t in d["tracks"]],
            "videos": [(m["type"], m.get("path")) for m in d["materials"]["videos"]]}


def test_no_intro_changes_nothing():
    """인트로를 안 주면 종전과 **완전히 같아야** 한다(회귀 0).

    ★draft에는 매번 새로 만드는 UUID가 들어 있어 통째로 비교하면 항상 다르다 — 그래서
      id를 뺀 모양(_shape)으로 비교한다. (내 첫 테스트가 이걸로 헛발질했다)
    """
    base = _shape(_build())
    assert _shape(_build(intro=None)) == base
    assert _shape(_build(intro={"path": "", "seconds": 1.2})) == base      # 경로 없으면 무시
    assert _shape(_build(intro={"path": "x.png", "seconds": 0})) == base   # 0초면 무시
    assert _shape(_build(intro={})) == base


def test_intro_segment_sits_at_zero_for_its_length():
    """인트로는 0초에, 준 길이만큼."""
    d = _build(intro=INTRO)
    intro_segs = [s for t in d["tracks"] for s in t["segments"]
                  if s["target_timerange"] == {"start": 0, "duration": INTRO_US}]
    assert intro_segs, "0초에 1.2초짜리 인트로 세그먼트가 없다"
    seg = intro_segs[0]
    assert seg["volume"] == 0.0, "사진에 소리가 있으면 안 된다"
    # 그 세그먼트가 가리키는 재료가 우리 PNG인지
    mat = [m for m in d["materials"]["videos"] if m["id"] == seg["material_id"]][0]
    assert mat["type"] == "photo" and mat["path"] == INTRO["path"]


def test_every_track_shifts_by_exactly_the_intro():
    """★핵심 — 모든 트랙이 **정확히 같은 만큼** 밀린다. 하나라도 안 밀리면 어긋난다."""
    deco = {"watermark": {"text": "숏템메이커"}}
    hc = {"_capcut_path": "C:/cap/p/headcopy.png", "t0": 0.0, "dur": 2.0}
    sfx = [{"_capcut_path": "C:/cap/p/sfx_00.mp3", "at": 2.0, "dur": 0.8, "volume": 60}]
    cut = {1: {"_capcut_path": "C:/cap/p/cutaway_01.mp4", "dur": 1.5}}
    kw = dict(deco=deco, headcopy_layer=hc, sfx_layers=sfx, cutaway_layers=cut)

    before, after = _build(**kw), _build(intro=INTRO, **kw)
    for ttype in ("video", "audio", "text"):
        b, a = sorted(_starts(before, ttype)), sorted(_starts(after, ttype))
        if ttype == "video":
            # after에는 인트로(0초에 새로 생긴 것)가 하나 더 있다 — 그 하나만 빼고 비교한다
            assert 0 in a, "인트로가 0초에 없다"
            a.remove(0)
        assert len(a) == len(b), f"{ttype}: 세그먼트 개수가 달라졌다 ({len(b)}→{len(a)})"
        assert b, f"{ttype}: 비교할 세그먼트가 없다 — 테스트가 아무것도 안 재고 있다"
        for x, y in zip(b, a):
            assert y - x == INTRO_US, f"{ttype}: {x} → {y} (밀린 양 {y-x} ≠ {INTRO_US})"


def test_source_timerange_is_not_shifted():
    """소스 안에서 읽을 위치는 **그대로**여야 한다 — 밀면 엉뚱한 데가 재생된다."""
    def srcs(d):
        return [s.get("source_timerange") for t in d["tracks"] for s in t["segments"]
                if s.get("source_timerange")]
    before, after = srcs(_build()), srcs(_build(intro=INTRO))
    # 인트로 세그먼트(0부터 1.2초)만 추가됐고 나머지 소스 위치는 한 톨도 안 변해야 한다
    for s in before:
        assert s in after, f"소스 위치가 바뀌었다: {s}"


def test_project_duration_grows_by_the_intro():
    """전체 길이도 그만큼 늘어야 한다 — 안 늘면 끝이 잘린다."""
    assert _build(intro=INTRO)["duration"] - _build()["duration"] == INTRO_US


def test_intro_does_not_disturb_track_order_of_existing_tracks():
    """기존 트랙 순서(층 쌓는 순서)는 그대로 — 인트로는 **뒤에** 붙는다."""
    deco = {"watermark": {"text": "숏템메이커"}}
    before = [t["type"] for t in _build(deco=deco)["tracks"]]
    after = [t["type"] for t in _build(intro=INTRO, deco=deco)["tracks"]]
    assert after[:len(before)] == before, "기존 트랙 순서가 흐트러졌다"
    assert after[len(before):] == ["video"], "인트로 트랙은 맨 뒤 video 하나여야 한다"


def test_materials_videos_zero_is_still_a_source_clip():
    """★videos[0]=소스 전제를 깨지 않는다 — 앞에 끼우면 기존 검사·보관함이 어긋난다."""
    d = _build(intro=INTRO)
    assert d["materials"]["videos"][0]["type"] != "photo", "인트로가 videos[0]을 차지했다"


def test_intro_length_comes_from_one_place():
    """렌더·CTA·캡컷이 **같은 함수**로 인트로 길이를 정한다(0순위-B)."""
    from shopping_shorts.app import thumb_intro_seconds
    assert thumb_intro_seconds({}) == 1.2                 # 기본값
    assert thumb_intro_seconds({"intro_sec": 2.5}) == 2.5
    assert thumb_intro_seconds({"intro_sec": 0}) == 1.2   # 0은 "안 정함"으로 본다(종전 동작)
    assert thumb_intro_seconds({"intro_sec": "x"}) == 1.2
    assert thumb_intro_seconds(None) == 1.2
