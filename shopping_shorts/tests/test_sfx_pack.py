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
        ("title", "천재가 왜 게으른지 알수있는 제품", ["천재가 왜 게으른지", "알수있는 제품"], 1.6),
        ("bait", "지금 해외 SNS에서 수억 조회수가 터지며", ["지금 해외 SNS에서", "수억 조회수가 터지며"], 2.4),
        ("how", "페이퍼로 칼을 감싸 버터를 썰어주면", ["페이퍼로 칼을 감싸", "버터를 썰어주면"], 2.4),
        ("twist", "근데 진짜 충격적인 포인트는 여기부터", ["근데 진짜 충격적인", "포인트는 여기부터"], 2.4),
        ("benefit", "도마 접시 안 사고 이걸로 다 해결한다고", ["도마 접시 안 사고", "이걸로 다 해결한다고"], 2.4),
    ]
    tl, t0 = [], 0.0
    for i, (role, n, lines, d) in enumerate(rows):
        tl.append({"beat_idx": i, "t0": t0, "dur": d, "narration": n, "caption_lines": lines, "role": role,
                   "cap_durs": None, "cap_lead": 0.0, "cap_offset": 0.0})
        t0 += d
    return tl


def test_packs_ship_complete():
    packs = sfx_pack.list_packs()
    assert len(packs) == 21
    for _, d in packs:
        for s in sfx_pack.SLOTS:
            assert os.path.getsize(os.path.join(d, s + ".wav")) > 1000


def test_pack_assignment_is_stable_and_overridable():
    a = sfx_pack.pack_for(123)
    assert a == sfx_pack.pack_for(123)
    # 사장님 확정(2026-09-22): 전 회원이 사장님 팩 하나
    assert {sfx_pack.pack_for(c)[0] for c in range(200)} == {"팩21_사장님"}
    assert sfx_pack.pack_for(123, override=5)[0] == "팩05"        # 수동 지정은 전체 목록에서


def test_gate_is_the_chosen_script_not_the_frame():
    """사장님 2026-09-22: 썰 대본을 골랐을 때만. 채널 틀(scene_style)은 판정에 안 쓴다."""
    frame_job = {"job_id": "j1", "customer_id": 7, "deco": {"scene_style": {"presetId": "x"}}}
    bare_job = {"job_id": "j1", "customer_id": 7, "deco": {}}
    assert sfx_pack.resolve(_Store(style=70), bare_job)                  # 발명품형 대본 — 틀 없어도 켜짐
    assert sfx_pack.resolve(_Store(style=56), bare_job)                  # 오용형
    assert sfx_pack.resolve(_Store(style=12), frame_job) is None         # 썰 틀이어도 사회증거형 대본이면 끔
    assert sfx_pack.resolve(_Store(style=None), frame_job) is None       # 제작 기록 없음 = 끔
    assert sfx_pack.resolve(_Store(style=999), frame_job) is None        # 없는 스파인 = 끔


def test_style_id_saved_on_job_survives_deleted_work():
    """실측 2026-09-22: 제작 기록이 지워지자 썰 대본인데 끔이 됐다 → job에 박힌 번호를 먼저 본다."""
    job = {"job_id": "j9", "customer_id": 7, "deco": {}, "script_structure": {"script_style_id": 70}}
    assert sfx_pack.resolve(_Store(style=None), job)                     # 제작 기록 없어도 켜짐
    job12 = {**job, "script_structure": {"script_style_id": 12}}
    assert sfx_pack.resolve(_Store(style=70), job12) is None             # job 번호가 우선(사회증거형=끔)


def test_roles_alone_can_say_sul():
    """틀 번호가 없는 대본도 칸 역할이 썰 구조면 켜진다(2026-09-23 라이브 job 93ea9d2639e6)."""
    sul_plan = {"beats": [{"role": r} for r in ["훅", "미끼", "공개", "고조1", "고조1", "반전", "마무리"]]}
    other = {"beats": [{"role": r} for r in ["situation", "notice", "ask", "method", "result", "regret"]]}
    assert sfx_pack.looks_sul_by_roles({"edit_plan": sul_plan})
    assert not sfx_pack.looks_sul_by_roles({"edit_plan": other})
    assert not sfx_pack.looks_sul_by_roles({"edit_plan": {"beats": [{"role": "훅"}]}})     # 너무 짧음
    job = {"job_id": "jr", "customer_id": 0, "deco": {}, "edit_plan": sul_plan}
    assert sfx_pack.resolve(_Store(style=None), job)          # 제작 기록·틀 없어도 켜짐


