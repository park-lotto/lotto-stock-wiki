# -*- coding: utf-8 -*-
"""필름 롤러 3단계 서버 계약(2026-08-26) — ⑤ 모든 조각 · ④ 화면이 만든 조각.

설계: docs/superpowers/specs/2026-08-26-필름롤러-3단계-design.md

지켜야 할 축 두 개:
  ⑤ `_build_inventory`가 첫·끝(CTA·썸네일) 조각을 **버리지 않고 edge 표식만** 단다.
     단 **모델이 보는 인벤토리(prompt_block)는 종전과 완전히 같다** → AI 자동 배치 회귀 0.
     (예전엔 seg_map에서 통째로 버렸다 — 그래서 seg_map을 훑는 자동 배치 코드가 전부
      "여기 있는 건 다 써도 된다"를 전제로 서 있다. 그 전제를 안 깨는 게 이 파일의 요지)
  ④ `apply_scene_lab`이 화면이 원본 필름에서 오려낸 구간(extra_segs)을 받아들인다.
     서버 seg_map은 job["extract"]에서 매번 새로 만들어 이런 id를 모른다 → 병합 안 하면
     "화면엔 담겼는데 렌더엔 없다"(최악의 실패)가 된다. 클라 입력이므로 방어적으로 검증.
"""
from shopping_shorts import edit_plan


def _seg(sid, i, **kw):
    s = {"seg_id": sid, "start": float(i), "end": float(i) + 2.0,
         "text": f"말{i}", "scene_desc": f"화면{i}", "shot_role": "기타"}
    s.update(kw)
    return s


def _script(n, vid="v"):
    return {"video_id": vid, "segments": [_seg(f"{vid}-{i}", i) for i in range(n)]}


# ── ⑤ _build_inventory — 버리지 않고 표식만 ────────────────────────────────

def test_edge_segments_kept_in_seg_map_with_flag():
    """첫·끝이 seg_map에 살아 있고 edge=True가 붙는다(예전엔 아예 없었다)."""
    seg_map, _ = edit_plan._build_inventory([_script(5)])
    assert set(seg_map) == {f"v-{i}" for i in range(5)}, "조각이 버려졌다"
    assert seg_map["v-0"]["edge"] is True
    assert seg_map["v-4"]["edge"] is True
    for sid in ("v-1", "v-2", "v-3"):
        assert seg_map[sid]["edge"] is False


def test_edge_segments_absent_from_prompt_lines():
    """★회귀 0의 핵심 — 모델이 보는 줄에는 첫·끝이 한 줄도 없다."""
    _, block = edit_plan._build_inventory([_script(5)])
    lines = [l for l in block.split("\n") if l.strip()]
    assert len(lines) == 3, f"프롬프트 줄 수가 변했다: {len(lines)}"
    assert "[v-0]" not in block and "[v-4]" not in block
    for sid in ("v-1", "v-2", "v-3"):
        assert f"[{sid}]" in block


def test_prompt_block_byte_identical_to_old_behavior():
    """옛 동작(첫·끝을 통째로 버린 뒤 만든 줄)과 **글자 하나까지** 같아야 한다.

    옛 결과 = 같은 소스에서 첫·끝을 직접 떼고 부른 것. 두 줄이 같으면 모델 입력은
    바뀐 게 없다 = 대본·매칭 회귀 0.
    """
    segs = [_seg(f"v-{i}", i, label=f"이름{i}", use_point=f"쓸모{i}",
                 action=f"행위{i}", change=f"변화{i}", is_key=(i == 2),
                 motion_level="PEAK" if i == 3 else None,
                 product_benefits=[f"장점{i}"]) for i in range(6)]
    _, new_block = edit_plan._build_inventory([{"video_id": "v", "segments": segs}])
    # 옛 방식 재현: 첫·끝을 미리 떼면 len<5가 될 수 있으니 4개(=자르기 미발동)로 넣는다
    _, old_block = edit_plan._build_inventory([{"video_id": "v", "segments": segs[1:-1]}])
    assert new_block == old_block


