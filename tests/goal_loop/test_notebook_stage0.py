from scripts.goal_loop import notebook_stage0 as ns


def test_build_notebook_no_atoms_returns_zero(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "_build_notebook_bundle",
                        lambda **kw: {"label": "x", "atoms_n": 0, "md_files": [], "yt_urls": [], "web_urls": []})
    r = ns.build_notebook("2026-07-03")
    assert r["atoms_n"] == 0 and r["notebook_id"] is None


def test_build_notebook_success(monkeypatch, tmp_path):
    monkeypatch.setattr(ns.nlm_bridge, "_build_notebook_bundle",
                        lambda **kw: {"label": "오늘", "atoms_n": 12,
                                      "md_files": [("[허브추출] 오늘 발언 12건", "본문내용")],
                                      "yt_urls": [], "web_urls": []})
    monkeypatch.setattr(ns, "OUT_DIR", tmp_path)
    monkeypatch.setattr(ns.nlm_bridge, "create_notebook",
                        lambda title: {"ok": True, "notebook_id": "nb-1", "error": ""})
    created = {}
    monkeypatch.setattr(ns.nlm_bridge, "add_source_file",
                        lambda nb_id, fp, title: created.setdefault("called", (nb_id, fp, title)) or {"ok": True, "error": ""})
    r = ns.build_notebook("2026-07-03")
    assert r["notebook_id"] == "nb-1" and r["atoms_n"] == 12
    assert r["url"] == "https://notebooklm.google.com/notebook/nb-1"
    assert created["called"][0] == "nb-1"


def test_build_notebook_create_fails_returns_none_id(monkeypatch, tmp_path):
    monkeypatch.setattr(ns.nlm_bridge, "_build_notebook_bundle",
                        lambda **kw: {"label": "오늘", "atoms_n": 5,
                                      "md_files": [("t", "본문")], "yt_urls": [], "web_urls": []})
    monkeypatch.setattr(ns, "OUT_DIR", tmp_path)
    monkeypatch.setattr(ns.nlm_bridge, "create_notebook",
                        lambda title: {"ok": False, "notebook_id": None, "error": "실패"})
    r = ns.build_notebook("2026-07-03")
    assert r["notebook_id"] is None


def test_query_card_content_returns_answer(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "notebook_query",
                        lambda nb_id, q, timeout=180: {"ok": True, "answer": "📌 오늘 핵심\n• 테스트", "error": ""})
    text = ns.query_card_content("nb-1", "2026-07-03")
    assert "📌" in text


def test_query_card_content_fails_returns_empty(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "notebook_query",
                        lambda nb_id, q, timeout=180: {"ok": False, "answer": "", "error": "x"})
    assert ns.query_card_content("nb-1", "2026-07-03") == ""


def test_generate_deep_report_success(monkeypatch, tmp_path):
    monkeypatch.setattr(ns.nlm_bridge, "create_report",
                        lambda nb_id, fmt="Briefing Doc", language="ko", out_dir=None:
                        {"ok": True, "markdown": "본문", "ready": True, "url": "https://x", "error": ""})
    p = ns.generate_deep_report("nb-1", "2026-07-03")
    assert p is not None


def test_generate_deep_report_failure_returns_none(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_report",
                        lambda nb_id, fmt="Briefing Doc", language="ko", out_dir=None:
                        (_ for _ in ()).throw(RuntimeError("nlm down")))
    assert ns.generate_deep_report("nb-1", "2026-07-03") is None


def test_generate_infographic_success(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": {"ok": True, "path": "/x/info.png", "error": ""})
    p = ns.generate_infographic("nb-1", "2026-07-03")
    assert p == "/x/info.png"


def test_generate_infographic_failure_returns_none(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": {"ok": False, "path": "", "error": "실패"})
    assert ns.generate_infographic("nb-1", "2026-07-03") is None


def test_generate_infographic_no_notebook_id_returns_none_without_calling(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": called.__setitem__("n", called["n"] + 1) or {"ok": True, "path": "x", "error": ""})
    assert ns.generate_infographic(None, "2026-07-03") is None
    assert called["n"] == 0


def test_generate_infographic_exception_returns_none(monkeypatch):
    monkeypatch.setattr(ns.nlm_bridge, "create_infographic",
                        lambda nb_id, out_dir=None, focus="": (_ for _ in ()).throw(RuntimeError("nlm down")))
    assert ns.generate_infographic("nb-1", "2026-07-03") is None
