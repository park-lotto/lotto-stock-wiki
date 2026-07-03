# tests/nlm_bridge/test_pure_helpers.py
from scripts import nlm_bridge as nb


def test_valid_period():
    assert nb._valid_period("today") == "today"
    assert nb._valid_period("d3") == "d3"
    assert nb._valid_period("garbage") == "all"
    assert nb._valid_period(None) == "all"


def test_tokenize_query_empty_returns_wildcard_token():
    assert nb._tokenize_query("") == [""]


def test_tokenize_query_strips_particles_and_stopwords():
    toks = nb._tokenize_query("삼성전자 관련 이슈 정리해줘")
    assert "삼성전자" in toks
    assert "이슈" not in toks
    assert "정리해줘" not in toks


def test_nb_cat_of():
    assert nb._nb_cat_of("yt") == "youtube"
    assert nb._nb_cat_of("youtube") == "youtube"
    assert nb._nb_cat_of("telegram") == "telegram"
    assert nb._nb_cat_of("report") == "report"


def test_nb_scope_label_today():
    assert nb._nb_scope_label(["telegram", "report"], "today") == "텔레그램·리포트 오늘"


def test_nlm_exe_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(nb.shutil, "which", lambda name: None)
    assert nb._nlm_exe() is None
