"""관제 304 A·D — 컷 지문(render_bench.cut_fp)·재사용 표식·자막 칸 지문·재검사 범위. 실제 프레임·소리 대조는 tools/calcopy/hybrid/partial_render_check.py."""
import json
import os

import pytest

from tools.calcopy.hybrid import quality_gate as QG, render_bench as RB


def _a(**kw):
    return {"ss": 10.0, "crop": [0, 0, 1080, 1434], "win": (1080, 1434), "push": 0.0, "move": None, "blur": None, "pic": None, "pic_bg": None, "speed": 1.0, **kw}


@pytest.fixture
def src(tmp_path):
    p = tmp_path / "a.mp4"
    p.write_bytes(b"x" * 100)
    return p


def test_fp_same_for_same_input(src):
    assert RB.cut_fp(src, _a(), 30) == RB.cut_fp(src, _a(), 30)


@pytest.mark.parametrize("kw", [{"ss": 10.5}, {"crop": [10, 0, 1080, 1434]}, {"speed": 0.8}, {"push": 0.1}, {"blur": [[1, 2, 30, 40, 10.0, 10.5]]},
                                {"pic": [0, 0, 540, 700], "pic_bg": "#112233"}])
def test_fp_changes_with_everything_that_changes_picture(src, kw):
    assert RB.cut_fp(src, _a(), 30) != RB.cut_fp(src, _a(**kw), 30)


def test_fp_changes_with_length(src):
    assert RB.cut_fp(src, _a(), 30) != RB.cut_fp(src, _a(), 31)


def test_fp_changes_when_source_replaced(src):
    a = RB.cut_fp(src, _a(), 30)
    src.write_bytes(b"y" * 101)              # VMake 로 지우면 파일이 바뀐다
    assert RB.cut_fp(src, _a(), 30) != a


def test_blur_outside_cut_keeps_fp(src):
    assert RB.cut_fp(src, _a(blur=[[1, 2, 30, 40, 50.0, 51.0]]), 30) == RB.cut_fp(src, _a(blur=None), 30)


def test_reuse_needs_mark(tmp_path):
    part = tmp_path / "p.mp4"
    part.write_bytes(b"z" * 50)
    store = tmp_path / "s"
    RB.reuse_put(store, "abc", RB.CUT_RULE, 30, part)
    assert RB.reuse_get(store, "abc", RB.CUT_RULE, 30)
    assert RB.reuse_get(store, "abc", RB.CUT_RULE + 1, 30) is None      # 규칙이 다르면
    assert RB.reuse_get(store, "abc", RB.CUT_RULE, 31) is None          # 프레임 수가 다르면
    (store / "abc.json").unlink()
    assert RB.reuse_get(store, "abc", RB.CUT_RULE, 30) is None          # 표식이 없으면 믿지 않는다


def test_reuse_refuses_changed_file(tmp_path):
    part = tmp_path / "p.mp4"
    part.write_bytes(b"z" * 50)
    store = tmp_path / "s"
    RB.reuse_put(store, "abc", RB.CUT_RULE, 30, part)
    (store / "abc.mp4").unlink()
    (store / "abc.mp4").write_bytes(b"z" * 10)
    assert RB.reuse_get(store, "abc", RB.CUT_RULE, 30) is None


def test_full_env_turns_reuse_off(tmp_path, monkeypatch):
    part = tmp_path / "p.mp4"
    part.write_bytes(b"z" * 50)
    store = tmp_path / "s"
    RB.reuse_put(store, "abc", RB.CUT_RULE, 30, part)
    monkeypatch.setenv(RB.FULL_ENV, "1")
    assert RB.reuse_get(store, "abc", RB.CUT_RULE, 30) is None


def _sr(tmp_path, cuts, placed=None, trans=None):
    T = {"cuts": [{"frames": n, "fp": fp} for fp, n in cuts]}
    return RB.SceneReuse(T, {"frame": {}}, {}, placed or {}, trans or [], [], tmp_path, None, None, log=lambda s: None)


def _ctx(*spans):
    return {"text": "", "autoText": "", "scenes": [{"start": a, "end": b, "caption": c, "chars": [a, a + 0.1]} for a, b, c in spans]}


def test_scene_token_same_when_shifted_in_time(tmp_path):
    """앞 줄이 길어져 뒤로 밀린 칸 = 같은 컷 같은 글 → 같은 지문(자막 안 다시 굽는다)."""
    a = _sr(tmp_path, [("A", 60), ("B", 60), ("C", 60)])
    b = _sr(tmp_path, [("A2", 90), ("B", 60), ("C", 60)])
    ca = _ctx((0, 2, "앞"), (2, 4, "가"), (4, 6, "나"))
    cb = _ctx((0, 3, "앞"), (3, 5, "가"), (5, 7, "나"))
    assert a.token(2, ca, 120, 180, "r", {}, []) == b.token(2, cb, 150, 210, "r", {}, [])


