# -*- coding: utf-8 -*-
"""VMake 규칙(사장님 10-26 "어떤 영상이든 동일 — 장면 편집 뒤 자막 있는 컷만") — 웹 라인 결과물 검사.

검사 = 업체로 **실제 넘긴 파일 길이**(가짜 업체가 ffprobe 로 잰다) ≤ 보낼 컷 합 + VMAKE_SENT_TOL.
★옛 코드(소스별 청소가 원본 통째를 보내던 길)에서 이 검사가 빨강인지 먼저 확인했다(관제 270 핸드오프).
"""
import json
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp

TOL = 0.5


def _mk(path, sec):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=160x284:rate=30:duration={sec}",
                    "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", str(sec), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return str(path)


def _dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


class _Store:
    def __init__(self, job):
        self._job = job
    def get_mix_job(self, _):
        return self._job
    def update_mix_job(self, _, **f):
        self._job.update(f)
    def get_setting(self, *_a, **_k):
        return "appkey:secret"


def _fake_vendor(monkeypatch, sent):
    def fake_remove(video, key, out_path, **kw):
        sent.append(_dur(video))
        Path(out_path).write_bytes(Path(video).read_bytes())
        return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 0)


def test_원본_통째_길은_검사에_걸린다_그리고_새_코드는_안_보낸다(monkeypatch, tmp_path):
    """옛 job: 소스 s0 은 지워 둠, s1(20초 원본)은 편성에서 2초만 쓴다 → 소스별 길이 s1 원본 통째를 보내면 빨강."""
    s0 = _mk(tmp_path / "s0.mp4", 3)
    s1 = _mk(tmp_path / "s1.mp4", 20)
    c0 = tmp_path / "clean_src_s0.mp4"
    c0.write_bytes(Path(s0).read_bytes())
    plan = {"beats": [{"beat_idx": 0, "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}},
                      {"beat_idx": 1, "primary": {"video_id": "s1", "start": 5.0, "end": 7.0}}]}
    job = {"job_id": "j", "edit_plan": plan, "clean_sources": {"s0": str(c0)}, "subtitle_removal": 1}
    monkeypatch.setattr(mp, "_resolve_sources", lambda j, w: {"s0": s0, "s1": s1})
    sent = []
    _fake_vendor(monkeypatch, sent)
    try:
        mp._ensure_clean_sources(_Store(job), job, "j", str(tmp_path), ["k"], 0)
    except RuntimeError:
        pass                                        # 새 코드: 관문이 멈춘다(업체 0)
    allow = 2.0                                     # s1 이 화면에 쓰는 초
    bad = [s for s in sent if s > allow + TOL]
    assert not bad, f"원본 통째 전송: {bad}초 > 쓰는 {allow}초"


def test_소스별_재사용은_편성_소스를_다_덮을_때만(monkeypatch, tmp_path):
    c0 = tmp_path / "c0.mp4"; c0.write_text("x")
    plan = {"beats": [{"beat_idx": 0, "primary": {"video_id": "s0", "start": 0, "end": 2}},
                      {"beat_idx": 1, "primary": {"video_id": "s1", "start": 0, "end": 2}}]}
    assert mp._clean_strategy({"edit_plan": plan, "clean_sources": {"s0": str(c0)}}) == "final"
    c1 = tmp_path / "c1.mp4"; c1.write_text("x")
    assert mp._clean_strategy({"edit_plan": plan, "clean_sources": {"s0": str(c0), "s1": str(c1)}}) == "sources"
    assert mp._clean_strategy({"edit_plan": plan}) == "final"


def test_주인을_안_거친_호출은_업체_0(monkeypatch, tmp_path):
    v = _mk(tmp_path / "a.mp4", 2)
    sent = []
    _fake_vendor(monkeypatch, sent)
    monkeypatch.setattr(mp, "_vmake_gate", mp._vmake_gate)
    with pytest.raises(RuntimeError):
        mp._vmake_clean(v, ["k"], str(tmp_path / "o.mp4"))
    with pytest.raises(RuntimeError):               # 허용보다 길면 거절
        mp._vmake_clean(v, ["k"], str(tmp_path / "o.mp4"), send={"kind": "t", "allow": 1.0, "work": str(tmp_path)})
    assert sent == []
    mp._vmake_clean(v, ["k"], str(tmp_path / "o.mp4"), send={"kind": "t", "allow": 2.0, "work": str(tmp_path)})
    assert len(sent) == 1
    rows = json.loads((tmp_path / mp.VMAKE_LEDGER).read_text(encoding="utf-8"))
    assert rows[-1]["kind"] == "t" and abs(rows[-1]["sec"] - 2.0) < 0.1 and rows[-1]["allow"] == 2.0


def test_보낼_컷_주인과_검사():
    cuts = [{"beat_idx": 0, "video_id": "s0", "src": 1.0, "fin": 0.0, "dur": 2.0},
            {"beat_idx": 1, "video_id": "s1", "src": 4.0, "fin": 2.0, "dur": 3.0}]
    assert mp.vmake_send_cuts(cuts, None) == cuts
    assert mp.vmake_send_cuts(cuts, ["1|s1|4.00"]) == [cuts[1]]
    assert mp.vmake_allow_sec(cuts) == 5.0
    assert mp.vmake_sent_check(5.4, 5.0) == []
    assert mp.vmake_sent_check(20.0, 5.0)
    assert mp.vmake_sent_check(None, 5.0)


def test_고른_장면만_보낸_초는_고른_컷_합(monkeypatch, tmp_path):
    """골라 지우기 실제 ffmpeg — 업체로 넘긴 partial_in 길이 ≤ 고른 컷 합 + 반올림."""
    raw = _mk(tmp_path / "mix_raw.mp4", 6)
    cuts = [{"beat_idx": 0, "video_id": "s0", "src": 0.0, "fin": 0.0, "dur": 2.0},
            {"beat_idx": 1, "video_id": "s1", "src": 0.0, "fin": 2.0, "dur": 2.0},
            {"beat_idx": 2, "video_id": "s2", "src": 0.0, "fin": 4.0, "dur": 2.0}]
    sent = []
    _fake_vendor(monkeypatch, sent)
    out = tmp_path / "final_clean_abc.mp4"
    mp._clean_partial(raw, cuts, ["1|s1|0.00"], ["k"], str(out), None, tmp_path)
    assert len(sent) == 1 and sent[0] <= 2.0 + TOL
    assert mp.vmake_sent_check(sent[0], mp.vmake_allow_sec(mp.vmake_send_cuts(cuts, ["1|s1|0.00"]))) == []
