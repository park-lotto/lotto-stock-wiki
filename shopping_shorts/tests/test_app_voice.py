from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def test_voice_presets_endpoint_lists_kr_and_hides_source_ref():
    # TestClient 컨텍스트 진입 시 startup seed가 큐레이션 프리셋을 DB에 넣는다
    with TestClient(appmod.app) as client:
        r = client.get("/api/voice-presets?lang=KR")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert len(d["presets"]) >= 6
        p = d["presets"][0]
        assert "source_ref" not in p          # 내부 전용 필드는 노출 금지
        assert "voice_settings" in p
        assert p["sample_url"] is None or p["sample_url"].startswith("/api/voice-presets/")