def test_short_source_has_no_edge_flag():
    """5개 미만은 종전대로 아무것도 안 자른다 → edge 표식도 안 붙는다."""
    for n in (2, 3, 4):
        seg_map, block = edit_plan._build_inventory([_script(n)])
        assert len(seg_map) == n
        assert all(s["edge"] is False for s in seg_map.values())
        assert all(f"[v-{i}]" in block for i in range(n)), "짧은 소스가 프롬프트에서 빠졌다"


def test_non_edge_segs_gives_old_inventory():
    """자동 배치가 쓰는 재고 = 옛 seg_map과 정확히 같다."""
    seg_map, _ = edit_plan._build_inventory([_script(6)])
    assert set(edit_plan.non_edge_segs(seg_map)) == {"v-1", "v-2", "v-3", "v-4"}
    assert edit_plan.non_edge_segs({}) == {}


def test_auto_fill_never_picks_edge_segments():
    """_fill_beat_screen_time(자동으로 컷을 더 붙이는 곳)이 CTA·썸네일을 안 집는다.

    이게 ⑤의 진짜 위험이다 — seg_map에 조각이 늘면 이 함수가 조용히 그걸 붙인다.
    """
    seg_map, _ = edit_plan._build_inventory([_script(6)])
    beats = [{"beat_idx": 0, "role": "훅", "narration": "말",
              "target_seconds": 99.0,           # 재고를 전부 끌어다 쓰게 만든다
              "primary": {"video_id": "v", "seg_id": "v-1", "start": 1.0, "end": 3.0},
              "alternates": []}]
    out = edit_plan._fill_beat_screen_time(beats, seg_map)
    used = {c.get("seg_id") for c in
            [out[0].get("primary")] + list(out[0].get("alternates") or [])}
    assert "v-0" not in used and "v-5" not in used, f"CTA·썸네일이 자동으로 붙었다: {used}"


def test_model_hallucinating_edge_id_is_still_rejected():
    """★실사고(2026-08-26 개발 중): edge를 seg_map에 살려 보내자 **모델 환각이 통과**했다.

    모델은 프롬프트에서 edge를 볼 수 없으니 edge id를 대면 그건 환각이다. 예전엔
    seg_map에 없어서 `_ground_ref`가 None으로 걸렀는데, 살려 보내면서 그라운딩에
    성공해버렸다 — test_rewrite_mix가 실제로 이걸 잡았다(경로가 통째로 바뀌었다).
    그라운딩은 종전대로 non-edge 재고에서만 되붙여야 한다.
    """
    seg_map, _ = edit_plan._build_inventory([_script(5)])
    raw = {"beats": [{"role": "훅", "narration": "말",
                      "primary": {"seg_id": "v-0"},          # ← edge(=환각)
                      "alternates": []}]}
    out = edit_plan._validate_and_ground(raw, seg_map, 2)
    assert out["beats"] == [], "환각 edge id가 그라운딩을 통과했다"

    # 후보 경로(_ground_candidate)도 같은 판정이어야 한다
    cand = {"hook": "h", "beats": [{"role": "훅", "narration": "말", "seg_ids": ["v-4"]}]}
    assert edit_plan._ground_candidate(cand, seg_map) is None

    # 반대로 정상(non-edge) id는 종전대로 통과한다
    ok = edit_plan._validate_and_ground(
        {"beats": [{"role": "훅", "narration": "말",
                    "primary": {"seg_id": "v-2"}, "alternates": []}]}, seg_map, 2)
    assert [b["primary"]["seg_id"] for b in ok["beats"]] == ["v-2"]


# ── ④ apply_scene_lab — 화면이 만든 조각(extra_segs) ───────────────────────

def _plan():
    return {"beats": [{"beat_idx": 0, "role": "훅", "narration": "말",
                       "primary": {"video_id": "v", "seg_id": "v-1",
                                   "start": 1.0, "end": 3.0},
                       "alternates": []}]}


def _base_map():
    seg_map, _ = edit_plan._build_inventory([_script(5)])
    return seg_map


def _over_ids(plan):
    return [o["seg_id"] for o in plan["beats"][0].get("scene_override") or []]


