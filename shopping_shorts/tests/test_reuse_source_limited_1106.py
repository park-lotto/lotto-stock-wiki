"""11-06 짧은 원본(10~23초, 원본 1개) 편 B13 반려 되풀이(김하영 #8834 13.8초 · 이부윤 #8978·#9006 23초 · 김효준 #9864 10.5초 · 이성택 #9390).
재료 원본 총 길이로 거리 문턱을 지킬 수 없으면(원본 한계) 가까운 재사용은 경고로 넘긴다 — 겹침(같은 화면 두 번)은 그대로 반려.
판단 주인 = quality_gate.source_limited · 나누기 = quality_gate.reuse_split."""
from tools.calcopy.hybrid import quality_gate as QG, runner_ops as RO


def _setup(tmp_path, monkeypatch, length):
    v = "판"
    (tmp_path / "doc" / v).mkdir(parents=True)
    (tmp_path / "doc" / v / "재료.json").write_text('{"cand_dir": "%s"}' % tmp_path.as_posix(), encoding="utf-8")
    (tmp_path / "a.mp4").write_bytes(b"x")
    import tools.calcopy.hybrid.styles as ST
    monkeypatch.setattr(ST, "load", lambda n: {})
    import tools.calcopy.hybrid.common as C
    monkeypatch.setattr(C, "dur_of", lambda p: length)
    return v


def _cuts(sss, dur=2.0):
    """원본 a.mp4 한 개에서 원본 순서를 뒤섞어 고른 나레 컷(화면에선 이어 붙음) — 이어 붙인 앞으로 가기 사슬이 아니라 B13 거리 판정을 받는다."""
    return {"cuts": [{"src": "a.mp4", "ss": s, "t0": k * dur, "t1": (k + 1) * dur, "line": f"N{k + 1}"} for k, s in enumerate(sss)]}


def test_short_single_source_distance_is_warning_on_first_plan(tmp_path, monkeypatch):
    v = _setup(tmp_path, monkeypatch, 10.5)
    T = _cuts([4.4, 0.0, 6.6, 2.2, 8.6])          # 5컷×2초 = 원본초 10 + 사이 4 × 2.6 = 20.5초 필요 > 10.5초
    assert QG.reuse_bad([{**c, "dur": c["t1"] - c["t0"]} for c in T["cuts"]], tmp_path, {})[0] == []
    assert RO._plan_reuse(tmp_path, v, T) == []
    block, warn, _ = QG.reuse_split([{**c, "dur": c["t1"] - c["t0"]} for c in T["cuts"]], tmp_path, {})
    assert block == [] and warn and all(w.startswith("원본 한계") for w in warn)


def test_short_source_overlap_still_rejected(tmp_path, monkeypatch):
    v = _setup(tmp_path, monkeypatch, 10.5)
    T = _cuts([4.4, 0.0, 5.0, 2.2, 8.6])          # N1 4.4~6.4 ↔ N3 5.0~7.0 = 같은 화면 겹침
    out = RO._plan_reuse(tmp_path, v, T)
    assert out and any("겹침" in x for x in out)


def test_long_source_distance_still_rejected(tmp_path, monkeypatch):
    v = _setup(tmp_path, monkeypatch, 60.0)        # 원본이 충분히 길면 거리를 지킬 수 있다 — 그대로 반려
    T = _cuts([4.4, 0.0, 6.6, 2.2, 8.6])
    out = RO._plan_reuse(tmp_path, v, T)
    assert out and any("거리" in x for x in out)


def test_source_limited_math():
    cuts = [{"src": "a.mp4", "ss": s, "dur": 2.0, "t0": k * 2.0, "t1": k * 2.0 + 2.0} for k, s in enumerate([4.4, 0.0, 6.6, 2.2, 8.6])]
    assert QG.source_limited(cuts, {"a.mp4": 10.5})
    assert not QG.source_limited(cuts, {"a.mp4": 60.0})
    assert not QG.source_limited(cuts, {"a.mp4": 10.5, "b.mp4": 30.0})      # 다른 재료 원본이 있으면 옮길 자리가 있다
