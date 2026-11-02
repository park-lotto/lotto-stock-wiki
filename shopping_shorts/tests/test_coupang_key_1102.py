# -*- coding: utf-8 -*-
"""11-02 회원 제보: shortem_setup 은 쿠팡 키 '준비됨'인데 제작 시작에 '키가 확인되지 않아요'.
shortem_setup 은 파일 있음만, 제작 시작은 실제 호출을 봤고 호출 실패를 사유 없이 전부 'bad' 로 뭉갰다 —
쿠팡이 키를 거부한 때만 'bad', 잠깐 막힘·끊김은 'unknown'(회원 안내 없음, 제작 때 키를 그대로 먼저 쓴다), 사유 코드는 남긴다.
쿠팡을 실제로 부르지 않는다(_call 가짜 + urlopen 차단)."""
import json
import urllib.request

import pytest

from shopping_shorts import coupang_partners as cp
from tools.calcopy import coupang_customer as C
from tools.calcopy.hybrid import runner_ops as R

AK, SK = "ACCESS-VALUE-NEVER-PRINT", "SECRET-VALUE-NEVER-PRINT"
OK = (200, {"rCode": "0", "data": []})
BAD_MSG = "키가 확인되지 않아요"


@pytest.fixture
def api(monkeypatch):
    """회원 PC 흉내 — 응답을 시험이 정한다. calls = 쿠팡을 부른 횟수."""
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    monkeypatch.setenv("COUPANG_ACCESS_KEY", AK)
    monkeypatch.setenv("COUPANG_SECRET_KEY", SK)
    monkeypatch.delenv("CALCOPY_DEV_COUPANG_SERVER", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("실제 쿠팡 호출 금지"))
    monkeypatch.setattr("time.sleep", lambda s: None)
    R._cp_last.clear() if hasattr(R, "_cp_last") else None
    box = {"replies": [], "calls": 0}

    def fake(method, path, ak, sk, body=None, timeout=15):
        box["calls"] += 1
        return box["replies"][min(box["calls"] - 1, len(box["replies"]) - 1)]
    monkeypatch.setattr(cp, "_call", fake)
    return box


TRANSIENT = [
    ((429, {"rCode": "429", "rMessage": "too many"}), "rate_limited"),
    ((500, {"error": "HTTP 500"}), "server_error"),
    ((503, {}), "server_error"),
    ((0, {"error": "<urlopen error timed out>"}), "net_timeout"),
    ((0, {"error": "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]>"}), "net_ssl"),
    ((0, {"error": "<urlopen error [Errno 11001] getaddrinfo failed>"}), "net_failed"),
    ((403, {"error": "HTTP 403"}), "blocked"),                     # 본문이 JSON 이 아닌 403 = 회선·방화벽 막힘(10-21 '사용권한이 제한된 페이지'), 키 판정 아님
    ((200, {"rCode": "400", "rMessage": "invalid url"}), "probe_refused"),   # 확인용 상품 거절 — 키가 죽었다는 증거가 아니다
    ((404, {}), "probe_refused"),                                  # _outcome 이 rCode 없으면 'ok' 라 하는 꼴 — ok 로 넘기지 않는다
]


@pytest.mark.parametrize("reply,reason", TRANSIENT)
def test_transient_failure_is_not_bad_key(api, reply, reason):
    api["replies"] = [reply]
    assert R.coupang_key_state() == "unknown"
    assert api["calls"] == 2                                       # 잠깐의 끊김은 한 번 더
    assert R._cp_last["reason"] == reason
    assert R._cp_last["http"] == (reply[0] or None)
    assert R.advice_list("연예인형") == []                          # 키는 멀쩡할 수 있다 — 회원을 놀라게 하지 않는다(제작 때 키를 먼저 쓴다)


@pytest.mark.parametrize("reply", [(401, {"code": "ERROR", "message": "x"}), (403, {"code": "ERROR", "message": "x"})])
def test_rejected_key_is_bad_and_told_once(api, reply):
    api["replies"] = [reply]
    adv = R.advice_list("연예인형")
    assert BAD_MSG in adv[0]
    assert api["calls"] == 1                                       # 거부는 다시 불러도 같다 — 기다리지 않는다
    assert R._cp_last == {"state": "bad", "reason": "key_rejected", "http": reply[0]}


