# -*- coding: utf-8 -*-
"""2단계 기본 효과음팩 소리 빼기·바꾸기(10-07 사장님) — 고른 대로 렌더·캡컷에 들어간다.
판단 주인: sfx_pack.apply_pack_edit (미리보기 preview_lines · 렌더/캡컷 sfx_events_for → events 가 같은 함수를 부른다)."""
import os

from shopping_shorts import sfx_pack
from shopping_shorts import storyboard as sb
from shopping_shorts import video_assemble as va
from shopping_shorts.tests.test_sfx_pack import _tl

PACK = {"name": "p", "dir": "PK"}


def _per(tl):
    return sfx_pack.plan_per_beat(tl, (), "normal", (), None)


def test_빼기_바꾸기_같은줄_같은이름_순번():
    per = {2: [("pop", 5.0, ""), ("dung", 5.5, ""), ("pop", 6.0, "")]}
    got = sfx_pack.apply_pack_edit(per, {2: {"off": [{"slot": "pop", "n": 1}], "swap": [{"slot": "dung", "n": 0, "to": "ding"}]}})
    assert [e[0] for e in got[2]] == ["pop", "ding"]
    assert got[2][1][1] == 5.5 and got[2][1][3] == {"from": "dung"}          # 시각 그대로, 소리만 바뀜
    keep = sfx_pack.apply_pack_edit(per, {2: {"off": [{"slot": "pop", "n": 1}]}}, keep_off=True)
    assert [e[3] for e in keep[2]] == [None, None, "off"]                   # 화면용: 지우지 않고 표시만


def test_순번_못찾으면_무시하고_로그():
    logs = []
    per = {1: [("pop", 3.0, "")]}
    got = sfx_pack.apply_pack_edit(per, {1: {"off": [{"slot": "pop", "n": 3}, {"slot": "ding", "n": 0}]}}, log=logs.append)
    assert [e[0] for e in got[1]] == ["pop"]          # 다른 소리를 대신 지우지 않는다
    assert len(logs) == 2 and "무시" in logs[0]


def test_이상한_모양은_버린다():
    assert sfx_pack.clean_pack_edit({"off": [{"slot": "nope", "n": 0}], "swap": [{"slot": "pop", "n": 0, "to": "pop"}]}) is None
    assert sfx_pack.clean_pack_edit("x") is None
    assert sfx_pack.clean_pack_edit({"off": [{"slot": "pop", "n": "1", "t": 3.2}]}) == {"off": [{"slot": "pop", "n": 1}]}   # 시각은 안 싣는다


def test_고름없으면_종전과_같다():
    tl = _tl()
    assert sfx_pack.events(tl, PACK) == sfx_pack.events(tl, PACK, pack_edit={})


def _first_ring(tl):
    """소리가 하나 이상 있는 칸 하나와 그 칸 첫 소리."""
    per = _per(tl)
    bi = next(b for b in sorted(per) if b >= 2 and per[b])
    return bi, per[bi][0]


def test_렌더_events_빼기_바꾸기_반영():
    tl = _tl()
    bi, (slot, t, _, _m) = _first_ring(tl)
    base = sfx_pack.events(tl, PACK)
    off = sfx_pack.events(tl, PACK, pack_edit={bi: {"off": [{"slot": slot, "n": 0}]}})
    assert len(off) == len(base) - 1
    assert not any(abs(e[1] - t) < 1e-9 and e[0] == os.path.join("PK", slot + ".wav") for e in off)
    to = "ding" if slot != "ding" else "pop"
    sw = sfx_pack.events(tl, PACK, pack_edit={bi: {"swap": [{"slot": slot, "n": 0, "to": to}]}})
    hit = [e for e in sw if abs(e[1] - t) < 1e-9]
    assert hit and hit[0][0] == os.path.join("PK", to + ".wav")


