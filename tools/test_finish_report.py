# -*- coding: utf-8 -*-
"""finish 계측·영상 관문 재사용(2026-10-03 카드 089)."""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finish_report  # noqa: E402
import track  # noqa: E402
import video_gate as vg  # noqa: E402


def test_로그_줄마다_시각이_붙는다():
    buf = io.StringIO()
    out = track._StampOut(buf)
    out.write("가\n나")
    out.write("다\n\n")
    lines = buf.getvalue().splitlines()
    assert lines[0][8:] == " 가" and lines[1][8:] == " 나다" and lines[0][2] == ":"


def test_집계는_단계별_분을_낸다(tmp_path):
    p = tmp_path / "x_20261003_120000.log"
    p.write_text("\n".join([
        "12:00:01 finish 시작",
        "12:01:00 게이트 실행 중 (병합된 상태 · 줄 밖)...",
        "12:07:00 ✅ 게이트 통과",
        "12:07:01 영상 관문: 실행 — 제작 라인 파일 변경",
        "12:17:01 검사 끝 — 줄에 선다(줄 안에선 커밋·push 만)",
        "12:19:01 ✅ main에 병합 완료 — push됨.",
    ]) + "\n", encoding="utf-8")
    (tmp_path / "x_20261003_120000.rc").write_text("0", encoding="utf-8")
    r = finish_report.parse(p)
    assert r["결과"] == "병합" and r["시각있음"]
    assert round(r["시험"] / 60) == 6 and round(r["영상관문"] / 60) == 10 and round(r["줄대기"] / 60) == 2


def _stub_gate(monkeypatch, tmp_path, ok=True):
    calls = []
    monkeypatch.setattr(vg, "gate_decision", lambda stage, cfg=None: (None, ["shopping_shorts/video_assemble.py"], True, ["x"], []))
    monkeypatch.setattr(vg, "_bundle", lambda stage, side="merged": ("b-" + side).encode())

    def mj(sh, stage, br, cfg, g, **kw):
        calls.append(1)
        return ok, ([] if ok else ["잔상 5"]), [], "요약"
    monkeypatch.setattr(vg, "_measure_and_judge", mj)
    stage = tmp_path / "_merge-x"
    stage.mkdir()
    cfg = {"gate": {"jobs": 6}}
    run = lambda env=None: vg.run_video_gate(str(stage), "br", printer=lambda s: None, sh=lambda *a, **k: (0, ""),  # noqa: E731
                                             cfg=cfg, env=env or {})
    return run, calls


def test_같은_묶음이_통과했으면_서버_비교를_다시_안_돈다(tmp_path, monkeypatch):
    run, calls = _stub_gate(monkeypatch, tmp_path)
    assert run().ok and run().ok
    assert len(calls) == 1, "같은 묶음인데 서버 비교를 또 돌렸다"
    assert run({"VIDEO_GATE_FRESH": "1"}).ok and len(calls) == 2


def test_묶음이_바뀌면_다시_잰다(tmp_path, monkeypatch):
    run, calls = _stub_gate(monkeypatch, tmp_path)
    run()
    monkeypatch.setattr(vg, "_bundle", lambda stage, side="merged": ("바뀜-" + side).encode())
    run()
    assert len(calls) == 2


def test_실패는_기억하지_않는다(tmp_path, monkeypatch):
    run, calls = _stub_gate(monkeypatch, tmp_path, ok=False)
    assert not run().ok and not run().ok
    assert len(calls) == 2


def test_오래된_통과는_다시_잰다(tmp_path, monkeypatch):
    run, calls = _stub_gate(monkeypatch, tmp_path)
    run()
    f = next((tmp_path / "_gate_cache").glob("video_pass_*.json"))
    f.write_text(json.dumps({"t": time.time() - vg.VIDEO_PASS_TTL - 5, "summary_line": ""}), encoding="utf-8")
    run()
    assert len(calls) == 2
