# tests/studio/test_studio_pipeline.py
from pathlib import Path
import json
import scripts.studio_pipeline as sp

def test_pipeline_emits_all_steps_and_done(tmp_path, monkeypatch):
    studio = tmp_path / "out" / "studio"
    monkeypatch.setattr(sp, "STUDIO_DIR", studio)
    monkeypatch.setattr(sp, "IMG_DIR", studio / "img")
    # 외부/무거운 단계 모킹
    monkeypatch.setattr(sp.studio_data, "get_briefing_data",
        lambda d: {"date": d, "headline": "테스트", "lead_sectors": ["반도체"], "lines": ["라인1"]})
    monkeypatch.setattr(sp.gemini_image, "generate_hero",
        lambda prompt, out, **k: (Path(out).parent.mkdir(parents=True, exist_ok=True),
                                   Path(out).write_bytes(b"\x89PNG"),
                                   {"ok": True, "path": str(out), "fallback": True})[-1])
    monkeypatch.setattr(sp.viz_card, "save_png",
        lambda hp, pp: (Path(pp).write_bytes(b"\x89PNG"), True)[-1])
    monkeypatch.setattr(sp.viz_card, "send_telegram_photo", lambda pp, caption="": True)

    events = list(sp.generate_briefing("2026-06-28"))
    step_ids = [e["id"] for e in events if e["type"] == "step" and e["status"] == "done"]
    assert step_ids == [1, 2, 3, 4, 5]
    done = events[-1]
    assert done["type"] == "done" and done["sent_tg"] is True
    assert Path(done["png"]).exists()
    # 이력 기록 확인
    idx = json.loads((studio / "index.json").read_text(encoding="utf-8"))
    assert idx[0]["date"] == "2026-06-28"

def test_pipeline_partial_success_when_telegram_fails(tmp_path, monkeypatch):
    studio = tmp_path / "out" / "studio"
    monkeypatch.setattr(sp, "STUDIO_DIR", studio)
    monkeypatch.setattr(sp, "IMG_DIR", studio / "img")
    monkeypatch.setattr(sp.studio_data, "get_briefing_data",
        lambda d: {"date": d, "headline": "t", "lead_sectors": [], "lines": ["x"]})
    monkeypatch.setattr(sp.gemini_image, "generate_hero",
        lambda prompt, out, **k: (Path(out).parent.mkdir(parents=True, exist_ok=True),
                                   Path(out).write_bytes(b"\x89PNG"),
                                   {"ok": True, "fallback": True})[-1])
    monkeypatch.setattr(sp.viz_card, "save_png", lambda hp, pp: (Path(pp).write_bytes(b"\x89PNG"), True)[-1])
    monkeypatch.setattr(sp.viz_card, "send_telegram_photo", lambda pp, caption="": False)
    events = list(sp.generate_briefing("2026-06-28"))
    done = events[-1]
    assert done["type"] == "done" and done["sent_tg"] is False  # 부분 성공
    assert Path(done["png"]).exists()