def test_retry_recovers(api):
    api["replies"] = [(429, {}), OK]
    assert R.coupang_key_state() == "ok"
    assert api["calls"] == 2


def test_200_without_rcode_is_not_ok(api):
    api["replies"] = [(200, {})]
    assert R.coupang_key_state() == "unknown"


def test_non_dict_reply_does_not_crash(api):
    api["replies"] = [(200, ["x"])]
    assert R.coupang_key_state() == "unknown"


def test_no_key_is_none(api, monkeypatch):
    monkeypatch.delenv("COUPANG_SECRET_KEY")
    api["replies"] = [OK]
    assert R.coupang_key_state() == "none"
    assert api["calls"] == 0
    assert "넣어 두시면" in R.advice_list("연예인형")[0]


def test_check_error_does_not_stop_making(api, monkeypatch):
    """확인 도구가 깨져도 제작 시작(c_env)을 죽이지 않는다 — 사유 코드만 남긴다."""
    def boom(*a, **k):
        raise RuntimeError(f"boom {SK}")
    monkeypatch.setattr(cp, "_call", boom)
    assert R.coupang_key_state() == "unknown"
    assert R._cp_last["reason"] == "check_error"


def test_reason_reaches_env_measure_without_key_value(api, monkeypatch, tmp_path, capfd):
    """사유 코드가 서버로 가는 measure(st['env']['keys'])에 실린다 — 키 값은 측정·로그 어디에도 없다."""
    from tools.calcopy.hybrid import styles as STY
    monkeypatch.setattr(STY, "load", lambda v: {})
    monkeypatch.setattr(R, "need_list", lambda *a, **k: [])
    monkeypatch.setattr(R, "have_speechmatics", lambda: False)
    monkeypatch.setattr(R, "done_refs", lambda: [])
    api["replies"] = [(429, {"rMessage": f"echo {AK} {SK}"})]
    out = R.c_env(tmp_path, {"version": "v", "fmt": "연예인형"})
    assert out["keys"]["coupang"] is True
    assert out["keys"]["coupang_check"] == {"state": "unknown", "reason": "rate_limited", "http": 429}
    assert out["advice"] == []
    cap = capfd.readouterr()
    text = json.dumps(out, ensure_ascii=False) + cap.err + cap.out
    assert "rate_limited" in cap.err                               # 회원 PC runner.log 에도 남는다
    assert AK not in text and SK not in text


def test_search_all_failed_leaves_reason_and_goes_chrome(api, monkeypatch, capfd):
    monkeypatch.setattr(cp, "search_products", lambda q, limit=10, access_key="", secret_key="": {"ok": False, "items": [], "notice": "x"})
    api["replies"] = [(0, {"error": f"timed out {SK}"})]
    out = C.search(["치약", "칫솔"])
    assert api["calls"] == 1                                       # 사유 확인은 한 번만(크롬 길로 빨리 간다)
    assert all(v["need"] == "chrome" and v["reason"] == "net_timeout" for v in out.values())
    cap = capfd.readouterr()
    assert "net_timeout" in cap.err
    assert AK not in cap.err + cap.out and SK not in cap.err + cap.out


def test_search_failed_but_key_alive_says_so(api, monkeypatch):
    """검색만 막힘(검색 API 쪽 사정) — 딥링크는 통과. 키 무효로 적지 않는다."""
    monkeypatch.setattr(cp, "search_products", lambda q, limit=10, access_key="", secret_key="": {"ok": False, "items": []})
    api["replies"] = [OK]
    out = C.search(["치약"])
    assert out["치약"]["need"] == "chrome" and out["치약"]["reason"] == "search_only"


def test_search_ok_makes_no_extra_call(api, monkeypatch):
    monkeypatch.setattr(cp, "search_products", lambda q, limit=10, access_key="", secret_key="": {"ok": True, "items": [{"product_id": "1"}]})
    api["replies"] = [OK]
    assert C.search(["치약"])["치약"]["ok"] is True
    assert api["calls"] == 0
