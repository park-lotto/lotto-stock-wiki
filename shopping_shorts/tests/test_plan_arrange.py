"""계획이 숫자 반려를 스스로 푼다(10-27 사장님 '뿌리 수정' — Claude 는 장면을 고르고 정확한 초·순서는 코드가).
재현(첫 재료 답 16편, tools/calcopy/hybrid/plan_replay.py): 재사용 6·경계/전환 5·A-B-A 4·컷 중앙 3·짧은 컷 1."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import material_fit as MF  # noqa: E402
from tools.calcopy.hybrid.checks import aba_violations  # noqa: E402


def _c(line, t0, src, ss, kind="tts"):
    return {"line": line, "t0": t0, "kind": kind, "src": src, "ss": ss, "see": src + str(ss)}


def test_aba_inside_one_line_is_swapped_without_changing_scenes():
    cuts = [_c("L1", 0, "X.mp4", 1), _c("L2", 1, "Y.mp4", 5), _c("L2", 2, "X.mp4", 9), _c("L3", 3, "Z.mp4", 2)]
    scenes = sorted((c["src"], c["ss"], c["see"]) for c in cuts)
    MF.fix_aba(cuts, log=lambda m: None)
    assert not aba_violations(cuts)
    assert sorted((c["src"], c["ss"], c["see"]) for c in cuts) == scenes          # 화면은 그대로(순서만)
    assert [c["line"] for c in cuts] == ["L1", "L2", "L2", "L3"] and [c["t0"] for c in cuts] == [0, 1, 2, 3]   # 자리(줄·시각)는 그대로


def test_aba_across_lines_is_left_for_gate():
    cuts = [_c("L1", 0, "X.mp4", 1), _c("L2", 1, "Y.mp4", 5), _c("L3", 2, "X.mp4", 9)]
    out = MF.fix_aba(cuts, log=lambda m: None)
    assert aba_violations(cuts) and "줄을 넘어" in out[-1]


def test_short_cut_borrows_from_previous_same_line():
    """10-27 썬크림 L7: 합치면 앞 컷이 늘어 원본 경계를 넘었다 → 앞 컷에서 빌려 짧은 컷을 늘린다(두 장면 다 남김)."""
    cuts = [_c("L7", 0.0, "A.mp4", 1), _c("L7", 1.0, "B.mp4", 3), _c("L8", 1.33, "C.mp4", 5)]
    MF.merge_short(cuts, end=3.0, log=lambda m: None)
    assert [c["src"] for c in cuts] == ["A.mp4", "B.mp4", "C.mp4"] and 1.33 - cuts[1]["t0"] >= 0.4


def test_short_cut_merges_when_previous_cannot_lend():
    cuts = [_c("L7", 0.0, "A.mp4", 1), _c("L7", 0.5, "B.mp4", 3), _c("L8", 0.8, "C.mp4", 5)]
    MF.merge_short(cuts, end=3.0, log=lambda m: None)
    assert [c["src"] for c in cuts] == ["A.mp4", "C.mp4"]


def test_orig_short_cut_borrow_keeps_lip_sync():
    cuts = [_c("O1", 0.0, "O.mp4", 10.0, "orig"), _c("O1", 2.0, "O.mp4", 12.0, "orig"), _c("L2", 2.3, "C.mp4", 5)]
    MF.merge_short(cuts, end=4.0, log=lambda m: None)
    c = cuts[1]
    assert round(c["ss"] - c["t0"], 3) == 10.0                     # 원본 초 − 줄 시각 = 그대로(입 맞춤)


def test_short_first_cut_of_line_merges_into_next():
    cuts = [_c("L6", 0.0, "A.mp4", 1), _c("L7", 1.0, "B.mp4", 3), _c("L7", 1.33, "C.mp4", 5)]
    MF.merge_short(cuts, end=3.0, log=lambda m: None)
    assert [c["src"] for c in cuts] == ["A.mp4", "C.mp4"] and cuts[1]["t0"] == 1.0


def test_photo_cut_splits_with_other_move():
    cuts = [_c("L9", 0.0, "prod_1_0.jpg", None), _c("L10", 6.0, "A.mp4", 1)]
    cuts[0].update({"ss": None, "move": "in"})
    m = MF.split_cut(cuts[0], cuts, Path("."), 8.0, {})
    assert m and [c["src"] for c in cuts] == ["prod_1_0.jpg", "prod_1_0.jpg", "A.mp4"] and cuts[1]["move"] == "out" and cuts[1]["t0"] == 3.0


def test_source_rule_scan_reads_source_seconds_of_slowed_cut(monkeypatch, tmp_path):
    """10-27 TV L0: 0.84배 늦춘 컷(원본 1.23초)을 화면 길이 1.47초로 읽어 안 보이는 뒤 전환을 잡은 거짓 반려."""
    from tools.calcopy.hybrid import runner_ops as R
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "v.mp4").write_bytes(b"x")
    seen = []
    monkeypatch.setattr(R, "_cut_jumps", lambda p, ss, dur, **k: seen.append(dur) or [])
    monkeypatch.setattr(R, "_cut_faces", lambda *a, **k: 0)
    T = {"cuts": [{"line": "L0", "src": "v.mp4", "ss": 4.367, "t0": 1.767, "t1": 3.239, "dur": 1.472, "speed": 0.8409, "kind": "tts"}]}
    R.source_rule_scan(tmp_path, T, set())
    assert seen and abs(seen[0] - 1.237) < 0.05


def test_relocate_drops_cut_when_no_room_and_line_has_mate(monkeypatch, tmp_path):
    """10-27 펜티 E2 80초: 원음 줄이 원본을 거의 다 써 빈자리가 없는 재사용 컷 → 빼고 같은 줄 다른 컷이 이어받음(다른 영상으로 안 바꾼다)."""
    from tools.calcopy.hybrid import render_bench as RB, runner_ops as R
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x64:d=10:r=30", "-c:v", "libx264", "-preset", "ultrafast",
                    str(tmp_path / "v.mp4")], check=True)
    monkeypatch.setattr(R, "jump_free_spans", lambda src, spans, **k: [])      # 빈자리 0
    monkeypatch.setattr(R, "_cut_jumps", lambda *a, **k: [])
    a = {**_c("E2", 0.0, "v.mp4", 1.0), "t1": 1.0, "dur": 1.0}
    b = {**_c("E2", 1.0, "v.mp4", 5.0), "t1": 2.0, "dur": 1.0, "reuse_unfixed": ["거리"]}
    cuts = [a, b]
    MF.relocate_cuts(cuts, tmp_path, set(), log=lambda m: None, end=2.0)
    assert cuts == [a]
