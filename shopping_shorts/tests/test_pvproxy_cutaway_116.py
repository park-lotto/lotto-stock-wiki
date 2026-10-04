"""관제 116 — 끼움 장면(AI 장면 등, beat.cutaway)이 붙은 칸은 편집 화면 합본에서도 완성본과 같은 구간에 그 장면이 나온다.

왜 (2026-10-04 사장님 "AI 장면을 넣었는데 어디서 보나 / 만들면 미리보기에 다시 적용돼야지", job f3d86941c30b 2번 칸):
  완성본(_render_mix)은 끼움 장면을 [0, min(자산 길이, 칸 길이)]에 풀프레임으로 얹는데, 편집 화면 합본(_pvproxy_build)은 컷만 구웠다.
검사: 어두운 합성 원본(프레임 번호 = 밝기) + 흰 끼움 장면 0.6초 → 합본·완성본을 **실제로 굽고** 흰 프레임 수가 같은지 본다.
"""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import video_assemble as va

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg 없음")

_P = Path(__file__).resolve().parent / "test_first_frame_no_dup.py"
_sp = importlib.util.spec_from_file_location("_ffnd116", str(_P))
H = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(H)

WHITE = 60          # H._levels 눈금으로 이보다 크면 흰 끼움 장면(원본은 2초·60프레임이라 60 미만)


def _white(tmp_path, sec):
    p = tmp_path / "cw.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=white:s=180x320:r=30:d={sec}",
                    "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(p)], check=True, stdin=subprocess.DEVNULL)
    return str(p)


def _editor(tmp_path, monkeypatch, src, tts, dur, cw):
    from shopping_shorts import app

    class _Store:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, *_a, **_k):
            return {"edit_plan": {"beats": [{"beat_idx": 0, **({"cutaway": {"asset_id": 1, "match_type": "ai"}} if cw else {})}]}}

    pv = tmp_path / ("pv1" if cw else "pv0")
    monkeypatch.setattr(app, "Store", _Store)
    monkeypatch.setattr(app, "_pvproxy_dir", lambda _j: pv)
    monkeypatch.setattr(app, "_pvproxy_cutaways", lambda _job: ({0: cw} if cw else {}))
    app._pvproxy_build("cwjob", "sigcw", [{"video_id": "V", "start": 0.0, "dur": dur, "src_dur": dur}],
                       {"V": src}, [1], {0: tts})
    out = pv / "sigcw.mp4"
    assert out.exists()
    return out


def _final(tmp_path, monkeypatch, src, tts, dur, cw):
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [
        {"video_id": "V", "seg_id": "V-0", "start": 0.0, "src_dur": dur, "out_dur": dur}])
    monkeypatch.setattr(va, "_trans_sec", lambda: 0.0)
    beat = {"beat_idx": 0, "narration": "테스트", "primary": {"video_id": "V", "seg_id": "V-0", "start": 0.0, "end": 2.0}}
    work = tmp_path / "final"
    work.mkdir()
    return va._render_mix({"beats": [beat]}, {0: tts}, {"V": src}, work, cutaway_paths={0: cw})


def test_끼움_장면이_합본에도_완성본과_같은_구간에_나온다(tmp_path, monkeypatch):
    src = H._make_src(tmp_path, "30")
    tts = H._tts(tmp_path, 1.5)
    cw = _white(tmp_path, 0.6)
    el = H._levels(_editor(tmp_path, monkeypatch, src, tts, 1.5, cw))
    fl = H._levels(_final(tmp_path, monkeypatch, src, tts, 1.5, cw))
    ew = [i for i, x in enumerate(el) if x > WHITE]
    fw = [i for i, x in enumerate(fl) if x > WHITE]
    assert len(el) == len(fl) == 45, (len(el), len(fl))
    assert ew and ew[0] == 0, "합본 첫 프레임부터 끼움 장면이어야 한다: %s" % el[:5]
    assert abs(len(ew) - 18) <= 1, "끼움 장면 0.6초 = 18프레임: %d" % len(ew)
    assert abs(len(ew) - len(fw)) <= 1, "합본 %d프레임 vs 완성본 %d프레임" % (len(ew), len(fw))
    assert el[-1] < WHITE, "창이 끝나면 담은 장면으로 돌아온다"


def test_끼움_장면이_없으면_종전_그대로(tmp_path, monkeypatch):
    src = H._make_src(tmp_path, "30")
    tts = H._tts(tmp_path, 1.5)
    el = H._levels(_editor(tmp_path, monkeypatch, src, tts, 1.5, None))
    assert not [x for x in el if x > WHITE]


def test_서명은_끼움_장면이_붙은_칸만_달라진다(tmp_path):
    from shopping_shorts import app
    cuts = [{"video_id": "V", "start": 0.0, "dur": 1.0}]
    beat = {"beat_idx": 0}
    cw = _white(tmp_path, 0.6)
    s0 = app._pvproxy_sig(cuts, [1], app._pvproxy_beat_meta([beat]))
    assert app._pvproxy_sig(cuts, [1], app._pvproxy_beat_meta([beat], {})) == s0      # 안 붙은 작업은 서명 그대로
    assert app._pvproxy_sig(cuts, [1], app._pvproxy_beat_meta([beat], {0: cw})) != s0


def test_규칙_함수_창은_짧은_쪽():
    assert va.cutaway_overlay(6.0, 4.8, 720, 1280)[0] == 4.8
    assert va.cutaway_overlay(2.0, 4.8, 720, 1280)[0] == 2.0
    assert "between(t,0,2.000)" in va.cutaway_overlay(2.0, 4.8, 720, 1280)[1]