def test_extra_seg_accepted_and_lands_in_override():
    """화면이 오려낸 구간이 scene_override에 그대로 들어간다(id·타임코드 보존)."""
    seg_map = _base_map()
    plan = edit_plan.apply_scene_lab(_plan(), seg_map, {
        "beats": [{"beat_idx": 0, "list": ["v-1", "film_v_7.5_9.25"]}],
        "extra_segs": {"film_v_7.5_9.25": {
            "video_id": "v", "start": 7.5, "end": 9.25,
            "scene_desc": "손으로 오린 구간", "label": "직접컷"}},
    })
    over = plan["beats"][0]["scene_override"]
    assert _over_ids(plan) == ["v-1", "film_v_7.5_9.25"]
    made = over[1]
    assert made["video_id"] == "v"
    assert made["start"] == 7.5 and made["end"] == 9.25
    assert made["scene_desc"] == "손으로 오린 구간"
    assert made["is_key"] is False and made["shot_role"] == "기타"


def test_extra_segs_does_not_mutate_caller_map():
    """호출자의 seg_map은 그대로 — 사본에만 병합한다."""
    seg_map = _base_map()
    before = set(seg_map)
    edit_plan.apply_scene_lab(_plan(), seg_map, {
        "beats": [{"beat_idx": 0, "list": ["film_x"]}],
        "extra_segs": {"film_x": {"video_id": "v", "start": 1.0, "end": 2.0}},
    })
    assert set(seg_map) == before, "호출자 seg_map이 오염됐다"


def test_extra_seg_never_overwrites_real_segment():
    """진짜 조각과 id가 겹치면 서버 것을 남긴다(클라가 타임코드를 위조해도 안 먹힌다)."""
    seg_map = _base_map()
    real = dict(seg_map["v-2"])
    plan = edit_plan.apply_scene_lab(_plan(), seg_map, {
        "beats": [{"beat_idx": 0, "list": ["v-2"]}],
        "extra_segs": {"v-2": {"video_id": "hack", "start": 999.0, "end": 1000.0}},
    })
    o = plan["beats"][0]["scene_override"][0]
    assert o["video_id"] == real["video_id"]
    assert o["start"] == real["start"] and o["end"] == real["end"]


def test_edge_segment_usable_via_normal_list():
    """⑤+④ 합류점 — 사람이 고른 edge 조각은 이제 override에 들어간다(예전엔 사라졌다)."""
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["v-0", "v-4"]}]})
    assert _over_ids(plan) == ["v-0", "v-4"]


# ── ④ 방어 — 망가진 입력은 예외 없이 조용히 버린다 ─────────────────────────

def test_malformed_extra_segs_dropped_without_raising():
    bad = {
        "no_vid":      {"start": 1.0, "end": 2.0},                     # video_id 없음
        "blank_vid":   {"video_id": "   ", "start": 1.0, "end": 2.0},  # 공백뿐
        "end_le_start": {"video_id": "v", "start": 5.0, "end": 5.0},   # 0초
        "reversed":    {"video_id": "v", "start": 9.0, "end": 3.0},    # 뒤집힘
        "not_number":  {"video_id": "v", "start": "abc", "end": "xyz"},
        "none_times":  {"video_id": "v", "start": None, "end": None},
        "missing":     {"video_id": "v"},                              # 키 자체가 없음
        "not_a_dict":  "문자열",
        "":            {"video_id": "v", "start": 1.0, "end": 2.0},    # 빈 id
    }
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["v-1"] + list(bad)}],
        "extra_segs": bad,
    })
    assert _over_ids(plan) == ["v-1"], "망가진 조각이 새어 들어왔다"


def test_extra_segs_rejects_nonfinite_and_nonstring_video_id():
    """float()·truthy 검사를 **통과해버리는** 값들 — 실측으로 새는 걸 확인하고 막았다.

    - "inf"는 float()도 되고 `inf > 0`도 True다 → 무한대 구간이 렌더로 간다.
    - dict를 str()로 뭉개면 "{'a': 1}"이라는 그럴듯한 video_id가 만들어진다.
    """
    bad = {
        "nan":      {"video_id": "v", "start": "nan", "end": "nan"},
        "inf":      {"video_id": "v", "start": "0", "end": "inf"},
        "neg_inf":  {"video_id": "v", "start": "-inf", "end": "1"},
        "dict_vid": {"video_id": {"a": 1}, "start": 0.0, "end": 1.0},
        "int_vid":  {"video_id": 7, "start": 0.0, "end": 1.0},
    }
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["v-1"] + list(bad)}], "extra_segs": bad})
    assert _over_ids(plan) == ["v-1"]


