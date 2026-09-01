# -*- coding: utf-8 -*-
"""제미나이 키 배선 검증 (2026-08-22 / 2026-08-24 공용 풀로 전환).

★왜 따로 쓰나: "should_charge가 False다"는 **과금 판정**만 본 것이다.
   실제로 그 키가 호출에 쓰이는지는 별개다 — vmake가 테스트 146개를 통과하고도
   라이브 사용 0건이었던 이유가 그거였다(판정만 맞고 실전 확인이 없었다).
   여기서는 **키를 꺼내는 출구가 진짜 그 키를 내놓는지**를 본다.

★2026-08-24 정책 변경(사장님): 제미니는 회원에게 1개만 받아 **우리 풀에 합류**시키고
   회원은 풀 전체를 무료로 쓴다. 그래서 "개인 키만 쓰고 폴백 없음"은 **버렸다** —
   1개로만 돌리면 한도에 곧바로 걸려 1개만 받은 취지가 뒤집히기 때문이다.
   대신 지켜야 할 것은 "등록한 키가 실제로 풀에 들어가 쓰이는가"다.
"""
import pytest
from cryptography.fernet import Fernet

from shopping_shorts import keyctx, keyroute
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    db = str(tmp_path / "t.db")
    monkeypatch.setattr("shopping_shorts.config.DB_PATH", db, raising=False)
    return Store(db)


@pytest.fixture
def vault(monkeypatch):
    """회사 키 풀을 가짜로 — 개인 키가 없을 때 여기로 떨어져야 한다."""
    from pipeline.atoms import key_vault
    monkeypatch.setattr(key_vault, "get_live_keys_cascade",
                        lambda group: ["OWNER-1", "OWNER-2"])
    return key_vault


def test_no_owner_uses_company_pool(store, vault):
    """주인이 안 정해졌으면 회사 키. 기존 동작(크론·사장님)이 안 바뀐다."""
    assert keyroute.gemini_keys() == ["OWNER-1", "OWNER-2"]


def test_registered_key_actually_joins_the_pool(store, vault, monkeypatch):
    """★배선의 핵심 — 등록한 키가 **합류 함수를 거쳐** 실제로 꺼내진다.

    회원 키가 풀에 안 들어가면 과금 면제만 켜진 꼴이라 08-17 사고가 재현된다.
    합류는 app이 기동·등록/삭제 때 refresh_member_gemini_keys로 한다 — 여기선
    그 호출을 재현해 '등록 → 합류 → 꺼내짐'의 사슬 전체를 본다."""
    from pipeline.atoms import key_vault
    from shopping_shorts import config
    monkeypatch.setattr(key_vault, "_member_keys", [], raising=False)
    store.add_customer_key(7, keyroute.SVC_GEMINI, "MINE-1")
    config.refresh_member_gemini_keys(store.get_pooled_keys(keyroute.SVC_GEMINI))
    # vault 픽스처가 get_live_keys_cascade를 가로채므로 합류분은 set_member_keys로 확인
    assert "MINE-1" in key_vault._member_keys
    assert "MINE-1" in config.SHORTS_GEMINI_KEYS


def test_pool_is_shared_not_personal_only(store, vault):
    """★공용 풀 — 회원은 자기 키 1개만 내고 **풀 전체**를 쓴다.
    (옛 규칙 '개인 키만·폴백 없음'은 2026-08-24에 사장님 지시로 폐기)"""
    store.add_customer_key(7, keyroute.SVC_GEMINI, "MINE-1")
    with keyctx.owner(7):
        got = keyroute.gemini_keys()
    assert "OWNER-1" in got and "OWNER-2" in got


def test_pool_has_no_duplicates(store, vault):
    """같은 키가 두 번 들어가면 로테이션이 그 키만 두 배로 때린다."""
    store.add_customer_key(7, keyroute.SVC_GEMINI, "OWNER-1")   # 사장님 키와 동일
    with keyctx.owner(7):
        got = keyroute.gemini_keys()
    assert got.count("OWNER-1") == 1


def test_owner_cid_zero_uses_pool(store, vault):
    """cid 0 = 사장님. 개인 키 조회를 아예 안 하고 풀을 쓴다(크론 동작 불변)."""
    store.add_customer_key(0, keyroute.SVC_GEMINI, "SHOULD-NOT-BE-USED")
    with keyctx.owner(0):
        assert keyroute.gemini_keys() == ["OWNER-1", "OWNER-2"]


def test_context_is_restored_after_block(store, vault):
    """블록을 벗어나면 원래대로 — 다음 작업에 주인이 새면 안 된다."""
    store.add_customer_key(7, keyroute.SVC_GEMINI, "MINE-1")
    with keyctx.owner(7):
        pass
    assert keyctx.owner_cid() == 0
    assert keyroute.gemini_keys() == ["OWNER-1", "OWNER-2"]


def test_string_cid_does_not_crash(store, vault):
    """cid는 int 0과 문자열 "0"이 섞여 온다(app.py:6813 실사고).
    공용 풀에선 cid가 키 선택을 안 가르지만, 문자열이 와도 터지면 안 된다."""
    store.add_customer_key(7, keyroute.SVC_GEMINI, "MINE-1")
    with keyctx.owner("7"):
        assert keyroute.gemini_keys() == ["OWNER-1", "OWNER-2"]


def test_every_gemini_key_fetch_goes_through_the_single_exit():
    """★키를 꺼내는 곳이 늘어나면 이 테스트가 깨진다.

    누가 key_vault를 직접 부르면 그 경로는 개인 키를 무시하고 회사 키로 돈다 —
    화면은 "등록했으니 0P"라고 하는데 실제로는 회사 돈이 나가는 구멍이 된다.
    새 호출부가 필요하면 keyroute.gemini_keys()를 쓰고 여기 목록을 늘려라."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for f in root.glob("*.py"):
        # api_health.py는 관측판 데이터층(2026-09-01) — 풀 구성을 **읽기만** 하고
        # 그 키로 Gemini를 호출하지 않는다(스냅샷 표시용). 과금 구멍이 아니다.
        if f.name in ("keyroute.py", "keyctx.py", "api_health.py"):
            continue
        txt = f.read_text(encoding="utf-8")
        if re.search(r"get_live_keys_cascade\(|get_live_keys\(|key_vault\.get_keys\(", txt):
            offenders.append(f.name)
    assert offenders == [], (
        "제미나이 키를 keyroute.gemini_keys() 밖에서 꺼내는 파일: %s" % offenders)


def test_workers_open_the_owner_context():
    """★워커는 미들웨어를 안 거친다 — 데코레이터가 빠지면 개인 키가 안 쓰인다.
    (contextvar는 스레드마다 따로라 HTTP 컨텍스트를 물려받지 못한다)"""
    import inspect

    from shopping_shorts import mix_pipeline as mp
    for name in ("run_mix_job", "retype_mix_job", "assemble_clean_video",
                 "run_clean_sources", "run_preview", "run_render"):
        fn = getattr(mp, name)
        src = inspect.getsource(fn)
        # functools.wraps로 감싸도 __wrapped__가 남는다 = 데코레이터가 붙었다는 증거
        assert hasattr(fn, "__wrapped__"), f"{name}에 @_owned_job이 없다"
        assert src, name
