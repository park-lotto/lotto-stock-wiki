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
    monkeypatch.setattr(sp.card_render, "render_briefing_card",
        lambda data, hero: "<html><div class='card'>x</div></html>")
    monkeypatch.setattr(sp.card_render, "save_card_html",
        lambda html, p: (__import__("pathlib").Path(p).write_text(html, encoding="utf-8"),
                         __import__("pathlib").Path(p))[-1])
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
    monkeypatch.setattr(sp.card_render, "render_briefing_card",
        lambda data, hero: "<html><div class='card'>x</div></html>")
    monkeypatch.setattr(sp.card_render, "save_card_html",
        lambda html, p: (__import__("pathlib").Path(p).write_text(html, encoding="utf-8"),
                         __import__("pathlib").Path(p))[-1])
    monkeypatch.setattr(sp.viz_card, "save_png", lambda hp, pp: (Path(pp).write_bytes(b"\x89PNG"), True)[-1])
    monkeypatch.setattr(sp.viz_card, "send_telegram_photo", lambda pp, caption="": False)
    events = list(sp.generate_briefing("2026-06-28"))
    done = events[-1]
    assert done["type"] == "done" and done["sent_tg"] is False  # 부분 성공
    assert Path(done["png"]).exists()

def test_pipeline_png_failure_emits_error_no_done(tmp_path, monkeypatch):
    studio = tmp_path / "out" / "studio"
    monkeypatch.setattr(sp, "STUDIO_DIR", studio)
    monkeypatch.setattr(sp, "IMG_DIR", studio / "img")
    monkeypatch.setattr(sp.studio_data, "get_briefing_data",
        lambda d: {"date": d, "headline": "t", "lead_sectors": [], "lines": ["x"]})
    monkeypatch.setattr(sp.gemini_image, "generate_hero",
        lambda prompt, out, **k: (__import__("pathlib").Path(out).parent.mkdir(parents=True, exist_ok=True),
                                  __import__("pathlib").Path(out).write_bytes(b"\x89PNG"),
                                  {"ok": True, "fallback": True})[-1])
    monkeypatch.setattr(sp.card_render, "render_briefing_card",
        lambda data, hero: "<html><div class='card'>x</div></html>")
    monkeypatch.setattr(sp.card_render, "save_card_html",
        lambda html, p: (__import__("pathlib").Path(p).write_text(html, encoding="utf-8"),
                         __import__("pathlib").Path(p))[-1])
    monkeypatch.setattr(sp.viz_card, "save_png", lambda hp, pp: False)  # PNG 추출 실패
    events = list(sp.generate_briefing("2026-06-28"))
    types = [e["type"] for e in events]
    assert "done" not in types
    step4_err = next((e for e in events if e.get("id") == 4 and e.get("status") == "error"), None)
    assert step4_err is not None
    assert events[-1]["type"] == "error"


def test_generate_picks_flow(tmp_path, monkeypatch):
    studio = tmp_path / "out" / "studio"
    monkeypatch.setattr(sp, "STUDIO_DIR", studio)
    monkeypatch.setattr(sp.studio_picks, "get_picks",
        lambda **k: {"date": "2026-06-27", "source": "signal_snapshot.json",
                     "market": {"verdict": "CAUTION", "vix": 18.4, "reasons": []},
                     "lead_sectors": [{"name": "반도체", "sortino": 98.2}],
                     "picks": [{"name": "SK하이닉스", "sector": "반도체", "score": 4,
                                "rs": 58.3, "vacancy": "A", "signals": ["기관 수급 빈집"], "atom": None}]})
    monkeypatch.setattr(sp.card_picks, "render_picks_card", lambda d: "<html><div class='card'>x</div></html>")
    monkeypatch.setattr(sp.card_picks, "save_card_html",
        lambda html, p: (__import__("pathlib").Path(p).write_text(html, encoding="utf-8"),
                         __import__("pathlib").Path(p))[-1])
    monkeypatch.setattr(sp.viz_card, "save_png", lambda hp, pp: (__import__("pathlib").Path(pp).write_bytes(b"\x89PNG"), True)[-1])
    monkeypatch.setattr(sp.viz_card, "send_telegram_photo", lambda pp, caption="": True)

    events = list(sp.generate_picks("2026-06-28"))
    done = [e["id"] for e in events if e["type"] == "step" and e["status"] == "done"]
    assert done == [1, 2, 3, 4, 5]
    assert events[-1]["type"] == "done" and events[-1]["sent_tg"] is True
    import json as _j
    idx = _j.loads((studio / "index.json").read_text(encoding="utf-8"))
    assert idx[0]["type"] == "picks"


def test_generate_picks_no_picks_errors(tmp_path, monkeypatch):
    studio = tmp_path / "out" / "studio"
    monkeypatch.setattr(sp, "STUDIO_DIR", studio)
    monkeypatch.setattr(sp.studio_picks, "get_picks", lambda **k: {"picks": []})
    events = list(sp.generate_picks("2026-06-28"))
    assert events[-1]["type"] == "error"
    assert "done" not in [e["type"] for e in events]