def test_scene_token_changes_when_cut_in_range_changes(tmp_path):
    a = _sr(tmp_path, [("A", 60), ("B", 60), ("C", 60)])
    b = _sr(tmp_path, [("A", 60), ("B2", 60), ("C", 60)])
    c = _ctx((0, 2, "가"), (2, 4, "나"), (4, 6, "다"))
    assert a.token(1, c, 60, 120, "r", {}, []) != b.token(1, c, 60, 120, "r", {}, [])


def test_scene_token_sees_neighbor_cut_inside_margin(tmp_path):
    """전환·edge_glow 는 이웃 컷을 읽는다 — 칸 앞뒤 SCENE_MARGIN 안 컷이 바뀌면 다시 굽는다."""
    a = _sr(tmp_path, [("A", 60), ("B", 60), ("C", 60)])
    b = _sr(tmp_path, [("A", 60), ("B", 60), ("C2", 60)])
    c = _ctx((0, 2, "가"), (2, 4, "나"), (4, 6, "다"))
    assert a.token(1, c, 60, 120, "r", {}, []) != b.token(1, c, 60, 120, "r", {}, [])


def test_scene_token_far_cut_does_not_matter(tmp_path):
    a = _sr(tmp_path, [("A", 60), ("B", 60), ("C", 60), ("D", 60)])
    b = _sr(tmp_path, [("A", 60), ("B", 60), ("C", 60), ("D2", 60)])
    c = _ctx((0, 2, "가"), (2, 4, "나"), (4, 6, "다"), (6, 8, "라"))
    assert a.token(0, c, 0, 60, "r", {}, []) == b.token(0, c, 0, 60, "r", {}, [])


def test_scene_token_sees_overlay_event_and_caption(tmp_path):
    a = _sr(tmp_path, [("A", 60), ("B", 60)])
    b = _sr(tmp_path, [("A", 60), ("B", 60)], trans=[{"kind": "flash", "t": 1.0, "ms": 100}])
    c = _ctx((0, 2, "가"), (2, 4, "나"))
    assert a.token(0, c, 0, 60, "r", {}, []) != b.token(0, c, 0, 60, "r", {}, [])
    assert a.token(0, c, 0, 60, "r", {}, []) != a.token(0, _ctx((0, 2, "바뀐 글"), (2, 4, "나")), 0, 60, "r", {}, [])


def test_compose_default_has_no_cache():
    import inspect
    from shopping_shorts import scene_style as SS
    assert inspect.signature(SS.compose).parameters["cache"].default is None        # 숏템메이커 고객 길은 옛 동작


# ── 재검사 범위 ──────────────────────────────────────────────────────────
def _T(*cuts):
    return {"end": 6.0, "cuts": [{"fp": f, "t0": a, "t1": b} for f, a, b in cuts], "lines": {"L1": [0, 3], "L2": [3, 6]}}


S0 = {"lines": [{"id": "L1", "kind": "tts", "tts": "가", "caps": ["가"]}, {"id": "L2", "kind": "tts", "tts": "나", "caps": ["나"]}]}


def _base(R, T, S=S0):
    (R / QG.CHECK_BASE).write_text(json.dumps({"cuts": [c["fp"] for c in T["cuts"]], "bounds": [[c["t0"], c["t1"]] for c in T["cuts"]], "lines": QG.line_sigs(S)}), encoding="utf-8")


def test_changed_first_check_is_none(tmp_path):
    assert QG.changed_since(tmp_path, _T(("a", 0, 3), ("b", 3, 6)), S0) is None


def test_changed_finds_new_cut_only(tmp_path):
    _base(tmp_path, _T(("a", 0, 3), ("b", 3, 6)))
    c = QG.changed_since(tmp_path, _T(("a", 0, 3), ("b2", 3, 6)), S0)
    assert c["cuts"] == [1] and c["lines"] == [] and c["spans"] == [[3.0, 6.0]] and c["share"] == 0.5 and c["same_bounds"] is True


def test_changed_nothing(tmp_path):
    _base(tmp_path, _T(("a", 0, 3), ("b", 3, 6)))
    c = QG.changed_since(tmp_path, _T(("a", 0, 3), ("b", 3, 6)), S0)
    assert c["cuts"] == [] and c["lines"] == [] and c["share"] == 0


