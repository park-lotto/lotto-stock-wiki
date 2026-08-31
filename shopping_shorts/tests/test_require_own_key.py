# -*- coding: utf-8 -*-
"""개인 키 없으면 차단 — VMake·TTS(2026-09-01 사장님 "v메이크랑 tts는 없으면 못하게 막아").

## 왜 생겼나 (실사고)

회원이 개인 키를 안 내면 **사장님 키로 조용히 나가고** 포인트만 깎였다. 회원들은
"다 개인 API키로 쓴다"고 알고 있었고 포인트 얘기는 아무도 못 들었다. 그래서
포인트가 남은 회원은 계속 사장님 일레븐랩스·VMake 계정을 태웠고, 잔액이 떨어진
회원만 402로 막혀 "어떤 사람은 되고 어떤 사람은 안 되는" 상태가 됐다.

실측(2026-09-01 서버): 최근 30일 제작 46명 중 **16명이 TTS 키 없이 86건**을 만들었고,
그 중엔 잔액 105,530P(이정훈)·98,640P(용석)처럼 한참 더 태울 회원도 있었다.

## 이 파일이 지키는 것

1. 키가 없으면 **막힌다**(사장님 키가 안 나간다)
2. 음성은 일레븐랩스·타입캐스트 **둘 중 하나만** 있으면 된다(타입캐스트만 등록한
   회원 4명이 억울하게 막히면 안 된다)
3. **사장님(cid 0)은 절대 안 막힌다** — 공용 보이스 굽기 등 회사 자산 작업이 여기서
   막히면 서비스가 통째로 선다
4. 공용 풀(제미니·유튜브)은 **막지 않는다** — 키 1개 받고 무료가 의도된 거래다
"""
import importlib

import pytest

from shopping_shorts import keycrypt, keyroute
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    return Store(str(tmp_path / "t.db"))


# ── 무엇이 개인 키 필수인가 ────────────────────────────────────────────

def test_require_list_is_exactly_vmake_and_tts():
    """★사장님이 정한 범위 그대로다. 여기에 gemini·youtube가 들어가면 공용 풀
    정책(키 1개 받고 무료)이 깨진다 — 그건 의도된 거래다."""
    assert set(keyroute.REQUIRE_OWN_KEY) == {
        keyroute.SVC_VMAKE, keyroute.SVC_ELEVENLABS, keyroute.SVC_TYPECAST}


@pytest.mark.parametrize("svc", [keyroute.SVC_GEMINI, keyroute.SVC_YOUTUBE])
def test_pooled_services_are_never_blocked(store, svc):
    """공용 풀은 키가 없어도 열려 있어야 한다(회사 풀 무료 제공이 정책)."""
    assert keyroute.block_reason(store, 9, svc) is None


# ── 차단 ───────────────────────────────────────────────────────────────

def test_vmake_blocked_without_own_key(store):
    hit = keyroute.block_reason(store, 7, keyroute.SVC_VMAKE)
    assert hit is not None
    code, msg = hit
    assert code == "need_own_key"
    # ★업체명을 쓰지 않는다(브랜드 정책) — 대신 회원이 화면에서 찾을 수 있는
    #   기능 이름('자막 지우기')과 할 행동('등록')이 문구에 있어야 한다.
    assert "자막 지우기" in msg and "등록" in msg
    assert "VMake" not in msg and "vmake" not in msg


def test_vmake_allowed_after_registering(store):
    store.add_customer_key(7, keyroute.SVC_VMAKE, "내-VM-키")
    assert keyroute.block_reason(store, 7, keyroute.SVC_VMAKE) is None


def test_tts_blocked_when_neither_engine_registered(store):
    hit = keyroute.tts_block_reason(store, 7)
    assert hit is not None and hit[0] == "need_own_key"
    assert "일레븐랩스" in hit[1] and "타입캐스트" in hit[1]   # 둘 중 하나면 된다고 알려준다


def test_tts_allowed_with_elevenlabs_only(store):
    store.add_customer_key(7, keyroute.SVC_ELEVENLABS, "EL")
    assert keyroute.tts_block_reason(store, 7) is None


def test_tts_allowed_with_typecast_only(store):
    """★타입캐스트만 등록한 회원(실측 4명)이 막히면 안 된다 — 음성은 엔진이 둘이다."""
    store.add_customer_key(8, keyroute.SVC_TYPECAST, "TC")
    assert keyroute.tts_block_reason(store, 8) is None


# ── 사장님은 안 막힌다 ─────────────────────────────────────────────────

def test_owner_cid0_never_blocked(store):
    """cid 0 = 사장님/관리자. 공용 보이스 굽기·샘플 제작이 여기서 막히면 서비스가 선다."""
    assert keyroute.block_reason(store, 0, keyroute.SVC_VMAKE) is None
    assert keyroute.block_reason(store, 0, keyroute.SVC_ELEVENLABS) is None
    assert keyroute.tts_block_reason(store, 0) is None


def test_owner_cid0_as_string_also_passes(store):
    """cid는 int 0과 문자열 "0"이 섞여 온다(app.py:6813 실사고 계보)."""
    assert keyroute.tts_block_reason(store, "0") is None


# ── 조회가 실패해도 회원을 막지 않는다 ─────────────────────────────────

def test_store_without_method_does_not_block(store):
    """store 스텁이 넘어오는 경로가 있다 — 판단 불가를 '차단'으로 읽으면
    멀쩡한 회원이 통째로 막힌다. 있음으로 처리하고 로그만 남긴다."""
    class _Stub:
        pass
    assert keyroute.tts_block_reason(_Stub(), 7) is None
    assert keyroute.block_reason(_Stub(), 7, keyroute.SVC_VMAKE) is None


def test_broken_store_does_not_block(store):
    class _Boom:
        def get_customer_keys_plain(self, *a, **kw):
            raise RuntimeError("DB 사망")
    assert keyroute.tts_block_reason(_Boom(), 7) is None


# ── 엔드포인트 응답 모양 ───────────────────────────────────────────────

def test_endpoint_helper_returns_402_with_guidance(store, monkeypatch, tmp_path):
    """★화면이 사유를 갈라 볼 수 있어야 한다 — 전엔 402를 전부
    "포인트가 부족합니다"로 뭉개서 키 미등록도 결제 문제로 읽혔다."""
    import json
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", store.db_path if hasattr(store, "db_path") else str(tmp_path / "t.db"))
    resp = appmod._need_own_key_or_402(7, tts=True)
    assert resp is not None and resp.status_code == 402
    body = json.loads(bytes(resp.body).decode("utf-8"))
    assert body["error_code"] == "need_own_key"
    assert body["need_key_service"] == "tts"
    assert body["settings_url"].startswith("/settings")
    assert not body["ok"]


def test_endpoint_helper_passes_owner(monkeypatch, tmp_path):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    assert appmod._need_own_key_or_402(0, tts=True) is None      # 사장님은 통과