def test_extra_segs_garbage_container_types():
    """extra_segs 자체가 이상해도 안 죽는다(None·리스트·문자열)."""
    for junk in (None, [], "x", 5):
        plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
            "beats": [{"beat_idx": 0, "list": ["v-1"]}], "extra_segs": junk})
        assert _over_ids(plan) == ["v-1"]


def test_extra_seg_string_fields_truncated():
    """긴 문자열은 잘라 담는다(클라가 메가바이트를 밀어넣어도 계획이 안 붓는다)."""
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["film_long"]}],
        "extra_segs": {"film_long": {"video_id": "v", "start": 0.0, "end": 1.0,
                                     "scene_desc": "가" * 5000, "label": "나" * 5000}},
    })
    o = plan["beats"][0]["scene_override"][0]
    assert len(o["scene_desc"]) == 200


# ── 회귀 — extra_segs가 없으면 종전 그대로 ──────────────────────────────────

def test_absent_extra_segs_behaves_exactly_as_before():
    """extra_segs를 안 보내면 모르는 id는 종전대로 조용히 걸러진다."""
    edits = {"beats": [{"beat_idx": 0, "list": ["v-1", "film_unknown", "v-2"]}]}
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), edits)
    assert _over_ids(plan) == ["v-1", "v-2"]
    assert plan["scene_lab"]["applied"] == 1


def test_trims_and_merges_still_work_with_extra_segs_present():
    """기존 기능(자르기·합치기)이 extra_segs와 함께 와도 그대로 돈다."""
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["v-1", "film_a"], "stretch": True}],
        "merges": {"v-1": ["v-2"]},          # v-1의 끝을 v-2 끝까지 늘린다
        "trims": {"film_a": [0.2, 0.5]},
        "extra_segs": {"film_a": {"video_id": "v", "start": 0.0, "end": 1.0}},
    })
    over = plan["beats"][0]["scene_override"]
    assert over[0]["seg_id"] == "v-1" and over[0]["end"] == 4.0   # 병합으로 늘어남
    assert plan["beats"][0]["stretch_fill"] is True
    # film_a는 [0.2,0.5]가 도려내져 앞·뒤 토막으로 갈린다
    assert [o["seg_id"] for o in over[1:]] == ["film_a", "film_a"]


def test_fixlen_accepts_extra_seg_id():
    """손으로 정한 컷 길이(fixlen)도 화면이 만든 조각에 걸린다."""
    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["film_a"]}],
        "fixlen": {"0:film_a": 1.75},
        "extra_segs": {"film_a": {"video_id": "v", "start": 0.0, "end": 4.0}},
    })
    assert plan["beats"][0]["fixed_lens"] == {"film_a": 1.75}


# ── ④-끝 화면이 오려낸 구간이 **렌더 계획까지** 닿는가 ──────────────────────
# 핸드오프(2026-08-26)가 "유일한 미검증"으로 남긴 축이다. apply_scene_lab까지는
# 테스트가 있었지만, 거기서 만든 조각이 실제로 **잘리는 화면**이 되는지는 아무도 안 봤다.
# 렌더·캡컷·ZIP이 전부 plan_beat_clips_for 하나를 쓰므로(video_assemble 주석) 여기까지
# 닿으면 세 경로 모두 닿는다. seg_map을 다시 뒤지지 않고 scene_override의 좌표만 쓰는
# 구조라 film_ id가 서버 seg_map에 없어도 안전하다 — 그 사실을 못으로 박아둔다.

def test_extra_seg_reaches_render_clip_plan():
    """film_ 조각이 실제 컷(video_id·start)으로 렌더 계획에 나온다."""
    from shopping_shorts import video_assemble

    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["film_v_7.5_9.25"]}],
        "extra_segs": {"film_v_7.5_9.25": {
            "video_id": "v", "start": 7.5, "end": 9.25, "label": "직접컷"}},
    })
    clips = video_assemble.plan_beat_clips_for(
        plan["beats"][0], 1.5, {"v": 30.0})
    assert clips, "화면엔 담겼는데 렌더 계획이 비었다 — 조용히 버려진 것"
    for c in clips:
        assert c["video_id"] == "v"
        # 오려낸 구간 [7.5, 9.25] 밖으로 새지 않는다(유출 0 규약)
        assert 7.5 - 1e-6 <= c["start"], c
        assert c["start"] + c["src_dur"] <= 9.25 + 1e-6, c


