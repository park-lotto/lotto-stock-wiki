from pathlib import Path
import scripts.gemini_image as gi


def test_build_prompt_includes_sectors():
    p = gi.build_prompt({"lead_sectors": ["반도체", "조선"], "headline": "외인 순매수"})
    assert "반도체" in p
    assert "text" in p.lower() or "글자" in p  # "텍스트 없음" 지시 포함


def test_generate_hero_falls_back_when_no_key(tmp_path, monkeypatch):
    # API 키 없음 → 폴백 그라데이션이 생성되고 파일 존재
    monkeypatch.setattr(gi, "_call_gemini", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no key")))
    out = tmp_path / "hero.png"
    res = gi.generate_hero("prompt", out, api_key=None)
    assert res["fallback"] is True
    assert out.exists() and out.stat().st_size > 0


def test_generate_hero_falls_back_when_api_raises(tmp_path, monkeypatch):
    # 키가 있어도 _call_gemini가 예외 → 폴백 PNG가 생성되어야 함
    def boom(prompt, key):
        raise RuntimeError("API 500")
    monkeypatch.setattr(gi, "_call_gemini", boom)
    out = tmp_path / "hero.png"
    res = gi.generate_hero("prompt", out, api_key="fake")
    assert res["fallback"] is True
    assert out.exists() and out.stat().st_size > 0


def test_generate_hero_uses_api_result(tmp_path, monkeypatch):
    out = tmp_path / "hero.png"
    monkeypatch.setattr(gi, "_call_gemini", lambda prompt, key: b"\x89PNG\r\n\x1a\nFAKEDATA")
    res = gi.generate_hero("prompt", out, api_key="fake")
    assert res["ok"] is True and res["fallback"] is False
    assert out.read_bytes().startswith(b"\x89PNG")
