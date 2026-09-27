"""테스트 공통 픽스처.

SSRF 가드(_reject_ssrf)는 도메인이 **실제로 어느 IP로 뜨는지** 확인한다(DNS rebinding
1차 방어). 그래서 가드가 걸린 라우트를 테스트하면 유닛테스트가 실제 DNS를 타게 되고,
- 네트워크 없는 CI/오프라인에선 "호스트 해석 실패"로 422가 되어 무관한 테스트가 깨지고,
- 있어도 조회 지연만큼 느려지며 결과가 환경에 따라 흔들린다.
→ 이름해석만 결정적으로 고정한다. 스킴 검사·사설망/링크로컬 IP 판정 등 가드의 실제
  로직은 그대로 돈다(IP 리터럴은 애초에 DNS를 안 탄다).
"""
import socket

import pytest

_PUBLIC_IP = "93.184.216.34"      # 공인 IP — 가드가 "내부망 아님"으로 통과시킨다.
# 이름이 내부망을 가리키는 상황을 재현하고 싶은 테스트를 위해 남겨둔다.
_FORCE_PRIVATE = {"internal.example", "metadata.example"}


@pytest.fixture(autouse=True)
def offline_dns(monkeypatch):
    def _fake_gethostbyname(host):
        if host in _FORCE_PRIVATE:
            return "169.254.169.254"
        return _PUBLIC_IP

    monkeypatch.setattr(socket, "gethostbyname", _fake_gethostbyname)


@pytest.fixture(autouse=True)
def _reset_gemini_key_cursor():
    """키 라운드로빈 커서를 테스트마다 처음으로 되돌린다(2026-08-18).

    _current_key_and_idx가 라운드로빈 페이서에 위임되면서 커서가 전역 상태가 됐다.
    안 되돌리면 앞 테스트가 커서를 밀어놓아 "키1 소진 → 키2" 류 테스트가 순서에
    따라 흔들린다(단독은 통과, 묶으면 실패).
    """
    from shopping_shorts import comment_gen as _cg
    _cg._rr_cursor["i"] = 0
    _cg._key_last_used.clear()
    yield


@pytest.fixture(autouse=True)
def _isolate_key_vault_state(tmp_path, monkeypatch):
    """key_vault 상태파일(영구 사망·사용불가 정지)을 테스트마다 빈 임시 파일로 가른다(2026-09-25).

    usage_meter 깔때기가 모든 제미니 실패를 key_vault.note_failure로 보내고, 쇼츠 풀
    (comment_gen._dead_fingerprints)도 key_vault 표시를 합쳐 본다. 격리하지 않으면 앞 테스트가
    **진짜 상태파일**(pipeline/atoms/.gemini_key_state.json)에 남긴 사망 표시가 뒤 테스트의 풀에서
    키를 빼 순서에 따라 흔들린다(실측: 단독 통과·묶으면 test_round_robin_cycles 등 5건 실패).
    텔레그램 경보도 막는다 — 새 정지가 _tg_alert로 실제 메시지를 보낼 수 있다.
    자기 경로를 따로 쓰는 테스트는 제 fixture에서 다시 monkeypatch하므로 그대로 된다."""
    from pipeline.atoms import key_vault as _kv
    monkeypatch.setattr(_kv, "_STATE_PATH", tmp_path / "_kv_state.json")
    monkeypatch.setattr(_kv, "_LOCK_PATH", tmp_path / "_kv_state.lock")
    monkeypatch.setattr(_kv, "_tg_alert", lambda *_a, **_k: None)
    _kv._SUS_CACHE["t"] = 0.0
    yield
    _kv._SUS_CACHE["t"] = 0.0
