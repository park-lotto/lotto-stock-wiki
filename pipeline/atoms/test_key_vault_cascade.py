import pipeline.atoms.key_vault as kv


def _setup(monkeypatch, keys_by_group, exhausted):
    """get_keys/_load_state/mark_exhausted를 모킹해 .env·상태파일 없이 검증."""
    monkeypatch.setattr(kv, "get_keys", lambda g: list(keys_by_group.get(g, [])))
    state = {"date": kv._today_str(), "exhausted": {k: list(v) for k, v in exhausted.items()}}
    monkeypatch.setattr(kv, "_load_state", lambda: state)

    def fake_mark(group, key):
        ks = keys_by_group.get(group, [])
        if key in ks:
            i = ks.index(key)
            state["exhausted"].setdefault(group, [])
            if i not in state["exhausted"][group]:
                state["exhausted"][group].append(i)
    monkeypatch.setattr(kv, "mark_exhausted", fake_mark)
    kv._active_idx.clear()
    return state


def test_cascade_falls_back_to_other_groups(monkeypatch):
    _setup(monkeypatch,
           {"ingest": ["i1", "i2"], "general": ["g1"], "embed": ["e1"], "briefing": ["b1"]},
           {"ingest": [0, 1]})  # ingest 둘 다 소진
    casc = kv.get_live_keys_cascade("ingest")
    assert "i1" not in casc and "i2" not in casc
    assert casc == ["g1", "e1", "b1"]  # 다른 그룹 라이브 키로 순차 폴백


def test_cascade_prioritizes_primary_group(monkeypatch):
    _setup(monkeypatch, {"ingest": ["i1", "i2"], "general": ["g1"]}, {})
    casc = kv.get_live_keys_cascade("ingest")
    assert casc[:2] == ["i1", "i2"]  # primary 그룹 먼저


def test_rotate_marks_borrowed_key_in_its_owner_group(monkeypatch):
    st = _setup(monkeypatch,
                {"ingest": ["i1"], "general": ["g1"], "embed": [], "briefing": []},
                {"ingest": [0]})  # ingest 소진 → g1 차용 중
    ok = kv.rotate("ingest")
    assert ok is False                       # g1까지 소진하면 전체 풀 빔
    assert 0 in st["exhausted"]["general"]   # 차용키를 소유그룹(general)에 기록


def test_rotate_true_while_pool_has_keys(monkeypatch):
    _setup(monkeypatch, {"ingest": ["i1"], "general": ["g1", "g2"]}, {"ingest": [0]})
    assert kv.rotate("ingest") is True       # g1 소진해도 g2 남음(전체 풀)
