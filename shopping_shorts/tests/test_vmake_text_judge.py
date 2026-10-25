# -*- coding: utf-8 -*-
"""관제 271 — 웹 라인 VMake: 고객이 장면을 안 골랐으면 **자동 글자 판정으로 자막 있는 컷만** 보낸다.

결과물 검사 = 업체로 실제 넘긴 파일 길이(가짜 업체가 ffprobe 로 잰다) ≤ 글자 있는 컷 합 + 반올림.
★옛 코드(6a9ea6b70)에서는 고객이 안 고르면 조립본 전체(6초)를 보냈다 — 이 시험이 빨강이었다.
판정 자(burned_text)는 칼카피 관문 ④ foreign_text 를 옮긴 것 — 표본 시험은 칼카피 표본이 있으면 같은 P/R 을 확인한다.
"""
import json
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp

TOL = 0.5
ROOT = Path(__file__).resolve().parents[2]


def _dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def _mk(path, sec):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=160x284:rate=30:duration={sec}",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(sec), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return str(path)


CUTS = [{"beat_idx": 0, "video_id": "s0", "src": 0.0, "fin": 0.0, "dur": 2.0},
        {"beat_idx": 1, "video_id": "s1", "src": 0.0, "fin": 2.0, "dur": 2.0},
        {"beat_idx": 2, "video_id": "s2", "src": 0.0, "fin": 4.0, "dur": 2.0}]


def test_보낼_컷_주인_자동판정():
    c = CUTS
    assert mp.vmake_send_cuts(c, None, [False, True, None]) == [c[1], c[2]]      # 못 잰 컷은 보낸다
    assert mp.vmake_send_cuts(c, None, None) == c                                # 판정기 없음 = 확정 컷 전부
    assert mp.vmake_send_cuts(c, None, [False, False, False]) == c               # 전부 '없음' = 판정 불신 → 전부
    assert mp.vmake_send_cuts(c, ["0|s0|0.00"], [False, True, True]) == [c[0]]  # 고객 선택이 이긴다
    assert mp.vmake_send_cuts(c, None, [True]) == c                              # 길이 안 맞는 판정은 안 쓴다
    info = mp.vmake_text_info(c, [False, True, None], [c[1], c[2]])
    assert info["sent"] == 2 and info["skipped"] == [0.0] and info["unsure"] == 1


def test_고객이_안_고르면_글자_있는_컷만_업체로(monkeypatch, tmp_path):
    raw = _mk(tmp_path / "mix_raw.mp4", 6)
    sent = []

    def fake_remove(video, key, out_path, **kw):
        sent.append(_dur(video))
        Path(out_path).write_bytes(Path(video).read_bytes())
        return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 0)
    monkeypatch.setattr(mp, "_va_read_cut_map", lambda p: [dict(x) for x in CUTS])
    monkeypatch.setattr(mp, "vmake_cut_text", lambda v, cuts, work=None: [False, True, False])
    job = {"job_id": "j", "edit_plan": {"beats": []}, "subtitle_removal": 1}
    fn = mp._final_clean_fn(None, job, "j", tmp_path, ["k"], 0)
    fn(raw)
    assert len(sent) == 1 and sent[0] <= 2.0 + TOL, f"보낸 초 {sent} — 글자 있는 컷 1개(2초)만 보내야 한다"
    rows = json.loads((tmp_path / mp.VMAKE_LEDGER).read_text(encoding="utf-8"))
    assert rows[-1]["text"]["sent"] == 1 and rows[-1]["text"]["skipped"] == [0.0, 4.0]
    assert mp.vmake_sent_check(rows[-1]["sec"], rows[-1]["allow"]) == []


def _mk_sub(path):
    """앞 2초: 움직이는 화면 + 아래 박힌 자막 / 뒤 2초: 움직이는 화면만."""
    font = "C\\:/Windows/Fonts/arial.ttf" if Path("C:/Windows/Fonts/arial.ttf").exists() else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    vf = ("drawtext=fontfile='%s':text='Poop clicker for fun':fontsize=64:fontcolor=white:borderw=4:bordercolor=black:"
          "x=(w-tw)/2:y=h*0.72:enable='lt(t,2)'" % font)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "mandelbrot=size=720x1280:rate=30", "-t", "4",
                    "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return str(path)


def test_진짜_판정기_박힌_자막_컷만_참(tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("onnxruntime")
    from shopping_shorts.channelkit import vision as V
    if [m for m in V.models_missing() if m.endswith(V.OCRDET)]:
        pytest.skip("글자 모델 없음")
    v = _mk_sub(tmp_path / "sub.mp4")
    cuts = [{"fin": 0.0, "dur": 2.0}, {"fin": 2.0, "dur": 2.0}]
    assert mp.vmake_cut_text(v, cuts, tmp_path) == [True, False]
    assert json.loads((tmp_path / mp.VMAKE_TEXT_CACHE).read_text(encoding="utf-8"))["text"] == [True, False]


def test_옮긴_판정이_칼카피_표본과_같은_정밀도_재현율():
    fx = ROOT / "shopping_shorts/tests/fixtures/cut_content_labels.json"
    if not fx.exists():
        pytest.skip("칼카피 표본 없음(칼카피 트랙 병합 뒤 생긴다)")
    from shopping_shorts.channelkit.vision import burned_text as BT
    F = json.loads(fx.read_text(encoding="utf-8"))["text"]
    rows = F["rows"]
    tp = sum(1 for r in rows if r["label"] == "pos" and BT.cut_hit(r["frames"]))
    fp = sum(1 for r in rows if r["label"] == "neg" and BT.cut_hit(r["frames"]))
    fn = sum(1 for r in rows if r["label"] == "pos" and not BT.cut_hit(r["frames"]))
    assert tp / max(1, tp + fp) >= F["min_precision"] and tp / max(1, tp + fn) >= F["min_recall"]
