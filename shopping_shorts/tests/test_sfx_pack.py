# -*- coding: utf-8 -*-
"""썰채널 효과음팩 자동배치 — 이븐쇼핑 실측 규칙이 코드에 그대로 들어갔나."""
import os

from shopping_shorts import sfx_pack
from shopping_shorts import video_assemble as va
from shopping_shorts import mix_pipeline


_SPINES = [{"id": 70, "name": "유튜브 「OO도 당황한 천재 발명품」", "fit_categories": ["발명품형"]},
           {"id": 56, "name": "유튜브 「OO도 감탄한 천재 아이디어」", "fit_categories": ["오용형"]},
           {"id": 12, "name": "사회증거형", "fit_categories": ["기타", "사회증거형", "홈템"]}]


class _Store:
    """style: 이 job의 제작 작업이 고른 스파인 id(None=제작 기록 없음)."""
    def __init__(self, on="1", assets=None, style=70):
        self.on, self.assets, self.style = on, assets or {}, style

    def get_setting(self, k, d=""):
        return self.on if k == "sfx_pack_enabled" else d

    def get_scene_asset(self, aid, customer_id=0):
        return self.assets.get(aid)

    def get_work_state_by_job(self, job_id):
        return None if self.style is None else {"script_style_id": self.style}

    def list_spines(self, status=None):
        return list(_SPINES)


def _tl():
    """제목 칸 + 본문 3칸 + 마무리 칸. 칸 안 자막은 caption_lines로 고정(2줄씩)."""
    rows = [
        ("천재가 왜 게으른지 알수있는 제품", ["천재가 왜 게으른지", "알수있는 제품"], 1.6),
        ("지금 해외 SNS에서 수억 조회수가 터지며", ["지금 해외 SNS에서", "수억 조회수가 터지며"], 2.4),
        ("페이퍼로 칼을 감싸 버터를 썰어주면", ["페이퍼로 칼을 감싸", "버터를 썰어주면"], 2.4),
        ("근데 진짜 충격적인 포인트는 여기부터", ["근데 진짜", "충격적인 포인트는 여기부터"], 2.4),
        ("도마 접시 안 사고 이걸로 다 해결한다고", ["도마 접시 안 사고", "이걸로 다 해결한다고"], 2.4),
    ]
    tl, t0 = [], 0.0
    for i, (n, lines, d) in enumerate(rows):
        tl.append({"beat_idx": i, "t0": t0, "dur": d, "narration": n, "caption_lines": lines,
                   "cap_durs": None, "cap_lead": 0.0, "cap_offset": 0.0})
        t0 += d
    return tl


def test_packs_ship_complete():
    packs = sfx_pack.list_packs()
    assert len(packs) == 20
    for _, d in packs:
        for s in sfx_pack.SLOTS:
            assert os.path.getsize(os.path.join(d, s + ".wav")) > 1000


def test_pack_assignment_is_stable_and_overridable():
    a = sfx_pack.pack_for(123)
    assert a == sfx_pack.pack_for(123)
    names = {sfx_pack.pack_for(c)[0] for c in range(200)}
    assert len(names) >= 15                     # 회원끼리 고르게 흩어진다
    assert sfx_pack.pack_for(123, override=5)[0] == "팩05"


def test_gate_is_the_chosen_script_not_the_frame():
    """사장님 2026-09-22: 썰 대본을 골랐을 때만. 채널 틀(scene_style)은 판정에 안 쓴다."""
    frame_job = {"job_id": "j1", "customer_id": 7, "deco": {"scene_style": {"presetId": "x"}}}
    bare_job = {"job_id": "j1", "customer_id": 7, "deco": {}}
    assert sfx_pack.resolve(_Store(style=70), bare_job)                  # 발명품형 대본 — 틀 없어도 켜짐
    assert sfx_pack.resolve(_Store(style=56), bare_job)                  # 오용형
    assert sfx_pack.resolve(_Store(style=12), frame_job) is None         # 썰 틀이어도 사회증거형 대본이면 끔
    assert sfx_pack.resolve(_Store(style=None), frame_job) is None       # 제작 기록 없음 = 끔
    assert sfx_pack.resolve(_Store(style=999), frame_job) is None        # 없는 스파인 = 끔


def test_resolve_needs_admin_switch():
    job = {"job_id": "j1", "customer_id": 7, "deco": {}}
    assert sfx_pack.resolve(_Store(on=""), job) is None                  # 스위치 꺼짐 = 라이브 무변화
    assert sfx_pack.resolve(_Store(), {**job, "deco": {"sfx_pack": "off"}}) is None
    got = sfx_pack.resolve(_Store(), job)
    assert got and os.path.isdir(got["dir"])


