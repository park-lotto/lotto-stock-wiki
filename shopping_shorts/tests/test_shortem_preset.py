"""숏템프리셋 홈(관제 224) — calcopy_board.preset_home 이 장부 3장을 엮는지, 판정 글을 상태로 나누는지."""
import json

from shopping_shorts import calcopy_board as cb


def _books(tmp_path, brands=None, styles=None, items=None):
    ch = tmp_path / "channel"
    ch.mkdir()
    (ch / "브랜드.json").write_text(json.dumps({"brands": brands or {}}, ensure_ascii=False), encoding="utf-8")
    (ch / "스타일.json").write_text(json.dumps({"styles": styles or {}}, ensure_ascii=False), encoding="utf-8")
    (ch / "결과물.json").write_text(json.dumps({"items": items or []}, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_result_state_does_not_count_pending_as_passed():
    assert cb.result_state("페이블 판정 통과") == "통과"
    assert cb.result_state("페이블 판정 통과 후보(16호) — 사장님 귀 확인 뒤 확정") == "사장님 확인 대기"
    assert cb.result_state("preset_make 자동 검사 통과(사람 판정 전)") == "자동 검사만"
    assert cb.result_state("사장님 지적 반영판 — 재확인 전") == "사장님 확인 대기"
    assert cb.result_state("") == "검수 중"


def test_preset_home_links_brand_style_results(tmp_path):
    root = _books(tmp_path,
                  brands={"sseol": {"brand": "도파민썰템", "bench": "썰풀다"}, "even": {"brand": "재미썸홈", "bench": "이븐"}},
                  styles={"나레썰": {"priority": 3, "bench": {"sseol": {"n": 4, "views_median": 370000}}, "strengths": []},
                          "현장썰": {"priority": 1, "bench": {"sseol": {"n": 2}}, "strengths": ["원음 크게"]}},
                  items=[{"n": 1, "channel": "sseol", "title": "a", "judge": "페이블 판정 통과", "style": "나레썰"},
                         {"n": 2, "channel": "even", "title": "b", "judge": "자동 검사 통과(사람 판정 전)"},
                         {"n": 3, "channel": "yan", "channel_name": "얜샷템", "title": "c", "judge": "재확인 전"}])
    d = cb.preset_home(root)
    assert d["errors"] == []
    assert d["summary"] == {"brands": 2, "styles": 2, "results": 3, "passed": 1}
    assert [s["name"] for s in d["styles"]] == ["현장썰", "나레썰"]          # 우선순위 순
    assert d["styles"][1]["results"] == [1]
    by = {b["slug"]: b for b in d["brands"]}
    assert by["sseol"]["styles"] == ["현장썰", "나레썰"] and by["sseol"]["latest"]["n"] == 1
    assert by["even"]["states"]["자동 검사만"] == 1
    assert by["yan"]["in_ledger"] is False and by["yan"]["brand"] == "얜샷템"   # 장부 밖 브랜드는 숨기지 않고 드러낸다
    assert [r["n"] for r in d["results"]] == [3, 2, 1]


def test_preset_home_reports_missing_ledger(tmp_path):
    (tmp_path / "channel").mkdir()
    d = cb.preset_home(tmp_path)
    assert len(d["errors"]) == 3 and d["summary"]["results"] == 0


def test_preset_doc_only_whitelisted(tmp_path):
    import pytest
    with pytest.raises(KeyError):
        cb.preset_doc("../.env", tmp_path)
