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


@pytest.fixture(autouse=True)
def _vertex_cutoff_off(monkeypatch):
    """사장님 프로젝트 공유 차단 시각(vertex_route.OWNER_CUTOFF_DEFAULT, 관제 159)을 테스트에선 끈다.

    기본값이 실제 날짜(2026-10-08 13:00 KST)라, 안 끄면 그 시각이 지나는 순간 Vertex 스위치 테스트가
    전부 다른 답을 낸다(시한폭탄 — 그날 오후 모든 finish 게이트가 막힌다). 차단 시각 자체의 시험은
    test_vertex_cutoff.py 가 시각을 직접 주입해 한다."""
    try:
        from shopping_shorts import vertex_route
    except Exception:      # noqa: BLE001 — 이 모듈을 못 불러도 다른 테스트는 돌아야 한다
        return
    monkeypatch.setattr(vertex_route, "OWNER_CUTOFF_DEFAULT", "off")


def pytest_collection_modifyitems(config, items):
    """병합 관문(GATE_XDIST_N)에선 이 PC 실제 영상(C:/숏템_칼카피)을 통째로 읽는 시험을 뺀다(2026-10-26).

    실측: 원본 크기 띠를 capture_output 으로 다 읽는 시험이 병렬 8개로 돌아 남은 메모리 19GB→1GB,
    ffmpeg 가 멈춰 칼카피 병합 관문이 1시간 반 정지. 집 PC 전용 시험이라 서버·다른 PC 관문에선 원래 skip 이다.
    직접 돌릴 땐(관문 밖) 그대로 돈다. 관문에서도 돌리려면 GATE_REAL_MEDIA=1."""
    import inspect
    import os
    if not os.environ.get("GATE_XDIST_N") or os.environ.get("GATE_REAL_MEDIA") == "1":
        return
    skip = pytest.mark.skip(reason="병합 관문: 집 PC 실제 영상 시험 제외(GATE_REAL_MEDIA=1 이면 돈다)")
    for it in items:
        reasons = " ".join(str(m.kwargs.get("reason", "")) for m in it.iter_markers("skipif"))
        try:
            src = inspect.getsource(it.function)
        except (OSError, TypeError, AttributeError):
            src = ""
        if "숏템_칼카피" in src or "집 PC" in reasons or "원본 없음" in reasons:
            it.add_marker(skip)