def test_changed_caption_text_only(tmp_path):
    _base(tmp_path, _T(("a", 0, 3), ("b", 3, 6)))
    S1 = json.loads(json.dumps(S0))
    S1["lines"][1]["caps"] = ["바뀐"]
    c = QG.changed_since(tmp_path, _T(("a", 0, 3), ("b", 3, 6)), S1)
    assert c["lines"] == ["L2"] and c["spans"] == [[3.0, 6.0]]


def test_changed_order_swap_means_full(tmp_path):
    _base(tmp_path, _T(("a", 0, 3), ("b", 3, 6)))
    assert QG.changed_since(tmp_path, _T(("b", 0, 3), ("a", 3, 6)), S0) is None


def test_old_timeline_without_fp_means_full(tmp_path):
    _base(tmp_path, _T(("a", 0, 3), ("b", 3, 6)))
    T = _T(("a", 0, 3), ("b", 3, 6))
    del T["cuts"][0]["fp"]
    assert QG.changed_since(tmp_path, T, S0) is None


def test_whole_video_rows_never_reused():
    """소리·길이·전체 음량처럼 전체에 걸린 항목은 재사용 표에 없다."""
    names = [k for k, _ in QG.ROW_KEEP]
    for what in ("길이", "음량", "최고점", "화면 멈춤 없음", "소리 끊김 없음(완성본 실측 1초↑)", "나레 받아쓰기 ↔ 대본", "광고 표시(ad_mark)", "완성본 컷 = 계획 프레임(창 대조 ≥0.97)"):
        assert not any(what.startswith(k) for k in names), what


def test_part_frames_only_looks_at_changed(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(RB, "count_frames", lambda p: seen.append(p.name) or 30)
    (tmp_path / "parts").mkdir()
    for k in range(3):
        (tmp_path / "parts" / f"c{k:02d}.mp4").write_bytes(b"x")
    T = {"cuts": [{"frames": 30, "line": "L", "src": "a", "ss": 0} for _ in range(3)]}
    assert QG.part_frames(tmp_path, T, [1]) == [] and seen == ["c01.mp4"]


def test_prune_keeps_newest(tmp_path):
    for k, kb in enumerate((600, 600)):
        f = tmp_path / f"{k}.mp4"
        f.write_bytes(b"x" * kb * 1000)
        (tmp_path / f"{k}.json").write_text("{}", encoding="utf-8")
        os.utime(f, (1000 + k, 1000 + k))
    RB.reuse_prune(tmp_path, keep_mb=1)
    assert (tmp_path / "1.mp4").exists() and not (tmp_path / "0.mp4").exists() and not (tmp_path / "0.json").exists()


def test_content_gate_only_keeps_full_timeline_for_anchors(tmp_path, monkeypatch):
    """바뀐 컷만 재도 기준 얼굴은 전체 시간표로 — 줄인 시간표를 넘기면 카드 컷 번호가 어긋나 항목이 '측정 실패'가 된다(실물 대조로 잡음)."""
    seen = {}
    monkeypatch.setattr(RB, "face_anchors", lambda st, doc, T, d: seen.setdefault("n", len(T["cuts"])) and [])
    monkeypatch.setattr(RB, "cut_content_feats", lambda *a, **k: seen.setdefault("feats", []).append(a[1]) or {"text": [], "face": []})
    monkeypatch.setattr(RB, "frame_window", lambda f: (0, 0, 100, 100))
    monkeypatch.setattr(RB, "cut_crop", lambda c, s, w: [0, 0, 100, 100])
    monkeypatch.setattr(RB, "cut_frames", lambda *a, **k: None)
    (tmp_path / "a.mp4").write_bytes(b"x")
    T = {"cuts": [{"src": "a.mp4", "ss": float(k), "line": "L", "t0": 0, "t1": 1, "frames": 30} for k in range(3)]}
    RB.cut_content_gate(T, {"cand_dir": str(tmp_path)}, {"frame": {}, "thumb_card_face": True}, tmp_path, None, log=lambda *a: None, only=[1])
    assert seen["n"] == 3 and seen["feats"] == [1.0]


def test_blur_elsewhere_keeps_content_key():
    assert RB.blur_in([[1, 2, 3, 4, 50.0, 51.0]], 10.0, 1.0) == []
    assert RB.blur_in([[1, 2, 3, 4]], 10.0, 1.0) == [[1, 2, 3, 4]]
    assert RB.blur_in([[1, 2, 3, 4, 10.5, 12.0]], 10.0, 1.0)
