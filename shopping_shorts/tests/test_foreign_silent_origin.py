"""해외원본형 원본에 소리 트랙이 없을 때(인스타·틱톡 무음 — 이성택 #9390 0e037b22c143 · 김하영 #8834 ac1fa00e7216).
판단 = 소리 유무 측정 common.has_audio(회원 판) → 서버 판단 주인 flow._silent_files/_no_speech 를 조사 검사·원음 받아쓰기(f_asr)·대본 검사가 부른다."""
import json
import shutil
import subprocess

import pytest

from tools.calcopy.hybrid import flow as F, script_audit

V = "잇템로그판_v2"
need_ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def _mute_mp4(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x568:d=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)], check=True)
    return p


def _st(**kw):
    return {"version": V, "fmt": "해외원본형", "log": [], "tries": {}, "bench": {"title": "t", "sheet": "b.jpg"}, "product_shots": [], "product": {"name": "n"},
            "origin": {"files": [{"name": "a.mp4", "dur": 20}, {"name": "b.mp4", "dur": 20}]},
            "origins": [{"id": "a", "files": [{"name": "a.mp4", "dur": 20}]}, {"id": "b", "files": [{"name": "b.mp4", "dur": 20}]}], **kw}


SILENT = {"words": [], "from": "소리 없음", "audio": False}
MD = "결론 출처 원음 없음 사실 금지 확인 못"


@need_ff
def test_runner_words_on_silent_origin_is_empty_not_error(tmp_path):
    from tools.calcopy.hybrid import runner_ops as R
    _mute_mp4(tmp_path / "src" / "x1.mp4")
    r = R.c_origin_words(tmp_path, {"vid": "x1", "src": "src/x1.mp4", "platform": "tiktok"})      # 고치기 전: asr_local.pcm ffmpeg 예외
    assert r["words"] == [] and r["audio"] is False


@need_ff
def test_runner_asr_spans_skips_silent_file(tmp_path):
    from tools.calcopy.hybrid import runner_ops as R
    _mute_mp4(tmp_path / "src" / "x1.mp4")
    r = R.c_asr_spans(tmp_path, {"spans": [{"tag": "O1", "src": "x1.mp4", "a": 1.0, "b": 3.0}]})   # 고치기 전: 'Output file does not contain any stream'
    assert r["spans"][0]["skipped"] and "whisper" not in r["spans"][0]


def test_all_silent_means_no_speech_and_asr_skipped():
    st = _st(_fwords={"a.mp4": SILENT, "b.mp4": SILENT}, research={"spans": []})
    assert F._no_speech(st)
    r = F.f_asr(st, {}, {}, {})
    assert r.get("goto") == "script" and not r.get("do")


def test_mixed_spans_on_silent_file_rejected_and_filtered():
    st = _st(_fwords={"a.mp4": {"words": [[1.0, "wow"]]}, "b.mp4": SILENT})
    assert not F._no_speech(st) and F._silent_files(st) == {"b.mp4"}
    sp = [{"tag": "O1", "src": "a.mp4", "a": 1, "b": 3}, {"tag": "O2", "src": "b.mp4", "a": 1, "b": 3}]
    r = F.f_research_check(st, {}, {"research": {"조사_md": MD, "keywords": ["k"], "queries": ["q"], "spans": sp}}, {})
    assert "소리" in str(r.get("reject")) and r["then"] == "f_research_check"
    st["research"] = {"spans": sp}
    r = F.f_asr(st, {}, {}, {})
    assert [s["src"] for s in r["do"][0]["spans"]] == ["a.mp4"]


def _no_orig_script(tmp_path):
    lines = [{"id": f"L{i}", "kind": "tts", "text": t, "tts": t, "caps": [t[:8]]} for i, t in enumerate(
        ["외국인이 있는데요.", "아, 이게 뭐지 싶던데,", "직접 써 봤다고 하고 하고.", "손에 착 붙는다고 하네요."])]
    p = tmp_path / "대본.json"
    p.write_text(json.dumps({"lines": lines}, ensure_ascii=False), encoding="utf-8")
    return p


def _count_orig(a):
    return next(r for r in a["rules"] if r["kind"] == "count" and "orig" in r["why"])


def test_audit_no_orig_accepts_zero_orig_lines(tmp_path):
    p = _no_orig_script(tmp_path)
    assert not _count_orig(script_audit.audit(p, V))["ok"]                 # 소리 있는 원본이면 원음 줄 3~8 그대로
    assert _count_orig(script_audit.audit(p, V, no_orig=True))["ok"]       # 고치기 전: no_orig 칸 없음 → 원음 줄 0 반려
    assert "원음 줄 수 0~0" in script_audit.rules_text(V, no_orig=True)


def test_flow_audit_passes_no_orig_from_owner(monkeypatch):
    seen = {}

    def fake(p, v, no_orig=False):
        seen["no_orig"] = no_orig
        return {"ok": True, "rules": []}
    monkeypatch.setattr(script_audit, "audit", fake)
    st = _st(_fwords={"a.mp4": SILENT, "b.mp4": SILENT})
    try:
        F.audit_script(st, {"lines": []}, {"cuts": {}})
    except Exception:  # noqa: BLE001 — 대본 검사 뒤 다른 규칙이 빈 대본에서 죽어도 넘긴 칸만 본다
        pass
    assert seen.get("no_orig") is True
    assert "원음 줄 수 0~0" in F._points_ctx(V, no_orig=True)
