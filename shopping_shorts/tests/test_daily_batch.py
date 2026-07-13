from shopping_shorts import daily_batch
from shopping_shorts.store import Store


def test_backfill_structures_fills_missing_and_returns_count(tmp_path, monkeypatch):
    s = Store(tmp_path / "b1.db")
    s.save_script("SC1", {"full_text": "대본1"}, category="레시피")
    s.save_script("SC2", {"full_text": "대본2"}, category="레시피")

    monkeypatch.setattr(daily_batch, "analyze_structure",
                         lambda text: {"hook_type": "경고형", "tone": "친근한"})

    n = daily_batch.backfill_structures(s, limit=100)
    assert n == 2
    assert s.get_extract("SC1")["structure"]["hook_type"] == "경고형"
    assert s.extracts_missing_structure(limit=10) == []


def test_recompute_element_stats_skips_categories_below_min(tmp_path, monkeypatch):
    s = Store(tmp_path / "b2.db")
    for i in range(3):
        s.save_script(f"SC{i}", {"full_text": "t"}, category="뷰티")
        s.save_extract_structure(f"SC{i}", {"tone": "친근한"})

    calls = []
    monkeypatch.setattr(daily_batch.element_stats, "cluster_element_values",
                         lambda element, values, **kw: calls.append((element, len(values))) or [])

    n = daily_batch.recompute_element_stats(s)
    assert n == 0  # 표본 3개뿐이라 전부 스킵(카테고리 저장 안 됨)
    # 그래도 cluster_element_values 자체는 호출됨(내부에서 MIN_SAMPLES 판단) — element 개수만큼
    from shopping_shorts.script_generate import ELEM_KEYS
    assert len(calls) == len(ELEM_KEYS)


def test_recompute_element_stats_saves_when_cluster_returns_categories(tmp_path, monkeypatch):
    s = Store(tmp_path / "b3.db")
    s.save_script("SC1", {"full_text": "t"}, category="레시피")
    s.save_extract_structure("SC1", {"tone": "친근한"})

    def fake_cluster(element, values, **kw):
        if element == "tone":
            return [{"label": "친근체", "description": "d", "examples": ["친근한"]}]
        return []
    monkeypatch.setattr(daily_batch.element_stats, "cluster_element_values", fake_cluster)

    n = daily_batch.recompute_element_stats(s)
    assert n == 1
    opts = s.get_element_options("레시피")
    assert opts["tone"][0]["label"] == "친근체"
