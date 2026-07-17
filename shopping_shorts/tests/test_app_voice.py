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
        # variants 집합은 큐레이션 성우 그룹(one_liner가 채워진 그룹)마다 정확히
        # {stable, natural, expressive} (+best면 whisper)와 일치해야 한다(등호 검사).
        # 정체불명 variant가 섞여도, best 아닌 그룹에 whisper가 새어 들어가도 여기서 잡힌다.
        # one_liner가 None인 그룹은 튜닝 작업대 임시 저장물(origin=tuned, api_voice_tune_profile_save가
        # variant 없이 생성 — 실측: stable 1개뿐)이라 이 3~4톤 계약 밖이라 제외한다.
        for grp in d["groups"]:
            if grp["one_liner"] is None:
                continue
            assert set(grp["variants"]) == {"stable", "natural", "expressive"} | (
                {"whisper"} if grp["best"] else set()
            )
        v = g["variants"]["stable"]
        assert "source_ref" not in v            # 내부 전용 필드는 노출 금지
        assert "voice_settings" in v
        assert v["sample_url"] is None or v["sample_url"].startswith("/api/voice-presets/")
