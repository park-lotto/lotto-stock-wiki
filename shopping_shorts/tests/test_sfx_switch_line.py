# -*- coding: utf-8 -*-
"""10-07 사장님 — 3단계 [효과음 자동 넣기]가 꺼져 있으면 2단계 줄 효과음도 완성본에 안 들어간다(인스타형 영상).
2단계 보드 효과음 스위치(전체 = deco.sfx_pack, 줄 = deco.sfx_mute_beats)는 3단계와 같은 값·같은 주인(sfx_pack.resolve).
판단 주인: 렌더·캡컷·미리보기 공통 입구 mix_pipeline._resolve_sfx_paths(줄 효과음 남기기) · sfx_pack.resolve(켜짐·끈 칸)."""
from shopping_shorts import mix_pipeline
from shopping_shorts import sfx_pack
from shopping_shorts import storyboard as sb
from shopping_shorts import video_assemble as va
from shopping_shorts.tests.test_sfx_pack import _Store, _tl
from shopping_shorts.tests.test_meme_sfx_picks_143 import env, _board  # noqa: F401 — pytest 고정물

_ASSETS = {501: {"media_path": "wow.wav"}, 777: {"media_path": "mine.wav"}}


def _plan(tl):
    """칸 3 = 2단계 줄 효과음(line), 칸 4 = 사람이 3단계에서 고른 옛 효과음(manual). timeline 칸에도 같은 sfx 를 싣는다(렌더 모양)."""
    tl[3]["sfx"] = sb.sfx_line(501, "리액션 탄성")
    tl[4]["sfx"] = {"asset_id": 777, "match_type": "manual", "position": "first"}
    return {"beats": [dict(beat_idx=b["beat_idx"], **({"sfx": b["sfx"]} if b.get("sfx") else {})) for b in tl]}


def _job(**deco):
    return {"job_id": "j3", "customer_id": 3, "deco": deco}


def test_체크_끔이면_줄효과음_빠지고_사람고른건_남는다():
    tl = _tl()
    plan = _plan(tl)
    on = mix_pipeline._resolve_sfx_paths(_Store(assets=_ASSETS), plan, 3, job=_job(sfx_pack="auto"))
    assert on.get(3) == "wow.wav" and on.get(4) == "mine.wav" and "_pack" in on
    off = mix_pipeline._resolve_sfx_paths(_Store(assets=_ASSETS), plan, 3, job=_job(sfx_pack="off"))
    assert 3 not in off and off.get(4) == "mine.wav" and "_pack" not in off
    ev = va.sfx_events_for(tl, off)
    assert [e[0] for e in ev] == ["mine.wav"]                    # 렌더 타점에도 줄 효과음 없음
    # 관리자 스위치가 꺼져 팩이 없어도 같다(체크 = resolve 결과)
    sw = mix_pipeline._resolve_sfx_paths(_Store(on="", assets=_ASSETS), plan, 3, job=_job(sfx_pack="auto"))
    assert 3 not in sw and sw.get(4) == "mine.wav"


def test_칸_끄면_그칸_팩소리와_줄효과음_둘다_없음():
    tl = _tl()
    plan = _plan(tl)
    paths = mix_pipeline._resolve_sfx_paths(_Store(assets=_ASSETS), plan, 3, job=_job(sfx_pack="auto", sfx_mute_beats=[3]))
    assert 3 not in paths and paths.get(4) == "mine.wav"
    ev = va.sfx_events_for(tl, paths)
    b3 = tl[3]
    assert not [e for e in ev if b3["t0"] - 0.3 <= e[1] < b3["t0"] + b3["dur"]]     # 그 칸 소리 0(휙 앞당김 포함)
    other = [e for e in ev if e[1] >= tl[1]["t0"] and e[1] < tl[2]["t0"] + tl[2]["dur"]]
    assert other                                                  # 다른 칸은 그대로 운다


def test_2단계_미리보기와_렌더가_같은_스위치로_판단():
    lines = [{"role": b["role"], "text": b["narration"]} for b in _tl()]
    roles = [x["role"] for x in lines]
    st = _Store()
    # 줄 끔 — 미리보기 그 줄 칩 0, 렌더도 그 칸 0
    pk = sfx_pack.preview_pack(st, 3, roles, deco={"sfx_pack": "auto", "sfx_mute_beats": [2]})
    rows = sfx_pack.preview_lines(lines, pk)
    assert rows[2] == [] and rows[3]
    rp = sfx_pack.resolve(st, _job(sfx_pack="auto", sfx_mute_beats=[2]))
    assert rp["mute_beats"] == pk["mute_beats"] == [2]
    # 전체 끔 — 미리보기 팩 없음 = 렌더 팩 없음
    assert sfx_pack.preview_pack(st, 3, roles, deco={"sfx_pack": "off"}) is None
    assert sfx_pack.resolve(st, _job(sfx_pack="off")) is None
    # 보드 값이 없으면 종전(job deco 그대로)
    assert sfx_pack.preview_pack(st, 3, roles, job=_job(sfx_pack="off"), deco={}) is None


def test_api_2단계_스위치_미리보기와_확정_저장(env):
    st, ids, sid, c = env
    st.set_setting("meme_enabled", "1")
    st.set_setting("sfx_pack_enabled", "1")
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board(), "sfx_pack": "auto"}).json()
    assert r["pack_sfx_on"] is True and r["slots"][0]["sfx_live"] is True and r["slots"][0]["sfx_pick"] == sid
    assert any(s["pack_sfx"] for s in r["slots"])
    # 줄 0 끔 → 그 줄 칩 0·줄 효과음 안 들어감, 다른 줄은 그대로
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board(), "sfx_pack": "auto", "sfx_mute_beats": [0]}).json()
    assert r["slots"][0]["pack_sfx"] == [] and r["slots"][0]["sfx_live"] is False and r["slots"][1]["sfx_live"] is True
    # 전체 끔 → 팩 없음·줄 효과음 안내(sfx_live False)
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board(), "sfx_pack": "off"}).json()
    assert r["pack_sfx_on"] is False and all(s["sfx_live"] is False for s in r["slots"])
    assert r["slots"][0]["sfx_pick"] == sid                       # 고른 건 남는다(켜면 다시 들어감)
    # 확정 → 새 job 에 같은 저장 API(3단계 스위치와 같은 것)로 넘긴다
    assert c.post("/api/produce/mix/settings", json={"job_id": "j1", "sfx_pack": "off", "sfx_mute_beats": [0]}).json()["ok"]
    d = st.get_mix_job("j1")["deco"]
    assert d["sfx_pack"] == "off" and d["sfx_mute_beats"] == [0]


def test_api_짤스위치_꺼지면_보드_그대로(env):
    st, ids, sid, c = env
    st.set_setting("meme_enabled", "")
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board(), "sfx_pack": "off"}).json()
    assert all("pack_sfx" not in s and "sfx_live" not in s and "sfx_pick" not in s for s in r["slots"])
