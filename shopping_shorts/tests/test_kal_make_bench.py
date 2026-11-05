"""kal make 의 render_bench 갈래(관제 319, 11-06 스냅봤니 — 나레 없는 판: 자막 + 원음).
Jev: 뿌리 cause_A 0.89·증명 0.91 / fix_A 해결 0.86·위험 0.23·신뢰 1.0 (C:/t/kal_snap_jev/q_make_route.json).
옛 kal(step_make 가 preset_make 만 부름)에서는 --style 이 없어 이 시험이 실패한다."""
import json
from pathlib import Path

from tools.calcopy.engine import kal


def _state(tmp_path, monkeypatch, style):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    monkeypatch.setattr(kal, "disk_gate", lambda what: None)
    S = kal.State("snap_t", "@x", "브랜드", 1, "아니오")
    S.d["work"] = str(tmp_path / "work")
    S.d["style"] = style
    (tmp_path / "work").mkdir()
    return S


def test_make_routes_to_render_bench(tmp_path, monkeypatch):
    from tools.calcopy.hybrid import render_bench as RB, styles as ST
    monkeypatch.setattr(ST, "load", lambda name: {"name": name, "renderer": "bench"})
    seen = {}

    def fake_render(style, doc, work, **k):
        seen["args"] = (style, Path(doc), Path(work))
        R = Path(work) / "render"
        R.mkdir(parents=True)
        (R / "final.mp4").write_bytes(b"mp4bytes")
        json.dump({"rows": [{"t0": 0.0, "t1": 1.2, "text": "가나다", "kind": "원음"}]}, open(R / "자막표.json", "w", encoding="utf-8"), ensure_ascii=False)
        info = {"final": str(R / "final.mp4"), "final_dur": 1.2, "cuts_flat": [{"line": "L1", "src": "origin.mp4", "ss": 3.0, "t0": 0.0, "t1": 1.2, "dur": 1.2}]}
        json.dump(info, open(R / "render_info.json", "w", encoding="utf-8"))
        return info
    monkeypatch.setattr(RB, "render", fake_render)
    monkeypatch.setattr(kal, "glyph_gate", lambda p, w: [])
    S = _state(tmp_path, monkeypatch, "스냅봤니판")
    st, out, note = kal.step_make(S)
    assert st == "done", note
    assert seen["args"][0] == "스냅봤니판" and seen["args"][1] == Path(S.d["work"])
    assert kal._rendered(out["ours_mp4"])                       # run_log.json final.md5 짝(감시 kal.py:524 규칙 그대로)
    T = json.loads((Path(out["out"]) / "timeline.json").read_text(encoding="utf-8"))
    md, empty = kal.K.scene_table(out["out"])                   # apply-15 장면표가 빈 표로 조용히 통과하지 않는다
    assert T["groups"] and not empty and "origin.mp4" in md
    assert json.loads(Path(out["ours_lines"]).read_text(encoding="utf-8"))["rows"]


def test_make_bench_rejects_non_bench_style(tmp_path, monkeypatch):
    from tools.calcopy.hybrid import styles as ST
    monkeypatch.setattr(ST, "load", lambda name: {"name": name, "renderer": "itssum"})
    S = _state(tmp_path, monkeypatch, "잇썸홈판")
    st, out, note = kal.step_make(S)
    assert st == "failed" and "bench" in note
