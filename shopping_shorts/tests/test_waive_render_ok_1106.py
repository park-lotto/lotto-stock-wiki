"""11-06 임수정 6283df26ebdb: 넘기기(waive) 뒤 같은 계획으로 다시 구운 렌더가 ok 인데 렌더 뒤 걸림(샷 넘침)으로 _tries 한도를 곧바로 넘겨 다시 멈췄다.
넘긴 편은 영상이 나왔으면 남은 걸림을 경고로 두고 검사로 간다 — 금지선은 그대로 멈춘다."""
import pytest

from tools.calcopy.hybrid import flow as F


def _st(waived=True):
    return {"version": "v", "waive_gate": waived, "tries": {"render": 9}, "log": [], "text_fix": {}, "script": {"M": {}}}


def test_waived_ok_render_goes_to_check(monkeypatch):
    monkeypatch.setattr(F, "_style", lambda v: {"voice": {"voice_id": "x"}})
    st = _st()
    out = F.ph_render_got(st, {"render": {"ok": True, "jumps": ["계획에서 컷이 원본 샷보다 길다: L5"]}}, {}, None)
    assert out == {"goto": "check"}
    assert any(w["stage"] == "render" for w in st["warn"])


def test_not_waived_still_counts_limit(monkeypatch):
    monkeypatch.setattr(F, "_style", lambda v: {"voice": {"voice_id": "x"}})
    with pytest.raises(F._Stop):
        F.ph_render_got(_st(False), {"render": {"ok": True, "jumps": ["계획에서 컷이 원본 샷보다 길다: L5"]}}, {}, None)


def test_waived_hard_line_still_stops(monkeypatch):
    monkeypatch.setattr(F, "_style", lambda v: {"voice": {"voice_id": "x"}})
    with pytest.raises(F._Stop):
        F.ph_render_got(_st(), {"render": {"ok": True, "error": "원본 규칙 위반: 다른 채널 연예인 장면"}}, {}, None)
