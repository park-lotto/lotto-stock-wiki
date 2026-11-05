"""11-04 강병주 #5656·#5864: 뒤 VMake 지우기 결과를 restyle(다시 만들기)로 받아 원본에 끼워도, 재료.blur 에서 지운 구간을 빼지 않아
지운 원본 위에 흐림 띠를 다시 덮었다(flow.f_bg_got 에만 blur_minus_spans). restyle 길도 받은 구간만큼 같은 함수로 뺀다."""
import json
from pathlib import Path

from tools.calcopy.hybrid import runner_ops as RO


def test_restyle_takes_bg_and_removes_blur(tmp_path, monkeypatch):
    W = tmp_path
    v = "v1"
    doc = W / "doc" / v
    doc.mkdir(parents=True)
    (doc / "재료.json").write_text(json.dumps({"blur": {"a.mp4": [[0, 1500, 1080, 200, 0.0, 10.0]]}}), encoding="utf-8")
    seen = {}
    monkeypatch.setenv("SHORTEM_RESTYLE", "1")
    monkeypatch.setattr(RO, "tts_cache_miss", lambda W, v: "")
    monkeypatch.setattr(RO, "c_clean_take", lambda W, d: {"state": "done", "done": {"a.mp4": [[2.0, 6.0]]}, "calls": 1})
    monkeypatch.setattr(RO, "source_rule_scan", lambda *a, **k: [])
    from tools.calcopy.hybrid import render_bench

    def fake_render(v, doc_dir, out, pack=None):
        seen["blur"] = json.loads((Path(doc_dir) / "재료.json").read_text(encoding="utf-8"))["blur"]["a.mp4"]
        (Path(out) / "render").mkdir(parents=True, exist_ok=True)
        (Path(out) / "render" / "final.mp4").write_bytes(b"x")
        return {}
    monkeypatch.setattr(render_bench, "render", fake_render)
    RO._c_render(W, {"version": v})
    spans = [(r[4], r[5]) for r in seen["blur"]]
    assert all(b <= 2.0 or a >= 6.0 for a, b in spans), f"지운 구간(2~6초)에 흐림이 남았다: {spans}"
    assert spans, "지우지 않은 구간의 흐림까지 사라졌다"