def test_switch_decides_even_for_other_scripts():
    """2026-09-23 사장님: 대본 종류와 무관하게 **체크하면 들어간다**. 기본값만 대본으로 정한다."""
    other = {"beats": [{"role": r} for r in ["situation", "notice", "ask", "method", "result"]]}
    job = {"job_id": "jo", "customer_id": 7, "deco": {}, "edit_plan": other}
    assert sfx_pack.resolve(_Store(style=12), job) is None                       # 기본값 = 꺼짐
    on_job = {**job, "deco": {"sfx_pack": "auto"}}
    assert sfx_pack.resolve(_Store(style=12), on_job)                            # 사람이 켜면 들어간다
    sul_job = {"job_id": "js", "customer_id": 7, "deco": {},
               "edit_plan": {"beats": [{"role": r} for r in ["훅", "미끼", "공개", "고조1", "반전", "마무리"]]}}
    assert sfx_pack.resolve(_Store(style=None), sul_job)                         # 썰 구조면 기본 켜짐
    assert sfx_pack.resolve(_Store(style=None), {**sul_job, "deco": {"sfx_pack": "off"}}) is None


def test_admin_only_mode():
    """2026-09-23 사장님 "관리자만 켜봐": sfx_pack_enabled='admin'이면 사장님(cid 0) 영상에서만."""
    admin_job = {"job_id": "j1", "customer_id": 0, "deco": {}}
    cust_job = {"job_id": "j1", "customer_id": 42, "deco": {}}
    assert sfx_pack.resolve(_Store(on="admin"), admin_job)              # 사장님 = 켜짐
    assert sfx_pack.resolve(_Store(on="admin"), cust_job) is None       # 고객 = 그대로 꺼짐
    assert sfx_pack.resolve(_Store(on="1"), cust_job)                   # 전체 모드면 고객도 켜짐
    assert sfx_pack.resolve(_Store(on="admin2"), admin_job) is None     # 모르는 값 = 끔


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
    # 칸 역할이 소리를 정한다(단어 검색 없음): 반전 칸 첫 자막=둥 · 결과 칸 첫 자막=띠링 · 시연 칸=시연 순서
    by_text = {txt: s for s, _, txt in ev if txt}
    assert by_text.get("근데 진짜 충격적인") == "dung"
    assert by_text.get("도마 접시 안 사고") == "ding"
    assert by_text.get("페이퍼로 칼을 감싸") in sfx_pack.RINGS["시연"]
    # 소리는 자막이 바뀌는 그 시각에 난다(렌더 자막 함수와 같은 값)
    starts = {round(st, 4) for b in tl for _, st, _ in va.caption_schedule(b)}
    for s, t, txt in ev:
        if txt:
            assert round(t, 4) in starts
    assert "opener" in slots


def test_rings_are_the_measured_even_counts():
    """순서는 이븐쇼핑 구간별 실측 건수 그대로 — 16칸 안 비율이 실측 비율과 1칸 이내."""
    from collections import Counter
    for g, counts in sfx_pack.RING_COUNTS.items():
        ring = sfx_pack.RINGS[g]; c = Counter(ring); tot = sum(counts.values())
        for k, v in counts.items():
            assert abs(c[k] - v * len(ring) / tot) <= 1.0, (g, k, c[k], v)


def test_unknown_role_still_gets_sound():
    assert sfx_pack.sounds_for_role("처음보는역할")[1] == sfx_pack.RINGS["떡밥"]
    assert sfx_pack.sounds_for_role("고조3")[1] == sfx_pack.RINGS["시연"]    # 번호 뗀다


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
    assert all(len(e) == 3 and e[2] > 0 for e in ev)        # 팩 보정배가 실린다(크기는 test_every_pack_file_lands_on_slot_target)
    # 스위치 꺼짐이면 종전 동작 그대로
    old = mix_pipeline._resolve_sfx_paths(_Store(on="", assets=store.assets), plan, 3, job=job)
    assert "_pack" not in old and old[0] == "auto.wav"


