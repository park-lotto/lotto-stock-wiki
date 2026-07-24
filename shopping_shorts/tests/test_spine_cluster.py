from shopping_shorts import spine_cluster


def test_cluster_uses_enum_hint_and_maps_assignments():
    captured = {}

    def fake_call(prompt, schema):
        captured["schema"] = schema
        captured["prompt"] = prompt
        return {"assignments": [
            {"source_id": 1, "spine_name": "제3자의심→인정", "situation_type": "레시피"},
            {"source_id": 2, "spine_name": "__NEW__", "situation_type": "뷰티"}]}

    sources = [{"id": 1, "full_text": "글1", "product_category": "레시피"},
               {"id": 2, "full_text": "글2", "product_category": "뷰티"}]
    existing = [{"name": "제3자의심→인정", "situation_type": "레시피"}]
    out = spine_cluster.cluster_sources(sources, existing, call=fake_call)
    enum = captured["schema"]["properties"]["assignments"]["items"]["properties"]["spine_name"]["enum"]
    assert "제3자의심→인정" in enum and "__NEW__" in enum
    assert {o["source_id"] for o in out} == {1, 2}


def test_cluster_empty_on_no_call():
    out = spine_cluster.cluster_sources([{"id": 1, "full_text": "x"}], [], call=lambda *a, **k: None)
    assert out == []


def test_cluster_empty_on_no_sources():
    out = spine_cluster.cluster_sources([], [{"name": "a"}], call=lambda *a, **k: {"assignments": []})
    assert out == []
