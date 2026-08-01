"""Task 7 최종 재실측 — **라이브 경로 그대로**(2026-08-01, v2).

★v1의 문제(어제 두 번 반복한 실수를 세 번째로 할 뻔했다): 플래그만 손으로 맞추고
  `bank_context=""`, `video_type=None`, `is_recipe=False`로 불렀다. 라이브는
  `bank_enabled=1`이라 부품은행 블록을 프롬프트에 실어 보내고, `is_recipe`는 소스
  다수결로 정해진다 — **다른 프롬프트로 재고 통과 판정을 내릴 뻔했다.**

v2는 설정을 손으로 쓰지 않는다. 서버 `reference.db` 사본을 그대로 열어
`mix_pipeline._plan_and_tts`가 하는 것과 **같은 순서로 같은 인자**를 만든다:

  ping_pong      = settings.ping_pong_enabled == "1"
  backbone_base  = settings.backbone_base_enabled == "1"
  judge          = backbone_base or ping_pong or settings.bank_enabled == "1"
  bank_context   = bank_assemble.parts_block(store)      (bank_enabled == "1"일 때)
  is_recipe      = mix_pipeline._sources_is_recipe(source_scripts)
  video_type     = None (자동판별) — run_mix_job의 기본 경로와 동일

검사:
  1) 화면 중복 0
  2) **Gemini가 정한 세트 순서가 그대로 화면에 나왔는가**
     — 설계 스펙의 핵심 불변식("이 순서·개수는 이후 절대 불변"). 소스별 시간순은
       불변식이 아니다(Gemini가 스토리 흐름으로 소스를 넘나들며 고르는 게 설계다) —
       v2까지 그걸 '역전'으로 세다가 정상 동작을 NG로 오판했다.
       세트 **안** 재배치도 말맞춤 `_order_clips_by_words`의 의도된 동작이라 세지 않는다.
  3) 담은 소스를 전부 쓰는가
  4) CTA가 마지막인가 / slot_source가 gemini인가(조용한 폴백 검출)
  5) 후보 개수가 n_candidates(3) 이하인가
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts import mix_pipeline                                  # noqa: E402
from shopping_shorts.edit_plan import (                                   # noqa: E402
    build_scene_first_plan, _build_inventory, _build_source_sentence_sets)

FIXTURE = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/fixture_live.json"
TARGET = 30
N_CANDIDATES = 3


def _seg_idx(seg_id):
    try:
        return int(str(seg_id).rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return -1


def _live_args(store, source_scripts):
    """mix_pipeline이 build_scene_first_plan에 넘기는 것과 같은 인자를 만든다."""
    ping_pong = store.get_setting("ping_pong_enabled", "") == "1"
    backbone_base = store.get_setting("backbone_base_enabled", "") == "1"
    bank_on = store.get_setting("bank_enabled", "") == "1"
    bank_context = ""
    if bank_on:
        from shopping_shorts import bank_assemble
        bank_context = bank_assemble.parts_block(store)
    return {
        "ping_pong": ping_pong,
        "backbone_base": backbone_base,
        "judge": (backbone_base or ping_pong or bank_on),
        "bank_context": bank_context,
        "is_recipe": mix_pipeline._sources_is_recipe(source_scripts),
    }


def main():
    with open(FIXTURE, encoding="utf-8") as f:
        raw = json.load(f)
    source_scripts = list(raw.values())

    from shopping_shorts.store import Store
    from shopping_shorts.config import DB_PATH
    store = Store(DB_PATH)      # 서버에서 받아온 라이브 reference.db 사본
    args = _live_args(store, source_scripts)
    print(f"소스 {len(source_scripts)}개 / 세그 합계 "
          f"{sum(len(s.get('segments') or []) for s in source_scripts)}")
    print(f"라이브 인자: ping_pong={args['ping_pong']} · backbone_base={args['backbone_base']} "
          f"· judge={args['judge']} · is_recipe={args['is_recipe']} "
          f"· bank_context {len(args['bank_context'])}자 "
          f"· REWRITE_MIX={os.getenv('REWRITE_MIX', '(기본1)')}")
    if args["ping_pong"] and not args["bank_context"]:
        print("⚠️ bank_enabled=1인데 bank_context가 비었다 — 라이브와 다른 프롬프트다")

    # seg_id -> (video_id, 그 소스 안에서 세트가 몇 번째인가)
    seg_map, _inv = _build_inventory(source_scripts)
    set_of = {}
    per_src = {}
    for st in _build_source_sentence_sets(seg_map):
        vid = st["video_id"]
        n = per_src.get(vid, 0)
        per_src[vid] = n + 1
        for s in st["segs"]:
            set_of[s["seg_id"]] = (vid, n)

    # Gemini가 정한 세트 순서를 가로채 기록한다(불변식 대조용 — 사후에 알 방법이 없다).
    import shopping_shorts.edit_plan as _ep
    slot_order = {}
    _orig = _ep._pick_slot_groups

    def _spy(seg_map_, target_=None, call=None):
        groups, src, info = _orig(seg_map_, target_, call)
        if info and not slot_order:
            print(f"슬롯 관측: 세트 {info['sets_total']}{info['sets_by_source']} → "
                  f"선택 {info['chosen']} → 통과 {info['kept']} · "
                  f"잘림 {info['filtered']} · 채택 {info['picked_by_source']} · "
                  f"미사용소스 {info['sources_unused']}")
        if not slot_order:
            for gi, g in enumerate(groups):
                for s in g:
                    slot_order[s["seg_id"]] = gi
        return groups, src, info

    _ep._pick_slot_groups = _spy
    try:
        sf = build_scene_first_plan(source_scripts, "", TARGET, n_candidates=N_CANDIDATES,
                                    video_type=None, **args)
    finally:
        _ep._pick_slot_groups = _orig
    print(f"Gemini 세트 순서: {len(set(slot_order.values()))}세트")
    cands = sf.get("candidates") or []
    n_ok = len(cands) <= N_CANDIDATES
    print(f"후보 {len(cands)}개 (상한 {N_CANDIDATES}) → {'OK' if n_ok else 'NG'}")
    if not cands:
        print("❌ 후보 0개 — 폴백 경로")
        return 1
    if sum(1 for c in cands if c.get("recommended")) != 1:
        print("❌ 추천 후보가 1개가 아니다")
        n_ok = False

    bad = 0 if n_ok else 1
    for i, c in enumerate(cands):
        plan = c["plan"]
        beats = plan.get("beats") or []
        ids = [(b.get("primary") or {}).get("seg_id") for b in beats]
        dup = len(ids) - len(set(ids))
        # 불변식: 최종 비트의 화면이 Gemini가 정한 세트 순서를 거스르지 않는다.
        gis = [slot_order[x] for x in ids if x in slot_order]
        rev = sum(1 for a, b in zip(gis, gis[1:]) if b < a)
        # 참고 지표: 세트 안에서 컷이 앞뒤로 바뀐 횟수(말맞춤의 의도된 대가)
        rev_in_set = 0
        prev_gi = prev_ix = None
        for x in ids:
            if x not in slot_order:
                continue
            gi, ix = slot_order[x], _seg_idx(x)
            if prev_gi == gi and ix < prev_ix:
                rev_in_set += 1
            prev_gi, prev_ix = gi, ix
        srcs = len({set_of[x][0] for x in ids if x in set_of})
        cta_last = "cta" in str(beats[-1].get("role", "")).lower() if beats else False
        slot = plan.get("slot_source")
        ok = (dup == 0 and rev == 0 and cta_last and slot == "gemini"
              and srcs == len(source_scripts))
        bad += 0 if ok else 1
        print(f"\n[{i}]{'★' if c.get('recommended') else ' '} 비트 {len(beats)} · 중복 {dup} · "
              f"순서위반 {rev} · 소스 {srcs}/{len(source_scripts)} · CTA끝 {cta_last} · "
              f"slot_source={slot} · 세트내재배치 {rev_in_set}(말맞춤) → {'OK' if ok else 'NG'}")
        for b in beats:
            print(f"   {(b.get('primary') or {}).get('seg_id'):<24} "
                  f"[{b.get('role', '')}] fit={b.get('fit')} "
                  f"{(b.get('narration') or '')[:40]}")
    print(f"\n=== 후보 {len(cands)}개 중 NG {bad}개 ===")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
