"""장면 자동 맞춤(B, 사장님 10-26 "글자가 많으면 자막을 지우면 되고, 조각이 짧거나 길면 숏템메이커처럼 늘리기").

주인: 컷을 원본 샷 안에 맞추는 시작 초·속도 = render_bench.fit_cut 하나(늦춤 하한 = shopping_shorts.config.MAX_SLOWMO) ·
      원본에서 쓰는 프레임 = src_frames(관문 ③④·접촉 시트·VMake 구간이 같이 읽음) · 조각 늦추기 = clip_cmd setpts ·
      박힌 글자 지우는 판의 글자 컷 = cut_content_gate(erase=[]) → timeline.vmake_cuts.
옛 코드: fit_cut·src_frames·erase 가 없어(컷이 샷보다 길면 '샷보다 길다'로 멈춤, 글자 컷도 멈춤) 이 시험이 실패한다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

FPS = RB.FPS


@pytest.fixture
def src(tmp_path, monkeypatch):
    """샷 경계 [0, 10, 20] 인 가짜 원본(파일은 빈 것 — 경계·남은 길이·첫 프레임 초는 가짜 함수)."""
    p = tmp_path / "a.mp4"
    p.write_bytes(b"x")
    monkeypatch.setattr(RB, "shot_starts", lambda s: [0.0, 10.0, 20.0])
    monkeypatch.setattr(RB, "src_left", lambda s, t: 30.0 - t)
    monkeypatch.setattr(RB, "src_start", lambda s, t: t)
    monkeypatch.setattr(RB, "snap_ss", lambda s, ss, dur, reach=0.4: ss)
    return p


def test_fits_as_is(src):
    """샷 안에 제 속도로 들어가면 그대로(속도 1)."""
    assert RB.fit_cut(src, 2.0, 60, cap=8.0) == (2.0, 1.0)


def test_longer_than_shot_is_slowed_within_cap(src):
    """재료 max(그 샷 끝까지 초) 1.8초에 화면 2초 컷 — 옛 코드는 '샷보다 길다'로 멈췄다. 새 = 1.2배 안에서 늦춰 채움."""
    ss, k = RB.fit_cut(src, 8.2, 60, cap=1.8)
    assert 1 / RB._max_slowmo() - 1e-6 <= k < 1.0
    assert round(60 * k) / FPS <= 1.8 + 1e-3 - (ss - 8.2)


def test_too_long_even_slowed_is_left_for_gate(src):
    """1.2배로 늦춰도 안 되면 그대로 둔다(관문이 잡는다 — 더 늦추거나 멈춤 프레임을 넣지 않는다)."""
    assert RB.fit_cut(src, 8.5, 60, cap=1.2)[1] == 1.0


def test_src_frames_reads_speed():
    c = {"t0": 0.0, "t1": 2.0, "speed": 0.9}
    assert RB.src_frames(c) == 54 and RB.src_frames({"t0": 0.0, "t1": 2.0}) == 60


def test_clip_cmd_slows_with_setpts(src):
    """늦춘 컷 = 원본 n×speed 프레임을 n 프레임으로 고르게(setpts 가 fps 앞) — 멈춤 프레임 없음."""
    _, vf, _ = RB.clip_cmd(src, 1.0, 60, [0, 0, 100, 100], (100, 100), speed=0.9)
    assert "setpts=(PTS-STARTPTS)/0.900000,fps=" in vf
    _, vf1, _ = RB.clip_cmd(src, 1.0, 60, [0, 0, 100, 100], (100, 100))
    assert "setpts" not in vf1


def test_text_cut_goes_to_erase_list(src, monkeypatch, tmp_path):
    """박힌 글자를 지우는 판(erase 목록을 줌) — 글자 컷은 멈추지 않고 erase 에 컷 번호. 얼굴은 그대로 멈춤. 목록 없으면 옛 동작(멈춤)."""
    monkeypatch.setattr(RB, "cut_crop", lambda c, s, win: [0, 0, 100, 100])
    monkeypatch.setattr(RB, "cut_frames", lambda reqs, jobs=None: [None] * len(reqs))
    hit = {"box": [1, 2, 3, 4]}
    monkeypatch.setattr(RB, "cut_content_feats", lambda *a, **k: {"text": [[hit], [hit], [hit]], "face": []})
    monkeypatch.setattr(RB, "foreign_text", lambda f: True)
    T = {"cuts": [{"src": "a.mp4", "ss": 1.0, "t0": 0.0, "t1": 1.0, "line": "L1"}], "end": 1.0}
    M = {"cand_dir": str(tmp_path)}
    st = {"frame": {"kind": "window", "window": [0, 0, 100, 100]}}
    er = []
    assert RB.cut_content_gate(T, M, st, None, None, log=lambda *a: None, erase=er) == [] and er == [0]
    assert RB.cut_content_gate(T, M, st, None, None, log=lambda *a: None)