def test_extra_seg_render_plan_ignores_server_seg_map():
    """서버 seg_map이 그 id를 몰라도 렌더 계획이 나온다(좌표만 쓰기 때문)."""
    from shopping_shorts import video_assemble

    plan = edit_plan.apply_scene_lab(_plan(), _base_map(), {
        "beats": [{"beat_idx": 0, "list": ["v-1", "film_v_12.0_14.0"]}],
        "extra_segs": {"film_v_12.0_14.0": {
            "video_id": "v", "start": 12.0, "end": 14.0}},
    })
    clips = video_assemble.plan_beat_clips_for(plan["beats"][0], 4.0, {"v": 30.0})
    starts = [round(c["start"], 2) for c in clips]
    assert any(s >= 12.0 for s in starts), f"오려낸 구간이 안 쓰였다: {starts}"


# ── 필름 자막띠 구간 (2026-08-29 사장님 "장면 자막이 안 맞음") ──────────────────
# 종전엔 자막의 끝을 **다음 자막 시작**으로 지어내, 말과 말 사이 공백이 앞 자막에
# 통째로 먹혔다(실측: 0.0~1.2초 자막이 0.0~3.5초로 그려짐 = +2.3초. 마지막 자막은
# 영상 끝까지 +20.9초). 진실은 세그의 end다 — 지어내지 말고 있는 값을 쓴다.
# JS 파일이라 파이썬으로 못 부른다. node로 그 함수만 떼어 실제로 돌린다.

def _caps_widths(caps):
    """filmroll.js drawCaps의 끝시각 규칙을 그 파일에서 읽어 그대로 돌린다."""
    import json
    import re
    import subprocess
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "static" / "filmroll.js").read_text(encoding="utf-8")
    # drawCaps 안의 '끝시각 정하는 세 줄'을 그대로 뽑아 쓴다(규칙을 두 벌로 적지 않는다).
    m = re.search(r"const st = c\[0\];\s*\n\s*(const nxt = [^\n]+)\s*\n\s*(const en = [^\n]+)", js)
    assert m, "drawCaps의 끝시각 규칙을 못 찾았다 — 코드가 바뀌었으면 이 테스트도 같이 고쳐라"
    script = (
        "const caps=" + json.dumps(caps, ensure_ascii=False) + ";const DUR=30;"
        "const out=caps.map((c,i)=>{const st=c[0];" + m.group(1) + " " + m.group(2)
        + " return [st,en];});console.log(JSON.stringify(out));"
    )
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_film_caption_band_uses_real_end_not_next_start():
    """자막띠는 실제 끝 시각으로 그린다 — 공백을 앞 자막이 먹지 않는다."""
    caps = [[0.0, "아이 생일 때마다", 1.2], [3.5, "케이크 고민하던", 4.4],
            [4.4, "엄마들 사이에서", 5.0], [8.0, "난리 난 물건인데", 9.1]]
    got = _caps_widths(caps)
    assert [round(e, 2) for _s, e in got] == [1.2, 4.4, 5.0, 9.1], got


def test_film_caption_band_falls_back_when_no_end():
    """끝이 없는 옛 2칸 caps는 종전대로(다음 시작까지) — 옛 호출부가 안 깨진다."""
    caps = [[0.0, "가"], [3.5, "나"]]
    got = _caps_widths(caps)
    assert [round(e, 2) for _s, e in got] == [3.5, 30.0], got


def test_film_caption_never_overruns_next_caption():
    """end가 다음 자막을 넘겨 들어와도 겹치지 않는다(자막끼리 포개지면 못 읽는다)."""
    caps = [[0.0, "가", 9.9], [3.5, "나", 4.0]]
    got = _caps_widths(caps)
    assert round(got[0][1], 2) == 3.5, got
