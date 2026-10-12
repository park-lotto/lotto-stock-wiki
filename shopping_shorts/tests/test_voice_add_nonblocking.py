# -*- coding: utf-8 -*-
"""성우 추가가 웹 요청을 막거나 같은 샘플을 두 번 굽지 않는지 검증한다."""
from shopping_shorts import eleven_voices as ev
import shopping_shorts.app as appmod
from shopping_shorts.store import Store


class MemoryStore:
    def __init__(self, rows=None):
        self.rows = {p["preset_id"]: dict(p) for p in (rows or [])}

    def list_voice_presets(self):
        return list(self.rows.values())

    def get_voice_preset(self, preset_id):
        row = self.rows.get(preset_id)
        return dict(row) if row else None

    def upsert_voice_preset(self, p):
        self.rows[p["preset_id"]] = dict(p)


def _rows(voice_id="voice-1", owner=7, group_id="lib-test-voice"):
    rows = ev.build_group(voice_id, "테스트", group_id=group_id)
    for row in rows:
        row["owner_customer_id"] = owner
    return rows


def test_store가_성우_소유자를_다시_돌려준다(tmp_path):
    store = Store(tmp_path / "voice.db")
    row = _rows()[0]
    store.upsert_voice_preset(row)

    assert store.get_voice_preset(row["preset_id"])["owner_customer_id"] == 7
    assert store.list_voice_presets()[0]["owner_customer_id"] == 7


def test_registration_status는_소유자와_실제파일을_함께_본다(tmp_path, monkeypatch):
    monkeypatch.setattr(ev.voice_presets, "SAMPLES_DIR", tmp_path)
    rows = _rows()
    for row in rows:
        (tmp_path / row["sample_file"]).write_bytes(b"mp3")
    store = MemoryStore(rows)

    assert ev.registration_status(store, "voice-1", 7)["ready"] is True
    assert ev.registration_status(store, "voice-1", 8)["registered"] is False
    (tmp_path / rows[0]["sample_file"]).unlink()
    assert ev.registration_status(store, "voice-1", 7)["ready"] is False


def test_카드만_먼저_등록해도_기존샘플을_지우지_않는다(tmp_path, monkeypatch):
    monkeypatch.setattr(ev.voice_presets, "SAMPLES_DIR", tmp_path)
    rows = _rows()
    for row in rows:
        (tmp_path / row["sample_file"]).write_bytes(b"mp3")
    store = MemoryStore(rows)

    ev.register(store, "voice-1", "테스트", bake=False, owner_customer_id=7,
                group_id="lib-test-voice")

    assert all(p["sample_file"] for p in store.list_voice_presets())


def test_재시도는_없는_샘플만_굽는다(tmp_path, monkeypatch):
    monkeypatch.setattr(ev.voice_presets, "SAMPLES_DIR", tmp_path)
    rows = _rows()
    for row in rows[:3]:
        (tmp_path / row["sample_file"]).write_bytes(b"mp3")
    rows[3]["sample_file"] = None
    store = MemoryStore(rows)
    baked = []

    def fake_bake(p, customer_id=0):
        baked.append((p["variant"], customer_id))
        (tmp_path / p["sample_file"]).write_bytes(b"mp3")

    monkeypatch.setattr(ev, "bake_sample", fake_bake)
    ev.register(store, "voice-1", "테스트", bake=True, missing_only=True,
                owner_customer_id=7, group_id="lib-test-voice")

    assert baked == [("whisper", 7)]


def test_같은_성우의_백그라운드작업은_하나만_등록된다(monkeypatch):
    class Tasks:
        def __init__(self):
            self.calls = []

        def add_task(self, fn, *args):
            self.calls.append((fn, args))

    monkeypatch.setattr(appmod, "Store", lambda _path: object())
    monkeypatch.setattr(ev, "registration_status", lambda *a, **k: {
        "registered": False, "group_id": None, "ready": False, "rows": []})
    register_calls = []

    def fake_register(*args, **kwargs):
        register_calls.append(kwargs)
        return {"group_id": "lib-new", "count": 4, "sample_failed": []}

    monkeypatch.setattr(ev, "register", fake_register)
    tasks = Tasks()
    with appmod._VOICE_SAMPLE_JOBS_LOCK:
        appmod._VOICE_SAMPLE_JOBS.clear()

    first = appmod._register_voice_card(tasks, "v-new", "새 성우", owner_customer_id=9)
    second = appmod._register_voice_card(tasks, "v-new", "새 성우", owner_customer_id=9)

    assert first["samples_pending"] and second["samples_pending"]
    assert len(tasks.calls) == 1
    assert [call["bake"] for call in register_calls] == [False, False]
    with appmod._VOICE_SAMPLE_JOBS_LOCK:
        appmod._VOICE_SAMPLE_JOBS.clear()


def test_샘플이_준비된_성우는_재등록도_재과금도_없다(monkeypatch):
    class Tasks:
        calls = []

        def add_task(self, *args):
            self.calls.append(args)

    monkeypatch.setattr(appmod, "Store", lambda _path: object())
    monkeypatch.setattr(ev, "registration_status", lambda *a, **k: {
        "registered": True, "group_id": "lib-ready", "ready": True,
        "rows": [{}, {}, {}, {}]})
    monkeypatch.setattr(ev, "register", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("준비된 성우를 다시 등록하면 안 됨")))

    out = appmod._register_voice_card(Tasks(), "v-ready", "기존 성우", owner_customer_id=9)

    assert out["already_registered"] is True
    assert out["samples_pending"] is False
    assert Tasks.calls == []
