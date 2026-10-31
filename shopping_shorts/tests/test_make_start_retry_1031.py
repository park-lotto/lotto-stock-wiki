"""글 소재 다시 시작(회원 고장 신고 10-31): 같은 소재 중복이 엔진을 말없이 죽이지 않고 JSON 한 줄로 답한다."""
import json

from shopping_shorts import calcopy_make as MK
from tools.calcopy import make


def _run(monkeypatch, capsys, boom):
    def fake(*a, **k):
        raise boom
    monkeypatch.setattr(MK, "start", fake)
    rc = make.main(["--json", "start", "--preset", "p", "--pack", "1", "--topic", "소재"])
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_duplicate_topic_is_json(monkeypatch, capsys):
    rc, out = _run(monkeypatch, capsys, MK.CT.TopicError("중복 소재: #1 (stopped) 가 이미 진행 중", 409))
    assert rc == 2 and out["code"] == "topic" and "중복 소재" in out["error"]


def test_unknown_crash_is_json(monkeypatch, capsys):
    rc, out = _run(monkeypatch, capsys, KeyError("칸"))
    assert rc == 3 and out["code"] == "engine_crash" and "KeyError" in out["error"]


def test_customer_restart_reopens_same_topic(tmp_path, monkeypatch):
    monkeypatch.setattr(MK, "CUSTOMER_MODE", True)
    a = MK._add_or_reopen("소재", "cat", {}, tmp_path)
    b = MK._add_or_reopen("소재", "cat", {}, tmp_path)
    assert a["id"] == b["id"]


def test_admin_duplicate_still_refused(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(MK, "CUSTOMER_MODE", False)
    MK._add_or_reopen("소재", "cat", {}, tmp_path)
    with pytest.raises(MK.CT.TopicError):
        MK._add_or_reopen("소재", "cat", {}, tmp_path)
