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
    # ★v4(2026-08-02): 슬롯이 후보마다 다를 수 있다(_pick_slot_variants). 벌A의 순서로
    #   모든 후보를 재면 **다른 벌을 쓰는 후보가 무조건 '순서위반'으로 찍힌다**(실측:
    #   정상 동작을 NG로 오판했다). 그래서 벌마다 순서표를 따로 만들고, 후보를 잴 때는
    #   **그 후보가 실제로 어느 벌을 썼는지 찾아** 그 표로 검사한다.
    import shopping_shorts.edit_plan as _ep
    slot_orders = []          # [ {seg_id: 세트인덱스}, ... ] 벌 순서대로
    _orig = _ep._pick_slot_variants

    def _spy(seg_map_, target_=None, n=1, call=None):
        variants, src, info, kinds = _orig(seg_map_, target_, n, call)
        if info and not slot_orders:
            print(f"슬롯 관측: 세트 {info['sets_total']}{info['sets_by_source']} → "
                  f"선택 {info['chosen']} → 통과 {info['kept']} · "
                  f"잘림 {info['filtered']} · 채택 {info['picked_by_source']} · "
                  f"미사용소스 {info['sources_unused']}")
            print(f"슬롯 벌: {kinds}")
        if not slot_orders:
            for g in variants:
                m = {}
                for gi, grp in enumerate(g):
                    for s in grp:
                        m[s["seg_id"]] = gi
                slot_orders.append(m)
        return variants, src, info, kinds

    _ep._pick_slot_variants = _spy
    try:
        sf = build_scene_first_plan(source_scripts, "", TARGET, n_candidates=N_CANDIDATES,
                                    video_type=None, **args)
    finally:
        _ep._pick_slot_variants = _orig
    if not slot_orders:
        slot_orders = [{}]
    slot_order = slot_orders[0]
    print(f"Gemini 세트 순서: {len(set(slot_order.values()))}세트 · 벌 {len(slot_orders)}개")

    def _best_order_for(ids):
        """이 후보가 쓴 벌을 찾는다.

        ★단순히 'seg_id가 많이 겹치는 벌'로 고르면 안 된다(2026-08-02 실측 오판):
          벌들이 같은 세트를 공유하므로 겹침 수가 같아지고, 그러면 **엉뚱한 벌**이 뽑혀
          정상 후보가 '순서위반'으로 찍힌다(a98a4c7c3ad1에서 실제로 그랬다).
          그 후보가 실제로 그 벌의 순서를 따르는지(역전 0)까지 보고 고른다."""
        def _rev(m):
            gis = [m[x] for x in ids if x in m]
            return sum(1 for a, b in zip(gis, gis[1:]) if b < a)

        def _hit(m):
            return sum(1 for x in ids if x in m)

        # ⚠️'역전이 가장 적은 벌'을 고르면 **진짜 위반도 가려질 수 있다**. 그래서
        #   후보 세그의 과반이 실제로 들어 있는 벌만 후보로 삼는다 — 아무 벌에도 안
        #   맞으면 겹침이 가장 큰 벌로 재서 위반이 드러나게 둔다.
        fit = [m for m in slot_orders if _hit(m) * 2 >= len(ids)]
        if not fit:
            return max(slot_orders, key=_hit)
        return min(fit, key=lambda m: (_rev(m), -_hit(m)))
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
        # 불변식: 최종 비트의 화면이 **그 후보가 받은 벌**의 세트 순서를 거스르지 않는다.
        order = _best_order_for(ids)
        gis = [order[x] for x in ids if x in order]
        rev = sum(1 for a, b in zip(gis, gis[1:]) if b < a)
        # 참고 지표: 세트 안에서 컷이 앞뒤로 바뀐 횟수(말맞춤의 의도된 대가)
        rev_in_set = 0
        prev_gi = prev_ix = None
        for x in ids:
            if x not in order:
                continue
            gi, ix = order[x], _seg_idx(x)
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
