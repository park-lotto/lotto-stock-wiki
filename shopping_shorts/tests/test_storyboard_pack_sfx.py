# -*- coding: utf-8 -*-
"""2단계 스토리보드 줄에 기본 효과음팩 미리보기(관제 143 확장, 10-07 사장님).
주인: sfx_pack.preview_lines(배치=plan_events 그대로) · sfx_pack.preview_pack(팩 결정=resolve 그대로). app._sb_picks 는 싣기만."""
import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import sfx_pack
from shopping_shorts.store import Store
from shopping_shorts.tests.test_sfx_pack import _Store

LINES = [{"role": "hook", "text": "이거 하나로 떼돈 번 사람이 있어요"},
         {"role": "bait_1", "text": "처음엔 다들 비웃었는데요 이게 진짜 대박이 났어요"},
         {"role": "reveal", "text": "바로 이 접이식 물통입니다 접으면 손바닥만 해져요"},
         {"role": "twist", "text": "근데 진짜 놀라운 건 따로 있어요 물이 안 새요"},
         {"role": "cta", "text": "이러니 품절대란이 났죠"}]


def _pack():
    p = sfx_pack.pack_for(0)
    assert p, "팩 파일이 있어야 시험이 뜻이 있다"
    return {"name": p[0], "dir": p[1], "density": "normal", "level": "normal", "mute_beats": []}


def test_미리보기는_plan_events_와_같은_슬롯_순서():
    pk = _pack()
    rows = sfx_pack.preview_lines(LINES, pk)
    direct = sfx_pack.plan_events(sfx_pack.preview_timeline(LINES), (), density="normal")
    got = sorted(((x["t"], x["slot"]) for r in rows for x in r))
    assert [s for _, s in got] == [e[0] for e in direct]
    assert rows[0][0]["slot"] == "opener" and rows[1][0]["slot"] == "whoosh"      # 휙은 둘째 줄 몫
    assert all(x["url"].startswith("/api/produce/sfx_pack/sound/") and x["label"] for r in rows for x in r)


def test_줄효과음_줄은_첫발_빠짐():
    pk = _pack()
    base = sfx_pack.preview_lines(LINES, pk)
    got = sfx_pack.preview_lines(LINES, pk, first_lines=[3])
    assert base[3] and got[3] == [x for x in base[3] if x["t"] > base[3][0]["t"]]
    direct = sfx_pack.plan_events(sfx_pack.preview_timeline(LINES), (), first_beats=[3])
    assert sum(len(r) for r in got) == len(direct)


def test_팩없으면_빈목록():
    assert sfx_pack.preview_lines(LINES, None) == [[], [], [], [], []]
    assert sfx_pack.preview_pack(_Store(on=""), 0, [l["role"] for l in LINES]) is None     # 관리자 스위치 꺼짐
    assert sfx_pack.preview_pack(_Store(on="1", style=None), 0, ["a", "b", "c", "d", "e"]) is None   # 썰 아님
    assert sfx_pack.preview_pack(_Store(on="1", style=None), 0, ["hook", "bait", "reveal", "twist", "cta"])  # 역할이 썰


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    st = Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(app_mod, "_sb_job", lambda req, key: (key, {"v": {}}, None))
    monkeypatch.setattr(app_mod, "_sb_gate", lambda req: None)
    return st, TestClient(app_mod.app)


def _slots():
    return [{"slot": l["role"], "line": l["text"]} for l in LINES]


def test_api_스위치꺼짐_불변_켜면_줄마다_pack_sfx(env):
    st, c = env
    st.set_setting("sfx_pack_enabled", "1")
    st.set_setting("meme_enabled", "")
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _slots()}).json()
    assert all("pack_sfx" not in s for s in r["slots"])                          # meme_enabled 꺼짐 = 그대로
    st.set_setting("meme_enabled", "1")
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _slots()}).json()
    assert r["pack_sfx_on"] is True and r["slots"][0]["pack_sfx"][0]["slot"] == "opener"
    snd = c.get(r["slots"][0]["pack_sfx"][0]["url"])
    assert snd.status_code == 200
    st.set_setting("sfx_pack_enabled", "")
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _slots()}).json()
    assert r["pack_sfx_on"] is False and all(s["pack_sfx"] == [] for s in r["slots"])
