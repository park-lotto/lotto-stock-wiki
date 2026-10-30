"""10-30 사장님 "말이 없으면 벤치 채널에서 조회수 순으로 · 후보 뽑아달라면 5개 · 벤치 채널은 계속 준다(같은 장르 — 원본을 찾아서)".
소재 창고 = channel/<slug>/_kal/벤치상위.json(bench_pool.py build) · 판단 주인 = flow.bench_pool(주소 없는 시작·후보 5개·둘째 소재가 같이 부른다)."""
import json

from tools.calcopy.hybrid import flow as F


def _pool(tmp_path, monkeypatch, rows, bench_ids=()):
    kal = tmp_path / "ch" / "slugx" / "_kal"
    kal.mkdir(parents=True)
    (kal / F.ALT_LIST).write_text(json.dumps({"rows": rows}), encoding="utf-8")
    if bench_ids:
        (kal / F.ALT_BENCH_IDS).write_text(json.dumps({"ids": list(bench_ids)}), encoding="utf-8")
    monkeypatch.setattr(F, "PRESETS_FILE", tmp_path / "ch" / "프리셋.json")
    monkeypatch.setattr(F, "flow_format_of", lambda v: ("쇼핑형", "slugx"))


ROWS = [{"id": f"id{i:08d}x", "views": v, "title": f"t{i}"} for i, v in enumerate([10, 900, 50, 700, 300, 20, 600])]


def test_pick_source_is_top_unmade_by_views(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, ROWS, bench_ids=["id00000003x"])          # 판 본보기(700)는 뺀다
    assert F.pick_source("v")["id"] == "id00000001x"                        # 900
    assert F.pick_source("v", ["https://www.youtube.com/shorts/id00000001x"])["id"] == "id00000006x"   # 만든 편(주소) 빼고 600


def test_candidates_are_five_in_order(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, ROWS)
    c = F.source_candidates("v")
    assert [x["n"] for x in c] == [1, 2, 3, 4, 5] and [x["views"] for x in c] == [900, 700, 600, 300, 50]


def test_auto_source_moves_to_next_when_not_shopping(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, ROWS)
    monkeypatch.setattr(F, "start", lambda url, v, sid, *a: {"sid": sid, "ref": url, "version": v, "fmt": "쇼핑형", "slug": "slugx", "phase": "setup", "tries": {}, "log": []})
    st = F.start("https://www.youtube.com/shorts/id00000001x", "v", "s1")
    st.update(auto_source={"id": "id00000001x"}, made_refs=[])
    assert F._auto_next_source(st, F._Stop("제품이 화면에 나오는 영상이 아니에요", "", final=True))
    assert st["ref"].endswith("id00000003x") and st["auto_tried"][0].endswith("id00000001x") and st["sid"] == "s1"
    st2 = F.start("https://www.youtube.com/shorts/id00000001x", "v", "s2")                    # 회원이 준 주소면 넘어가지 않는다
    assert not F._auto_next_source(st2, F._Stop("x", "", final=True))


def test_server_record_uses_hash_not_url(tmp_path, monkeypatch):
    """서버 작업 기록엔 주소를 안 남긴다(claude_flow 요약 규칙) — 지문(ref_hash)으로도 만든 편이 빠진다."""
    _pool(tmp_path, monkeypatch, ROWS)
    h = F.ref_hash("https://www.youtube.com/shorts/id00000001x")
    assert h.startswith("h:") and "id00000001x" not in h
    assert F.pick_source("v", [h])["id"] == "id00000003x"
