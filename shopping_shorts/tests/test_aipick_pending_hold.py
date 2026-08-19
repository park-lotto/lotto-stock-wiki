"""AI PICK — 덜 끝난 건 덜 끝났다고 말한다(2026-08-14 사장님 "왜 메인이 중국어냐").

실측 근거(work 73fc36693ed5): 담긴 4개 중 인스타 Db9O4pqza74의 추출은 04:05:00에 끝났는데
사장님이 화면을 본 건 04:02 — 그 3분 동안 한국어 소스가 목록에서 통째로 사라졌고, 남은
샤오홍슈 2개로 메인이 확정됐다(pick_backbone의 '인스타/유튜브 후보 0이면 전체 폴백' 경로).

증상 3개(중국어 메인 · 카드 2장 · 상단 이름 뒤섞임)는 전부 한 뿌리다:
**미완성 상태를 확정된 결과처럼 그린다.** 그래서 여기서 고치는 것은
  ① 추출 대기 소스를 드롭하지 않고 pending으로 남기고
  ② 한국어 축이 아직 없고 대기 중인 게 있으면 메인 확정을 보류(hold)한다.
"""
from shopping_shorts import aipick


def _src(vid, text="본문", pending=False, **kw):
    d = {"video_id": vid, "text": text, "segments": [], "name": vid, "thumbnail": "",
         "structure": None, "comments": None, "followers": None, "seconds": None,
         "views": None, "source_url": ""}
    if pending:
        d["pending"] = True
        d["text"] = ""
    d.update(kw)
    return d


def _meta(**platforms):
    return {k: {"platform": v, "comments": 10} for k, v in platforms.items()}


def test_hold_when_korean_axis_still_loading():
    """한국어 축(인스타)이 아직 분석 중이면 메인을 정하지 않는다 — 이게 사고의 핵심."""
    out = aipick.build_aipick(
        [_src("cn1"), _src("cn2"), _src("insta", pending=True)],
        _meta(cn1="xiaohongshu", cn2="xiaohongshu", insta="instagram"))
    assert out["hold"] is True
    assert out["pick_id"] is None          # ★샤오홍슈가 메인으로 앉지 않는다
    assert out["pending_count"] == 1


def test_pending_source_still_shown_as_card():
    """대기 소스도 카드로는 보인다 — 사라지면 '왜 2개뿐이냐'를 다시 겪는다."""
    out = aipick.build_aipick(
        [_src("cn1"), _src("cn2"), _src("insta", pending=True)],
        _meta(cn1="xiaohongshu", cn2="xiaohongshu", insta="instagram"))
    ids = [c["video_id"] for c in out["candidates"]]
    assert set(ids) == {"cn1", "cn2", "insta"}
    p = next(c for c in out["candidates"] if c["video_id"] == "insta")
    assert p["pending"] is True and p["score"] is None


def test_no_hold_when_korean_axis_ready():
    """한국어 축이 준비됐으면 대기 소스가 남아 있어도 종전대로 확정한다."""
    out = aipick.build_aipick(
        [_src("insta"), _src("cn1"), _src("cn2", pending=True)],
        _meta(insta="instagram", cn1="xiaohongshu", cn2="xiaohongshu"))
    assert out["hold"] is False
    assert out["pick_id"] == "insta"       # 백본 규칙대로 인스타
    assert out["pending_count"] == 1


def test_no_hold_when_nothing_is_waiting():
    """대기 중인 게 없으면(더 기다려도 안 온다) 종전 폴백 그대로 — 회귀 0."""
    out = aipick.build_aipick([_src("cn1"), _src("cn2")],
                              _meta(cn1="xiaohongshu", cn2="xiaohongshu"))
    assert out["hold"] is False
    assert out["pick_id"] in {"cn1", "cn2"}


def test_all_pending():
    """전부 분석 중이면 아무것도 확정하지 않는다."""
    out = aipick.build_aipick([_src("a", pending=True), _src("b", pending=True)], {})
    assert out["hold"] is True and out["pick_id"] is None
    assert out["pending_count"] == 2
    assert all(c["pending"] for c in out["candidates"])


def test_empty_sources_shape():
    out = aipick.build_aipick([], {})
    assert out["pick_id"] is None and out["hold"] is False and out["pending_count"] == 0


def test_pending_excluded_from_scoring():
    """대기 소스는 채점에 안 들어간다(대본이 없어 coverage 0으로 순위를 더럽힌다)."""
    out = aipick.build_aipick(
        [_src("insta"), _src("cn", pending=True)], _meta(insta="instagram", cn="xiaohongshu"))
    scored = [c for c in out["candidates"] if not c.get("pending")]
    assert [c["video_id"] for c in scored] == ["insta"]
