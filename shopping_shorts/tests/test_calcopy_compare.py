# -*- coding: utf-8 -*-
"""칼카피 대조 도구(tools/calcopy/engine/compare.py) 시험.

합성 영상(1080×1920·6초): 밝은 배경 + 가운데 영상 창(testsrc2 → 반전 → mandelbrot, 2초마다 컷)
+ 창 아래 어두운 자막(1.5초마다 교체) + 440Hz 소리. 자는 bench 그대로(layout_mode="bench").
  1. 같은 영상을 원본·우리에 넣으면 모든 차 0, 판정 통과.
  2. 사보타주 — 우리 쪽 자막 띠를 ffmpeg로 300px 내려 붙이면 자막 자리 항목이 밖·판정 미달.
  3. 사보타주 — 우리 쪽 길이를 30% 자르면 길이 항목이 밖·판정 미달.
  4. ② 규칙 수준: --rules-json 이 없으면 failed:미측정(판정은 ①만), 규칙이 어긋나면 ② 밖이지만 판정은 그대로.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                reason="ffmpeg 없음")

CAP_Y = 1480          # 자막 글자 윗변 y
CAP_BOX = (1440, 140)  # 사보타주 때 옮길 띠 [y0, 높이] — 글자(64px)+외곽선을 넉넉히 덮는다
BG = "0xF0F0F0"
TEXTS = ["Hello world caption", "Second line here", "Short one", "A much longer caption text"]


def _font(dirpath: Path) -> str:
    for f in ("C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        if os.path.exists(f):
            shutil.copy(f, dirpath / "font.ttf")
            return "font.ttf"
    pytest.skip("drawtext 글꼴 없음")


def _ff(args, cwd):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], cwd=str(cwd), capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")


def make_synth(dirpath: Path, name: str = "syn.mp4") -> Path:
    font = _font(dirpath)  # 상대경로로 넘긴다(윈도 드라이브 콜론이 drawtext 파서를 깬다)
    dt = "".join(
        f",drawtext=fontfile={font}:text='{t}':fontsize=64:fontcolor=black:borderw=4:bordercolor=red"
        f":x=(w-tw)/2:y={CAP_Y}:enable='between(t,{i * 1.5},{(i + 1) * 1.5})'" for i, t in enumerate(TEXTS))
    _ff(["-f", "lavfi", "-i", f"color=c={BG}:s=1080x1920:r=30:d=6",
         "-f", "lavfi", "-i", "testsrc2=s=1080x1000:r=30:d=2",
         "-f", "lavfi", "-i", "testsrc2=s=1080x1000:r=30:d=2,negate",
         "-f", "lavfi", "-i", "mandelbrot=s=1080x1000:r=30,trim=duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=6",
         "-filter_complex", f"[1][2][3]concat=n=3:v=1:a=0,setpts=PTS-STARTPTS[w];[0][w]overlay=0:420:shortest=1{dt}[v]",
         "-map", "[v]", "-map", "4:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         "-c:a", "aac", "-shortest", name], dirpath)
    return dirpath / name


def sabotage_caption_down(src: Path, dst: Path, dy: int = 300) -> Path:
    """자막 띠를 잘라 배경색으로 지우고 dy px 아래에 다시 붙인다."""
    y0, h = CAP_BOX
    _ff(["-i", str(src), "-filter_complex",
         f"[0:v]split[a][b];[b]crop=1080:{h}:0:{y0}[c];[a]drawbox=x=0:y={y0}:w=1080:h={h}:color={BG}:t=fill[d];"
         f"[d][c]overlay=0:{y0 + dy}[v]", "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "18", "-c:a", "copy", str(dst)], src.parent)
    return dst


def sabotage_trim(src: Path, dst: Path, keep: float = 0.7) -> Path:
    _ff(["-i", str(src), "-t", f"{6 * keep:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         "-c:a", "aac", str(dst)], src.parent)
    return dst


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    d = tmp_path_factory.mktemp("calcopy_cmp")
    return make_synth(d)


def _cmp():
    from tools.calcopy.engine import compare
    return compare


def _row(res, key):
    return next(r for r in res["rows"] if r["key"] == key)


def test_same_video_all_zero_and_pass(synth, tmp_path):
    compare = _cmp()
    res = compare.compare(str(synth), str(synth), str(tmp_path / "out"), layout_mode="bench")
    v = res["verdict"]
    assert v["verdict"] == "통과", (v, [r for r in res["rows"] if r["layer"] == "pixel" and r["status"] not in ("in", "참고")])
    # 기준 있는 항목이 실제로 재졌는지(빈 측정으로 통과하는 가짜 통과 차단)
    crit = [r for r in res["rows"] if r["key"] in compare.TOL]
    assert len(crit) >= 15 and all(r["status"] == "in" for r in crit)
    assert all(r["orig"] is not None and r["orig"] == r["ours"] for r in crit)
    for r in crit:  # 모든 차 0
        d = r["diff"]
        assert d in (0, 0.0, "같음") or (isinstance(d, str) and (d.startswith("0 (0.0%)") or d.startswith("0.0 (0.0%)")
                                                               or d.startswith("0.0px (0.0%"))), (r["key"], d)
    # 측정값이 합성 설계와 맞는지(자가 엉뚱한 곳을 재고 있지 않은지)
    assert abs(_row(res, "frame.window")["orig"][1] - 420) <= 4
    assert abs(_row(res, "cap.top_y")["orig"] - CAP_Y) <= 20
    assert _row(res, "frame.caption_pos")["orig"] == "below"
    assert abs(_row(res, "len.duration")["orig"] - 6.0) < 0.1
    out = tmp_path / "out"
    for f in ("차이표.json", "차이표.md", "side_by_side.jpg", "verdict.json"):
        assert (out / f).exists() and (out / f).stat().st_size > 0, f
    assert json.loads((out / "verdict.json").read_text(encoding="utf-8"))["verdict"] == "통과"
    from PIL import Image
    assert Image.open(out / "side_by_side.jpg").size == (270 * 8, 28 + (480 + 28) * 2)


def test_sabotage_caption_down_300px(synth, tmp_path):
    compare = _cmp()
    bad = sabotage_caption_down(synth, synth.parent / "cap_down.mp4")
    res = compare.compare(str(synth), str(bad), str(tmp_path / "out"), layout_mode="bench")
    assert res["verdict"]["verdict"] == "미달"
    top = _row(res, "cap.top_y")
    assert top["status"] == "out", top
    assert top["ours"] - top["orig"] > 250
    assert _row(res, "frame.caption_band")["status"] == "out"
    assert _row(res, "len.duration")["status"] == "in"
    assert "첫 줄 y 중앙(px)" in res["verdict"]["out"]


def test_sabotage_trim_30pct(synth, tmp_path):
    compare = _cmp()
    bad = sabotage_trim(synth, synth.parent / "trim.mp4")
    res = compare.compare(str(synth), str(bad), str(tmp_path / "out"), layout_mode="bench")
    assert res["verdict"]["verdict"] == "미달"
    d = _row(res, "len.duration")
    assert d["status"] == "out", d
    assert abs(d["ours"] - 4.2) < 0.1
    assert "길이(초, 프레임÷fps)" in res["verdict"]["out"]


def _rules(sfx_t, memes, dur=6.0, duck=-6.0, genders=("female",)):
    """뜯기.json(analyze.py) 꼴의 최소 사본 — 읽는 길(경로)만 시험한다."""
    return {"audio": {"composition": {
                "sfx_per_sec": round(len(sfx_t) / dur, 3),
                "sfx": {"count": len(sfx_t), "first": [[t, 0.1] for t in sfx_t]},
                "duck_db": duck,
                "speakers": [{"n": f"S{i + 1}", "gender": g} for i, g in enumerate(genders)]}},
            "materials": {"ok": True, "per_shot": [{"shot": i, "t": [a, b], "kind": "짤·밈"} for i, (a, b) in enumerate(memes)]
                          + [{"shot": 99, "t": [5.0, 6.0], "kind": "스톡영상"}]}}


def test_rules_layer_reported_not_judged(synth, tmp_path):
    compare = _cmp()
    # (a) 뜯기.json 없음 → ② 는 미측정, mix.lufs 만 bench 로 재짐. 판정은 ① 만 보고 통과.
    res = compare.compare(str(synth), str(synth), str(tmp_path / "a"), layout_mode="bench")
    rule = {r["key"]: r for r in res["rows"] if r["layer"] == "rule"}
    assert set(rule) == set(compare.RULE_TOL)
    assert rule["mix.lufs"]["status"] == "in" and rule["mix.lufs"]["orig"] is not None
    assert all(r["status"].startswith("failed:") and "미측정" in r["status"] for k, r in rule.items() if k != "mix.lufs")
    assert res["verdict"]["verdict"] == "통과"
    # (b) 같은 규칙 → ② 전부 안(배경음 둘·말속도는 자료가 없어 미측정으로 남는다)
    same = _rules([1.5, 3.0, 4.6], [(0.0, 2.0)])
    po, pu = tmp_path / "o.json", tmp_path / "u.json"
    po.write_text(json.dumps(same, ensure_ascii=False), encoding="utf-8")
    pu.write_text(json.dumps(same, ensure_ascii=False), encoding="utf-8")
    res = compare.compare(str(synth), str(synth), str(tmp_path / "b"), layout_mode="bench", picture=False,
                          rules_orig=str(po), rules_ours=str(pu))
    rule = {r["key"]: r for r in res["rows"] if r["layer"] == "rule"}
    for k in ("sfx.per_sec", "sfx.after_event", "bgm.duck", "meme.count", "meme.pos", "voice.gender", "voice.roles"):
        assert rule[k]["status"] == "in", (k, rule[k])
    assert rule["sfx.after_event"]["orig"] > 0  # 1.5·3.0초 = 합성 영상의 자막 교체 시각 → 붙음으로 잡혀야 한다
    assert rule["meme.pos"]["orig"] == {"훅": 1, "중간": 0, "끝": 0}
    # (c) 규칙 어긋남(효과음 3→9발, 짤 1→4개, 목소리 여→남, 덕킹 −6→−12) → ② 밖, 그래도 판정은 ① 만 → 통과
    diff = _rules([0.3, 0.9, 1.1, 2.4, 2.7, 3.3, 3.9, 4.4, 5.2], [(0, 1), (1, 2), (2.5, 3.5), (4.5, 5.5)],
                  duck=-12.0, genders=("male",))
    pu.write_text(json.dumps(diff, ensure_ascii=False), encoding="utf-8")
    res = compare.compare(str(synth), str(synth), str(tmp_path / "c"), layout_mode="bench", picture=False,
                          rules_orig=str(po), rules_ours=str(pu))
    rule = {r["key"]: r for r in res["rows"] if r["layer"] == "rule"}
    for k in ("sfx.per_sec", "meme.count", "meme.pos", "voice.gender", "bgm.duck"):
        assert rule[k]["status"] == "out", (k, rule[k])
    v = res["verdict"]
    assert v["verdict"] == "통과" and "짤 개수/편" in v["rules_out"]
    md = (tmp_path / "c" / "차이표.md").read_text(encoding="utf-8")
    assert "## ① 픽셀 수준" in md and "## ② 규칙 수준" in md
