from fastapi.testclient import TestClient
from shopping_shorts.app import app

client = TestClient(app)


def test_corpus_returns_lines():
    r = client.get("/api/voice-tune/corpus")
    assert r.status_code == 200
    lines = r.json()["lines"]
    assert any(l["role"] == "hook" for l in lines)


def test_preview_transforms_text_no_synth():
    r = client.post("/api/voice-tune/preview", json={
        "text": "이건 정말 좋습니다. 50% 할인",
        "profile": {"spoken_style": {"on": True, "intensity": 1.0},
                    "normalize": {"on": True}},
        "beat_role": "hook",
    })
    assert r.status_code == 200
    out = r.json()["text"]
    assert "좋아요" in out and "오십 퍼센트" in out
