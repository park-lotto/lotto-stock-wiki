from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def test_voice_presets_endpoint_lists_kr_and_hides_source_ref():
    # TestClient 컨텍스트 진입 시 startup seed가 큐레이션 프리셋을 DB에 넣는다
    with TestClient(appmod.app) as client:
        r = client.get("/api/voice-presets?lang=KR")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert len(d["groups"]) >= 6           # 성우 6명 이상(그룹) — 전원 stable/natural/expressive 3톤 + 베스트 5명은 whisper 추가(2026-07-16 청취 판정)
        g = d["groups"][0]                     # ORDER BY best DESC, created_at → 베스트 성우가 맨 앞
        assert g["default_variant"] == "stable"
        # 3톤은 전 성우 공통 하한선(부분집합 검사).
        assert {"stable", "natural", "expressive"} <= set(g["variants"].keys())
        # whisper 유무는 약화가 아니라 진짜 계약: best 플래그와 정확히 일치해야 한다
        # (베스트 5명만 whisper를 갖고, best 플래그로 순서·⭐배지를 동시에 결정하므로).
        assert ("whisper" in g["variants"]) is g["best"]
        v = g["variants"]["stable"]
        assert "source_ref" not in v            # 내부 전용 필드는 노출 금지
        assert "voice_settings" in v
        assert v["sample_url"] is None or v["sample_url"].startswith("/api/voice-presets/")