def test_events_follow_even_rules():
    tl = _tl()
    ev = sfx_pack.plan_events(tl)
    slots = [e[0] for e in ev]
    assert ev[0][:2] == ("opener", sfx_pack.OPENER_AT)
    # 제목 칸(0~1.6초) 안에는 오프너 말고 없다
    assert [e for e in ev if e[1] < 1.6 - sfx_pack.WHOOSH_LEAD - 1e-9 and e[0] != "opener"] == []
    # 첫 넘김: 휙이 먼저, 틱이 뒤
    assert ("whoosh", round(1.6 - 0.035, 3)) in [(s, round(t, 3)) for s, t, _ in ev]
    assert ("tick", round(1.6 + 0.07, 3)) in [(s, round(t, 3)) for s, t, _ in ev]
    # 문구 규칙
    by_text = {txt: s for s, _, txt in ev if txt}
    assert by_text.get("충격적인 포인트는 여기부터") == "dung"
    assert by_text.get("이걸로 다 해결한다고") == "ding"
    assert by_text.get("페이퍼로 칼을 감싸") == "pop"
    # 소리는 자막이 바뀌는 그 시각에 난다(렌더 자막 함수와 같은 값)
    starts = {round(st, 4) for b in tl for _, st, _ in va.caption_schedule(b)}
    for s, t, txt in ev:
        if txt:
            assert round(t, 4) in starts
    assert "opener" in slots


def test_density_caps_whoosh_first():
    tl, t0 = [], 0.0
    for i in range(12):   # 휙만 나올 평범한 문구로 촘촘히
        tl.append({"beat_idx": i, "t0": t0, "dur": 1.2, "narration": "평범한 문장 하나 둘",
                   "caption_lines": ["평범한 문장", "하나 둘"], "cap_durs": None, "cap_lead": 0.0, "cap_offset": 0.0})
        t0 += 1.2
    ev = sfx_pack.plan_events(tl)
    body = t0 - 1.2
    assert len(ev) <= round(sfx_pack.TARGET_PER_SEC * body) + 1


def test_manual_beat_wins():
    tl = _tl()
    ev = sfx_pack.plan_events(tl, manual_beats={3})
    b3 = tl[3]
    assert not [e for e in ev if b3["t0"] <= e[1] < b3["t0"] + b3["dur"] and e[2]]


def test_render_seam_uses_pack(tmp_path):
    """_resolve_sfx_paths → sfx_events_for 경로로 팩 소리가 실제로 나온다(고치기 전엔 0건)."""
    plan = {"beats": [{"beat_idx": b["beat_idx"], "sfx": {"asset_id": 1, "match_type": "cycle"}} for b in _tl()]}
    store = _Store(assets={1: {"media_path": "auto.wav"}})
    job = {"job_id": "j3", "customer_id": 3, "deco": {}}
    paths = mix_pipeline._resolve_sfx_paths(store, plan, 3, job=job)
    assert "_pack" in paths and not [k for k in paths if k != "_pack"]   # 자동 매칭분은 팩이 대신
    ev = va.sfx_events_for(_tl(), paths)
    assert len(ev) >= 6 and all(os.path.isfile(e[0]) for e in ev)
    assert all(len(e) == 3 and e[2] > 1.0 for e in ev)      # 팩 보정배가 실린다
    # 스위치 꺼짐이면 종전 동작 그대로
    old = mix_pipeline._resolve_sfx_paths(_Store(on="", assets=store.assets), plan, 3, job=job)
    assert "_pack" not in old and old[0] == "auto.wav"


def test_no_single_sound_dominates():
    """2026-09-22 라이브 실측: 기본값을 전부 휙으로 두니 한 편에서 휙 66%(이븐쇼핑 27%)."""
    tl, t0 = [], 0.0
    for i in range(10):
        tl.append({"beat_idx": i, "t0": t0, "dur": 3.0, "narration": "평범한 문장 하나 둘 셋",
                   "caption_lines": ["평범한 문장", "하나 둘", "셋 넷"], "cap_durs": None, "cap_lead": 0.0, "cap_offset": 0.0})
        t0 += 3.0
    from collections import Counter
    c = Counter(s for s, _, _ in sfx_pack.plan_events(tl))
    total = sum(c.values())
    assert max(c.values()) / total <= 0.5, c
    assert {"whoosh", "pop", "click2", "tick"} <= set(c)
