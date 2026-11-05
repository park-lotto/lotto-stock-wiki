"""#4085·#4089(11-04 박영상): 원음 줄 O4 spans 59.9~62.6 이 원본 화면 끝(약 62.4)을 넘어 계획 'cut_len' 반려 3번 연속.
같은 판단('원음 구간이 원본 화면 안인가')을 조사 검사(flow, 파일 길이 + 0.5 여유)와 계획(render_bench.src_left, 영상 길이 − 1프레임)이 따로 했고,
대본 단계엔 검사가 없었다. 판단 주인 = common.orig_span_over 한 곳 — 조사·대본 검사(flow)와 계획(src_left)이 같은 화면 끝을 본다."""
import subprocess

from tools.calcopy.hybrid import common as C
from tools.calcopy.hybrid import flow as FL
from tools.calcopy.hybrid import render_bench as RB
from tools.calcopy.hybrid import runner_ops as RO


def test_화면_끝_기준():
    f = {"name": "o.mp4", "dur": 62.6, "vdur": 62.4}
    assert C.orig_span_over(62.6, f) > 0.2          # 화면 끝 = 62.4 − 1/30
    assert C.orig_span_over(62.2, f) == 0
    assert C.orig_span_over(62.6, {"name": "o.mp4", "dur": 62.5}) == 0     # 영상 길이를 모르는 옛 엔진 = 옛 기준(파일 길이 + 0.5)


def test_대본_단계에서_바로_반려():
    st = {"origin": {"files": [{"name": "o.mp4", "dur": 62.6, "vdur": 62.4}]}}
    S = {"lines": [{"id": "O4", "kind": "orig", "src": "o.mp4", "spans": [[59.9, 62.6]]},
                   {"id": "O5", "kind": "orig", "src": "o.mp4", "spans": [[10.0, 12.0]]}]}
    bad = FL.orig_end_problems(st, S)
    assert len(bad) == 1 and "O4" in bad[0] and "62.6" in bad[0]


def test_실행기는_영상_길이를_따로_재고_계획과_같다(tmp_path):
    p = tmp_path / "a.mp4"       # 소리가 화면보다 0.5초 긴 원본(파일 길이 ≠ 화면 길이)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x64:r=30:d=2", "-f", "lavfi", "-i", "sine=d=2.5",
                    "-c:v", "libx264", "-c:a", "aac", str(p)], check=True)
    d = RO.dims(p)
    assert d["vdur"] < d["dur"] - 0.3
    assert abs(RB.src_left(p, 0.0) - (d["vdur"] - 1 / C.FPS)) < 0.01
