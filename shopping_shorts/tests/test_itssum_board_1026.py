"""잇썸홈 판(channel/homedesignnote/preset/전체화면_가운데자막) 10-26 벤치 맞춤 — 판 칸이 실제 판정·렌더로 이어지는지.

① B13 '한 동작 이어서 반복'(사장님 결정 '가') = quality_gate.reuse_violations_bench(adjacent_run) 한 곳 — 바로 이어 붙은 같은 소스 줄기만 거리 허용,
   겹침·사이 컷 낀 재등장은 계속 × / preset_make B13 이 그 함수를 판 칸 reuse.adjacent_run 으로 부른다(옛 check_overlap.py ±3초 대신).
② 판 rhythm 칸 → preset_gates.cut_gates 가 render_bench.rhythm_gate 를 부른다(재미썸홈 판도 같은 길).
③ 표지 카드(make.cover_card) = 완성 영상 맨 앞 thumb.THUMB_FRAMES 프레임만 바뀐다.
④ 판 값이 벤치 실측 칸을 가졌는지(atempo 상한 1.25·rhythm 4칸 why·자막 외곽)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid.quality_gate import reuse_violations_bench  # noqa: E402
from tools.calcopy.engine import preset_make as PM  # noqa: E402
from tools.calcopy.engine import preset_gates as PG  # noqa: E402

PDIR = ROOT / "channel/homedesignnote/preset/전체화면_가운데자막"


def _c(src, ss, dur, t0):
    return {"src": src, "ss": ss, "dur": dur, "t0": t0, "t1": t0 + dur, "line": "줄1"}


# ── ① B13 ────────────────────────────────────────────────────────────────
def test_adjacent_run_allows_continued_action_only():
    lens = {"a.mp4": 20.0, "b.mp4": 20.0}
    run = [_c("a.mp4", 5.0, 1.0, 0.0), _c("a.mp4", 6.5, 1.0, 1.0), _c("a.mp4", 4.6, 0.3, 2.0)]   # 같은 원본 이어 붙임: 앞으로 건너뜀·뒤로(겹침 없음)
    assert reuse_violations_bench(run, lens)                       # 옛 판정(다른 판) = 거리 ×
    assert reuse_violations_bench(run, lens, adjacent_run=True) == []
    over = [_c("a.mp4", 5.0, 1.0, 0.0), _c("a.mp4", 5.5, 1.0, 1.0)]  # 이어 붙었어도 같은 프레임(5.5~6.0)을 다시 보이면 ×
    assert any("겹침" in v for v in reuse_violations_bench(over, lens, adjacent_run=True))
    back = [_c("a.mp4", 5.0, 1.0, 0.0), _c("b.mp4", 1.0, 1.0, 1.0), _c("a.mp4", 6.5, 1.0, 2.0)]   # 사이에 다른 컷 → 몇 초 뒤 같은 장면 재등장 ×
    assert any("거리" in v for v in reuse_violations_bench(back, lens, adjacent_run=True))


def test_preset_make_b13_uses_board_flag():
    w = {"pieces": [{"line": 0}, {"line": 0}],
         "cuts": [{"path": Path("x/a.mp4"), "ss": 5.0, "n": 30, "f0": 0, "pieces": [0], "meme": False, "src_dur": 20.0},
                  {"path": Path("x/a.mp4"), "ss": 3.5, "n": 30, "f0": 30, "pieces": [1], "meme": False, "src_dur": 20.0}]}
    assert PM.reuse_rows(w, {})                                    # 칸 없는 판 = 거리 ×
    assert PM.reuse_rows(w, {"reuse": {"adjacent_run": True}}) == []


# ── ② 리듬 관문 연결 ────────────────────────────────────────────────────────
def _ff(*a):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, a)], check=True, stdin=subprocess.DEVNULL)


def test_cut_gates_calls_rhythm_gate(tmp_path):
    src = tmp_path / "a.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=s=640x480:r=30:d=8", "-pix_fmt", "yuv420p", src)
    lines = [{"text": "첫 줄 이야기", "tts": "첫 줄 이야기."}]
    w = {"name": "시험", "data": tmp_path, "lines": lines, "pieces": [{"text": "첫 줄 이야기", "chars": 5, "line": 0}],
         "cuts": [{"src": "a.mp4", "path": src, "ss": 1.0, "box": [100, 20, 300, 390], "crop": None, "pieces": [0], "move": None,
                   "src_dur": 8.0, "meme": False, "f0": 0, "n": 150}], "voice": "v", "S": {}}
    R = {"cut_median": {"v": 1.07, "why": "시험"}, "hook_cuts_3s": {"min": 2, "why": "시험"}}
    cfg = {"window": [540, 703], "cps": 8.8, "checks": {"length_s": {"allow": [1.0, 60.0]}}, "rhythm": R}
    G = PG.to_bench(w, cfg)
    bad = [x for x in PG.cut_gates(G, None, tmp_path) if x.startswith("리듬")]
    assert len(bad) == 2 and "cut_median" in bad[0] and "훅" in bad[1]   # 5초 한 컷 = 중앙 5초 > 1.39 · 훅 경계 0 < 2


# ── ③ 표지 카드 ─────────────────────────────────────────────────────────────
def _frames(p, n=4):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", "scale=54:96,format=gray", "-frames:v", str(n), "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.uint8).reshape(n, 96, 54).astype(int)


def test_cover_card_only_first_frames(tmp_path):
    from tools.calcopy.hybrid.thumb import THUMB_FRAMES
    M = json.loads((PDIR / "manifest.json").read_text(encoding="utf-8"))
    cfg = {**M["channel_rules"]["make"], "window": [540, 960]}
    cfg["cover_card"] = {**cfg["cover_card"], "px": 56, "stroke": 6}
    mat, vid = tmp_path / "mat.mp4", tmp_path / "video.mp4"
    _ff("-f", "lavfi", "-i", "color=c=gray:s=540x960:r=30:d=1", "-pix_fmt", "yuv420p", mat)
    _ff("-f", "lavfi", "-i", "color=c=gray:s=540x960:r=30:d=1", "-pix_fmt", "yuv420p", vid)
    doc = tmp_path / "doc"
    doc.mkdir()
    (doc / "썸네일.json").write_text(json.dumps({"options": [{"id": "A", "why": "시험", "lines": [["이거 절대", "main"], ["사지 마세요!", "accent"]]}], "pick": "A"},
                                             ensure_ascii=False), encoding="utf-8")
    before = _frames(vid)
    log = {}
    PM.cover_card({"dir": doc}, cfg, mat, [("k", 30)], vid, tmp_path, log)
    after = _frames(vid)
    diff = np.abs(after - before).mean(axis=(1, 2))
    assert all(diff[:THUMB_FRAMES] > 1) and all(diff[THUMB_FRAMES:] < 1.5), diff
    assert log["cover_card"]["pick"] == "A" and (doc / "thumb" / "A.jpg").exists()


# ── ④ 판 값 ─────────────────────────────────────────────────────────────────
def test_board_values_from_bench():
    from tools.calcopy.hybrid import styles as ST
    M = json.loads((PDIR / "manifest.json").read_text(encoding="utf-8"))
    mk = M["channel_rules"]["make"]
    assert mk["atempo_range"][1] <= 1.25
    assert not ST.rhythm_missing({"rhythm": mk["rhythm"]})
    assert mk["reuse"]["adjacent_run"] is True and mk["voice_name"] != "필재"
    F = json.loads((PDIR / "frame.json").read_text(encoding="utf-8"))
    cap = next(l for l in F["layers"] if l.get("role") == "caption")
    assert 6 <= cap["outline"]["px"] <= 8 and not cap.get("glow")      # 벤치 외곽 6~8px · 검은 번짐(glow) 없음
