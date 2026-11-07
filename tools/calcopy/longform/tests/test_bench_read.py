# bench_read.measure 시험 — ffmpeg 합성 영상(파랑 정지 3초 · testsrc 움직임 3초 · 빨강 정지 3초 = 컷 2개)으로 컷·정지·챕터·cps 를 맞게 재나.
import os, subprocess, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
import pytest
from tools.calcopy.longform.steps import bench_read as BR


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    d = tmp_path_factory.mktemp("br")
    mp4 = str(d / "s.mp4")
    fc = ("color=c=blue:s=640x360:r=30:d=3[a];testsrc=s=640x360:r=30:d=3[b];color=c=red:s=640x360:r=30:d=3[c];"
          "[a][b][c]concat=n=3:v=1:a=0,format=yuv420p[v];sine=f=440:d=9[s]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", fc, "-map", "[v]", "-map", "[s]", "-c:v", "libx264", "-c:a", "aac", mp4], check=True)
    vtt = d / "s.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n가나다 라마\n\n00:00:04.000 --> 00:00:06.000\n바사아자\n", encoding="utf-8")
    return mp4, str(vtt)


def test_cuts_still_chapters_cps(synth):
    mp4, vtt = synth
    m = BR.measure(mp4, vtt=vtt, chapters=[0, 3, 6])
    assert m["cut.n"] == 2, m["cut.at"]
    assert all(abs(a - b) < 0.2 for a, b in zip(m["cut.at"], [3.0, 6.0]))
    assert abs(m["len.duration"] - 9.0) < 0.2
    assert abs(m["cut.median"] - 3.0) < 0.2
    assert abs(m["still.rate"] - 2 / 3) < 0.08              # 파랑·빨강 정지, testsrc 는 움직임
    assert m["chapter.n"] == 3 and abs(m["chapter.sec"] - 3.0) < 0.2 and m["hook.sec"] == 3.0
    assert abs(m["speech.cps"] - 9 / 4.0) < 0.01             # 공백 뺀 9글자 ÷ 말한 4초
    assert m["shot_mix"] == "미측정" and m["caption"] == "없음"
    assert isinstance(m["mix.lufs"], float)


def test_missing_inputs_are_unmeasured(synth):
    mp4, _ = synth
    m = BR.measure(mp4)
    assert m["chapter.n"] == "미측정" and m["speech.cps"] == "미측정"


def test_screen_json_shot_mix(synth, tmp_path):
    mp4, _ = synth
    sj = tmp_path / "x_screen.json"
    sj.write_text('{"shots":[{"t0":0,"t1":3,"kind":"글자 카드"},{"t0":3,"t1":9,"kind":"실사영상"}]}', encoding="utf-8")
    m = BR.measure(mp4, screen_json=str(sj))
    assert abs(m["shot_mix"]["실사영상"] - 2 / 3) < 0.01 and m["screen.n_shots"] == 2


def test_dissolve_is_a_cut(tmp_path):
    """디졸브 1초(검정→흰→검정): 옛 자 scene>0.3 은 못 잡고(cut.scene_n) 컷 주인 _cuts 는 2개 잡아야 한다 — 모둠경제 전환 꼴."""
    mp4 = str(tmp_path / "d.mp4")
    fc = ("color=c=black:s=640x360:r=30:d=5[a];color=c=white:s=640x360:r=30:d=5[b];color=c=black:s=640x360:r=30:d=5[c];"
          "[a][b]xfade=transition=fade:duration=1:offset=4[ab];[ab][c]xfade=transition=fade:duration=1:offset=8,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", mp4], check=True)
    m = BR.measure(mp4)
    assert m["cut.scene_n"] < 2, m["cut.scene_at"]           # scene>0.3 은 디졸브를 놓친다(옛 자가 실패하는 꼴)
    assert m["cut.n"] == 2, m["cut.at"]
    assert all(abs(a - b) <= 0.75 for a, b in zip(m["cut.at"], [4.5, 8.5]))


def test_caption_change_keeps_still(tmp_path):
    """정지 그림 + 아래 자막 띠만 1초마다 바뀜 → 정지 1.0(띠는 정지 판정에서 뺀다). 전체 프레임으로 재면 움직임으로 잡힌다."""
    mp4 = str(tmp_path / "c.mp4")
    vf = ("drawbox=x=200:y=290:w=240:h=30:color=white:t=fill:enable='lt(mod(t,2),1)',"
          "drawbox=x=120:y=290:w=400:h=30:color=white:t=fill:enable='gte(mod(t,2),1)',format=yuv420p")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=640x360:r=30:d=8", "-vf", vf, "-c:v", "libx264", mp4], check=True)
    m = BR.measure(mp4)
    assert m["cut.n"] == 0 and m["still.rate"] == 1.0
    import numpy as np
    _, fr, _ = BR._decode(mp4, False)
    full = np.abs(np.diff(fr.astype(np.float32), axis=0)).mean(axis=(1, 2))
    assert np.percentile(full, 90) >= BR.STILL_TH                # 띠를 넣으면 정지 아님으로 잡혔을 것
