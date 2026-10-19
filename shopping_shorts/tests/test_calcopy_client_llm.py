"""고객 PC 모드 AI 창구(관제 234) — gemini_free.ask(BACKEND=client) → client_llm 줄 폴더 → 답.

2026-10-19 실측 결함을 시험으로 박는다:
  - 답을 쓰는 중(빈 파일)에 읽어 '틀린 답'으로 셌다 → 다 써진 뒤에만 읽는다
  - 틀린 모양의 답은 error.json 에 이유를 적고 다시 기다린다(RETRIES 넘으면 실패 이유를 돌려준다)
  - 고객 모드에서만 '고객'이 승인할 수 있다
"""
import json
import threading
import time

import pytest

from tools.calcopy.engine import client_llm as C


def _answer_when_ready(q, payload, delay=0.2, empty_first=False):
    def run():
        t0 = time.time()
        while time.time() - t0 < 10:
            for d in q.iterdir():
                if (d / "request.json").exists() and not (d / "answer.json").exists():
                    if empty_first:
                        (d / "answer.json").write_text("", encoding="utf-8")
                        time.sleep(0.3)
                    time.sleep(delay)
                    (d / "answer.json").write_text(payload, encoding="utf-8")
                    return
            time.sleep(0.05)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th


def test_client_answer_roundtrip_and_image_part(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    _answer_when_ready(tmp_path, json.dumps({"items": [{"label": "자막 0", "lines": ["안녕"]}]}))
    d, err = C.ask([b"\xff\xd8fakejpeg", "라벨"], "읽어라", tag="ocr0")
    assert err is None and d["items"][0]["lines"] == ["안녕"] and d["_via"] == "client"
    req = json.loads(next(tmp_path.iterdir()).joinpath("request.json").read_text(encoding="utf-8"))
    assert [p["kind"] for p in req["parts"]] == ["image", "text"] and req["tier"] == "sonnet"


def test_empty_file_while_writing_is_not_counted_as_bad(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    _answer_when_ready(tmp_path, '{"ok": 1}', empty_first=True)
    d, err = C.ask([], "x", tag="t")
    assert err is None and d["ok"] == 1
    assert not list(next(tmp_path.iterdir()).glob("answer.bad*.json"))


def test_bad_answer_retries_then_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    monkeypatch.setattr(C, "RETRIES", 0)

    def bad():
        t0 = time.time()
        while time.time() - t0 < 10:
            for d in tmp_path.iterdir():
                if (d / "request.json").exists() and not (d / "answer.json").exists() and not (d / "done").exists():
                    (d / "answer.json").write_text('"문자열"', encoding="utf-8")
                    return
            time.sleep(0.05)
    threading.Thread(target=bad, daemon=True).start()
    d, err = C.ask([], "x", tag="t")
    assert d is None and err.startswith("client_bad_answer")


def test_tier_of():
    assert C.tier_of("draft") == "opus" and C.tier_of("asr") == "haiku" and C.tier_of("mat0") == "sonnet"


def test_customer_mode_approve_gate(monkeypatch):
    import importlib
    from shopping_shorts import calcopy_make as MK
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    MK2 = importlib.reload(MK)
    assert MK2.CUSTOMER_MODE and MK2.CUSTOMER == "고객"
    monkeypatch.delenv("CALCOPY_CUSTOMER_MODE")
    MK3 = importlib.reload(MK)
    assert not MK3.CUSTOMER_MODE
    with pytest.raises(MK3.MakeError):
        MK3.approve("없는세션", by="고객")