def test_미리보기와_렌더가_같은_함수로_같은_결과(monkeypatch):
    """preview_lines 와 events 가 같은 timeline·같은 고름이면 남는 소리(이름·시각)가 같다."""
    monkeypatch.setattr(sfx_pack, "list_packs", lambda: [("p", "PK")])
    lines = [{"role": "hook", "text": "와 이거 진짜 뭐야 대박이다"}, {"role": "how", "text": "페이퍼로 칼을 감싸 버터를 썰어주면 됩니다 진짜로"},
             {"role": "twist", "text": "근데 진짜 충격적인 포인트는 여기부터입니다 여러분"}, {"role": "benefit", "text": "도마 접시 안 사고 이걸로 다 해결한다고 하네요"}]
    tl = sfx_pack.preview_timeline(lines)
    per = _per(tl)
    bi = next(b for b in sorted(per) if per[b])
    s0 = per[bi][0][0]
    edit = {"off": [{"slot": s0, "n": 0}]}
    lines[bi]["pack_edit"] = edit
    rows = sfx_pack.preview_lines(lines, PACK)
    shown = sorted((r["slot"], r["t"]) for row in rows for r in row if not r.get("off"))
    rend = sorted((os.path.basename(p)[:-4], round(t, 1)) for p, t, _ in sfx_pack.events(tl, PACK, pack_edit={bi: edit}))
    assert shown == rend
    assert any(r.get("off") for r in rows[bi]) and rows[bi][0]["ref"] == {"slot": s0, "n": 0}


def test_carry_picks_로_beat_에_넘어감():
    got = sb.carry_picks({"sfx_pick": 3, "pack_edit": {"off": [{"slot": "pop", "n": 0}], "junk": 1}})
    assert got == {"sfx_pick": 3, "pack_edit": {"off": [{"slot": "pop", "n": 0}]}}
    assert "pack_edit" not in sb.carry_picks({"pack_edit": {"off": []}})


def test_sfx_events_for_결과에서_뺀소리없고_바꾼소리파일():
    tl = _tl()
    bi, (slot, t, _, _m) = _first_ring(tl)
    to = "ding" if slot != "ding" else "pop"
    tl2 = [dict(b) for b in tl]
    for b in tl2:
        if b["beat_idx"] == bi:
            b["pack_edit"] = {"swap": [{"slot": slot, "n": 0, "to": to}]}
    ev = va.sfx_events_for(tl2, {"_pack": PACK})
    hit = [e for e in ev if abs(e[1] - t) < 1e-9]
    assert hit and hit[0][0] == os.path.join("PK", to + ".wav")
    for b in tl2:
        if b["beat_idx"] == bi:
            b["pack_edit"] = {"off": [{"slot": slot, "n": 0}]}
    ev2 = va.sfx_events_for(tl2, {"_pack": PACK})
    assert not [e for e in ev2 if abs(e[1] - t) < 1e-9]
    assert len(ev2) == len(va.sfx_events_for(tl, {"_pack": PACK})) - 1


def test_스위치꺼짐_팩없음_불변():
    tl = [dict(b, pack_edit={"off": [{"slot": "pop", "n": 0}]}) for b in _tl()]
    assert va.sfx_events_for(tl, {}) == []                    # 팩이 없으면(스위치 꺼짐) 아무 소리도 안 생긴다
    assert sfx_pack.preview_lines([{"role": "hook", "text": "a", "pack_edit": {"off": []}}], None) == [[]]


def test_timeline_에_pack_edit_실림():
    import inspect
    assert '"pack_edit": beat.get("pack_edit")' in inspect.getsource(va)


def test_줄효과음_길이동안_팩소리를_비운다_빼면_돌아온다():
    """10-07 사장님 '겹치는 거 빼고, 빼기 누르면 자동으로 넣어주고' — 실측 951d050cc3df 넷플 두둥 2.0초 끝에 휙이 겹쳤다."""
    from shopping_shorts import sfx_pack
    tl = sfx_pack.preview_timeline([{"role": "title", "text": "가" * 30}, {"role": "twist", "text": "나" * 60},
                                    {"role": "land", "text": "다" * 30}])
    t0 = float(tl[1]["t0"])
    base = sfx_pack.plan_events(tl)
    near = [e for e in base if t0 - 1e-6 <= float(e[1]) < t0 + 2.05]
    held = sfx_pack.plan_events(tl, first_beats={tl[1]["beat_idx"]: 2.0})
    assert not [e for e in held if t0 - 1e-6 <= float(e[1]) < t0 + 2.05]
    assert len(held) < len(base) and near
    assert sfx_pack.plan_events(tl, first_beats=()) == base      # 줄 효과음을 빼면 종전 그대로 돌아온다