def test_no_single_sound_dominates():
    """2026-09-22 라이브 실측: 기본값을 전부 휙으로 두니 한 편에서 휙 66%(이븐쇼핑 27%)."""
    tl, t0 = [], 0.0
    for i in range(10):
        tl.append({"beat_idx": i, "t0": t0, "dur": 3.0, "narration": "평범한 문장 하나 둘 셋", "role": "bait",
                   "caption_lines": ["평범한 문장", "하나 둘", "셋 넷"], "cap_durs": None, "cap_lead": 0.0, "cap_offset": 0.0})
        t0 += 3.0
    from collections import Counter
    c = Counter(s for s, _, _ in sfx_pack.plan_events(tl))
    total = sum(c.values())
    assert max(c.values()) / total <= 0.5, c
    assert {"whoosh", "pop", "tick"} <= set(c)


def test_every_pack_file_lands_on_slot_target():
    """2026-09-22 라이브: 팩10 둥 파일이 목표보다 3dB 작아 둥이 약했다 → 렌더 때 파일마다 목표로 맞춘다."""
    import math
    for _, d in sfx_pack.list_packs():
        for slot in sfx_pack.SLOTS:
            p = os.path.join(d, slot + ".wav")
            got = sfx_pack._peak20_db(p) + 20 * math.log10(sfx_pack._gain_for(p, slot)) - sfx_pack.PACK_GAIN_DB
            assert abs(got - sfx_pack.LEVEL_TARGET_DB[slot]) < 0.05, (d, slot, got)


def test_two_sounds_per_scene():
    """2026-09-22 사장님 "장면당 2개": 칸마다 첫 줄 + 가운데 줄."""
    tl = _tl()
    ev = [e for e in sfx_pack.plan_events(tl) if e[0] != "opener"]
    for b in tl[2:]:
        sched = va.caption_schedule(b)
        inside = [e for e in ev if b["t0"] <= e[1] < b["t0"] + b["dur"]]
        want = sorted({round(sched[0][1], 6), round(sched[len(sched) // 2][1], 6)})
        assert sorted(round(e[1], 6) for e in inside) == want, (b["role"], inside)


def test_quiet_slots_raised_to_audible_floor():
    assert min(sfx_pack.LEVEL_TARGET_DB.values()) >= sfx_pack._AUDIBLE_FLOOR_DB


def test_settings_toggle_and_preserve(tmp_path, monkeypatch):
    """3단계 스위치: sfx_pack만 합쳐 저장 · 꾸미기 통째 저장이 이 값을 지우지 않는다."""
    from shopping_shorts import app as A
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"; st = Store(str(db))
    st.create_mix_job("jx", ["u"], 25, "free", customer_id=7)
    st.update_mix_job("jx", deco={"bgm": {"volume": 15}})
    monkeypatch.setattr(A, "DB_PATH", str(db))
    assert A.api_produce_mix_settings({"job_id": "jx", "sfx_pack": "off"})["ok"]
    d = Store(str(db)).get_mix_job("jx")["deco"]
    assert d["sfx_pack"] == "off" and d["bgm"] == {"volume": 15}          # 다른 꾸미기 보존
    A.api_produce_mix_settings({"job_id": "jx", "deco": {"bgm": {"volume": 30}}})   # sfx_pack 모르는 통째 저장
    d = Store(str(db)).get_mix_job("jx")["deco"]
    assert d["sfx_pack"] == "off" and d["bgm"] == {"volume": 30}          # 끈 값 유지
    # ★스위치를 바꾸면 이미 만든 미리보기도 버린다 — 안 그러면 [완성본 만들기]가 옛 영상을 그대로 보여준다
    Store(str(db)).update_mix_job("jx", preview_status="ready")
    A.api_produce_mix_settings({"job_id": "jx", "sfx_pack": "auto"})
    got = Store(str(db)).get_mix_job("jx")
    assert got["deco"]["sfx_pack"] == "auto" and not got.get("preview_status")
    Store(str(db)).update_mix_job("jx", preview_status="ready")
    A.api_produce_mix_settings({"job_id": "jx", "sfx_pack": "auto"})          # 같은 값이면 그대로 둔다
    assert Store(str(db)).get_mix_job("jx").get("preview_status") == "ready"
