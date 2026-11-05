"""11-05 사장님 결정: 회원이 넣은 소재 영상(벤치)을 완성본 재료로 쓸 수 있다 — 처음 쓸 때 '저작권 책임은 회원 본인' 문구를 한 번 보인다.
(김미향 d016425e7b25·김형관 511f2b03f336: '받은 파일이 아니다' 로 막혀 회원 Claude 가 손으로 덮어 씀)"""
from tools.calcopy.hybrid import flow as F


def _st():
    return {"ref": "https://www.tiktok.com/@a/video/7600275103594728735", "bench": {"id": "7600275103594728735", "dur": 21.0},
            "research": {}, "read": {}, "tries": {}, "log": [], "product": {"product_id": "1", "image": "x.jpg"},
            "screen_rows": [{"id": "rev1"}], "origin": {"files": [{"name": "orig.mp4"}]}}


def test_material_download_also_fetches_bench(monkeypatch):
    st = _st()
    monkeypatch.setattr(F, "_reply", lambda rp, k, need: {"chosen": [{"id": "rev1"}]})
    monkeypatch.setattr(F, "_material_n", lambda st: (1, 3))
    r = F.ph_material_pick(st, {}, {}, {})
    b = [d for d in r["do"] if d.get("cmd") == "origin_get"]
    assert b and b[0]["vid"] == "7600275103594728735" and b[0]["full"] and b[0]["url"] == st["ref"]


def test_bench_file_counts_as_received_material():
    st = _st()
    F.ph_material_dl(st, {"dl": {"files": [{"name": "rev1.mp4"}]}, "bench_mat": {"files": [{"name": "7600275103594728735.mp4"}]}}, {}, {})
    assert "7600275103594728735.mp4" in {f["name"] for f in st["material"]["files"]}


def test_bench_not_rejected_by_source_rule():
    assert F._rule_bench_id(_st()) == ""


def test_first_use_shows_copyright_notice_once():
    st = _st()
    st["material"] = {"files": [{"name": "7600275103594728735.mp4"}]}
    M = {"cuts": {"L1": [{"src": "7600275103594728735.mp4"}]}}
    F._bench_notice(st, M)
    assert "저작권" in st["notice"] and "회원님 본인" in st["notice"] and not st.get("_notice_shown")
    st["_notice_shown"] = True
    F._bench_notice(st, M)
    assert st["_notice_shown"] and st["notice"].count("저작권") == 1


def test_no_notice_without_bench_cut():
    st = _st()
    F._bench_notice(st, {"cuts": {"L1": [{"src": "rev1.mp4"}]}})
    assert not st.get("notice")


def test_foreign_material_also_fetches_bench_and_keeps_it(monkeypatch):
    st = _st()
    st["origins"] = [{"id": "other"}]
    st["origin"] = {"id": "other", "files": [{"name": "other.mp4"}]}
    monkeypatch.setattr(F, "_alt_material_needed", lambda st: False)
    r = F.f_material(st, {}, {}, {})
    assert any(d.get("cmd") == "origin_get" and d["vid"] == "7600275103594728735" for d in r["do"])
    F.f_material_got(st, {"stills": {"files": [{"name": "p.jpg"}]}, "bench_mat": {"files": [{"name": "7600275103594728735.mp4"}]}, "shots": {}}, {}, {})
    assert "7600275103594728735.mp4" in {f["name"] for f in st["material"]["files"]}


def test_bench_that_is_the_origin_is_not_fetched_twice():
    st = _st()
    st["origins"] = [{"id": "7600275103594728735"}]
    assert F._bench_mat_do(st) == []
