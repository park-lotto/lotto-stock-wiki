"""VMake 키 등록 검증 (2026-08-31 실사고).

키의 짝이 안 맞는데 '● 정상'으로 떠서, 고객이 제작을 돌리다 1시간 45분을 버렸다
(에러 `[10021] sign not equals client`). 형식만 보던 판정을 서명 실검증으로 바꿨다.
/skill/config.json은 SDK가 본작업 전에 부르는 설정 조회라 **크레딧을 안 쓴다**.
"""
import pytest
from shopping_shorts import app as A
from shopping_shorts import keyroute


# ── 형식 힌트: 외부를 때리기 전에 눈으로 걸러지는 실수를 잡는다 ────────────────
@pytest.mark.parametrize("key, 걸려야하나", [
    ("a" * 32 + ":" + "b" * 32, False),      # 정상
    ("a" * 32, True),                        # 콜론 없음 = 하나만 넣음
    ("a" * 32 + ":", True),                  # 뒤가 비었다
    (":" + "b" * 32, True),                  # 앞이 비었다
    ("a" * 32 + ":" + "b" * 16 + " " + "b" * 15, True),   # 중간 공백(라이브 실측 2건)
    ("a" * 32 + ":b:c", True),               # 조각이 셋
])
def test_형식힌트가_잘못된_모양을_잡는다(key, 걸려야하나):
    hint = A._key_format_hint(keyroute.SVC_VMAKE, key)
    assert bool(hint) is 걸려야하나, f"{key[:20]}… → {hint!r}"


def test_형식이_틀리면_실호출까지_안_간다(monkeypatch):
    """형식 힌트가 걸리면 _key_status는 bad를 주고 외부를 안 때린다(돈·시간 절약)."""
    called = []
    monkeypatch.setattr(A, "_probe_user_key", lambda *a: called.append(a) or True)
    assert A._key_status(keyroute.SVC_VMAKE, "콜론없는키") == "bad"
    assert not called


def test_서명이_틀리면_bad(monkeypatch):
    """SkillClient 생성(=fetch_config)이 실패하면 bad. 종전엔 ok였다."""
    class _Boom:
        def __init__(self, ak=None, sk=None):
            raise RuntimeError("[10021] sign not equals client")
    import shopping_shorts.vmake_sdk as sdk
    monkeypatch.setattr(sdk, "SkillClient", _Boom)
    assert A._probe_user_key(keyroute.SVC_VMAKE, "a" * 32 + ":" + "b" * 32) is False


def test_서명이_맞으면_ok(monkeypatch):
    class _Ok:
        def __init__(self, ak=None, sk=None):
            pass
    import shopping_shorts.vmake_sdk as sdk
    monkeypatch.setattr(sdk, "SkillClient", _Ok)
    assert A._probe_user_key(keyroute.SVC_VMAKE, "a" * 32 + ":" + "b" * 32) is True


def test_실패사유에_키값이_안_남는다(monkeypatch):
    """사유 문구·로그에 키가 섞이면 안 된다."""
    ak, sk = "A" * 32, "S" * 32
    class _Leak:
        def __init__(self, ak=None, sk=None):
            raise RuntimeError(f"bad key ak={ak} sk={sk}")
    import shopping_shorts.vmake_sdk as sdk
    monkeypatch.setattr(sdk, "SkillClient", _Leak)
    assert A._probe_user_key(keyroute.SVC_VMAKE, f"{ak}:{sk}") is False
    reason = A._take_key_failure()
    assert ak not in reason and sk not in reason


@pytest.mark.parametrize("detail, 들어가야할말", [
    ("[10021] sign not equals client", "짝이 맞지 않"),
    ("[10021] invalid or inactive AK/SK", "다시 등록"),
    ("[60002] You don't have enough credits", "충전"),
])
def test_vmake_실패사유가_사람말로_나온다(monkeypatch, detail, 들어가야할말):
    """★네트워크 탓으로 둘러대면 안 된다 — 고객이 멀쩡한 인터넷을 의심하며 재시도만 한다."""
    class _Boom:
        def __init__(self, ak=None, sk=None):
            raise RuntimeError("Failed to fetch skill config ... Detail: " + detail)
    import shopping_shorts.vmake_sdk as sdk
    monkeypatch.setattr(sdk, "SkillClient", _Boom)
    assert A._probe_user_key(keyroute.SVC_VMAKE, "a" * 32 + ":" + "b" * 32) is False
    reason = A._take_key_failure()
    assert 들어가야할말 in reason, reason
    assert "인터넷" not in reason
