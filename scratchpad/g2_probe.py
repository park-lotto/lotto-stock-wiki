"""G2 전제 실측 — 백본 화면 후처리 5종(12~16단계)이 정말 버려지는가.

주장(코드 읽기): `_assign_timeline`(2620, 2회차)이 `b["primary"]`와 `b["alternates"]`를
통째로 덮어쓰므로, 그 앞의 order_by_backbone·dedup_and_balance·ensure_sources_used·
dedup_clips_global·swap_hook_cta_for_differentiation이 화면에 한 일은 전부 소멸한다.

★모델을 두 번 부르지 않는다. Gemini는 비결정적이라 "스킵 전/후"를 각각 돌려 비교하면
  모델 노이즈와 코드 효과가 섞인다. 대신 **한 번 도는 동안** 각 후처리의 입출력을
  가로채, 마지막 `_assign_timeline` 결과와 대조한다 — 노이즈 0.

검사:
  A) 5종이 화면(primary seg_id)을 실제로 바꾸는가        → 바꾼다면 '일은 하고 있다'
  B) 그 변경이 최종 결과에 남아 있는가                    → 안 남으면 '버려진다'(주장 확인)
  C) screen_pinned(CTA) 비트만 예외로 살아남는가          → 조사의 (b)4 상충 확인
"""
import json
import os
import sys

# 윈도우 cp949 콘솔에서 이모지·한글이 죽는다(tag_audit.py가 같은 데 걸렸다).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts import mix_pipeline                                  # noqa: E402
from shopping_shorts.edit_plan import build_scene_first_plan              # noqa: E402

FIXTURE = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/fixture_live.json"
TARGET = 30
N_CANDIDATES = 3


def _screens(beats):
    """비트별 (primary seg_id, alternates seg_id들, 핀 여부) — 화면 상태의 지문."""
    out = []
    for b in beats or []:
        out.append((
            (b.get("primary") or {}).get("seg_id"),
            tuple((a or {}).get("seg_id") for a in (b.get("alternates") or [])),
            bool(b.get("screen_pinned")),
        ))
    return out


def _live_args(store, source_scripts):
    """live_recheck.py와 같은 방식 — 설정을 손으로 쓰지 않는다."""
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


# 감시 대상 = 조사가 지목한 12~16단계 (11번 ping_pong_reconcile은 나레이션도 만지므로 별도)
_WATCH = ["order_by_backbone", "dedup_and_balance", "ensure_sources_used",
          "dedup_clips_global", "swap_hook_cta_for_differentiation"]


def main():
    with open(FIXTURE, encoding="utf-8") as f:
        raw = json.load(f)
    source_scripts = list(raw.values())

    from shopping_shorts.store import Store
    from shopping_shorts.config import DB_PATH
    store = Store(DB_PATH)
    args = _live_args(store, source_scripts)
    print(f"소재: {os.path.basename(FIXTURE)} · 소스 {len(source_scripts)}개")
    print(f"라이브 인자: ping_pong={args['ping_pong']} · backbone_base={args['backbone_base']} "
          f"· bank_context {len(args['bank_context'])}자")
    if not args["ping_pong"]:
        print("⚠️ ping_pong=False — 12~16단계가 애초에 안 돈다. 이 소재로는 측정 불가.")
        return 2

    import shopping_shorts.backbone as _bb
    import shopping_shorts.edit_plan as _ep

    # 후보별 기록: [{stage: (before, after)}, ...]
    log = []
    cur = {}
    _originals = {n: getattr(_bb, n) for n in _WATCH}

    def _wrap(name):
        orig = _originals[name]

        def w(beats, *a, **k):
            before = _screens(beats)
            # 12~16에 들어가기 직전 상태를 통째로 보존(반사실 대조용).
            if "pre_backbone_beats" not in cur:
                import copy
                cur["pre_backbone_beats"] = copy.deepcopy(beats)
            out = orig(beats, *a, **k)
            after = _screens(out)
            if before != after:
                cur.setdefault("changed", []).append(name)
            cur.setdefault("stages", {})[name] = (before, after)
            print(f"    · {name}: {'화면 변경' if before != after else '변경 없음'}")
            return out
        return w

    for n in _WATCH:
        setattr(_bb, n, _wrap(n))

    # _assign_timeline 2회차 = 후보 하나의 끝. 그 직전/직후를 잡고 기록을 닫는다.
    orig_at = _ep._assign_timeline
    seen = {"n": 0}

    def at_spy(beats, groups):
        seen["n"] += 1
        before = _screens(beats)
        out = orig_at(beats, groups)
        after = _screens(out)
        # 1회차(2563)는 backbone 이전이라 무시. 2회차(2620)만 기록.
        if cur.get("stages"):
            cur["at_before"] = before
            cur["at_after"] = after
            # ★반사실 대조(counterfactual): 12~16을 **안 탄** 비트에 같은
            #   _assign_timeline을 걸면 결과가 같은가? 이게 진짜 '스킵해도 동일한가'다.
            #   at_before와 at_after만 비교하면, _assign_timeline이 우연히 backbone과
            #   같은 seg를 고른 경우를 '살아남았다'로 오판한다(실제로는 덮어쓴 것).
            import copy
            pre = cur.get("pre_backbone_beats")
            if pre is not None:
                try:
                    cf = orig_at(copy.deepcopy(pre), groups)
                    cur["cf_after"] = _screens(cf)
                except Exception as e:      # noqa: BLE001
                    cur["cf_err"] = repr(e)[:120]
            log.append(dict(cur))
            cur.clear()
        return out

    _ep._assign_timeline = at_spy
    try:
        build_scene_first_plan(source_scripts, "", TARGET, n_candidates=N_CANDIDATES,
                               video_type=None, **args)
    finally:
        _ep._assign_timeline = orig_at
        for n, fn in _originals.items():
            setattr(_bb, n, fn)

    if not log:
        print("[x] 12~16단계 기록 0건 — 경로를 안 탔다.")
        print(f"    _assign_timeline 호출 {seen['n']}회 / 미완 기록 cur={list(cur.keys())}")
        print(f"    감시 단계 호출 여부: "
              f"{ {n: (n in (cur.get('stages') or {})) for n in _WATCH} }")
        return 1

    print(f"\n_assign_timeline 총 호출 {seen['n']}회 · 후보 기록 {len(log)}건\n")

    verdict_all = []
    for i, rec in enumerate(log):
        changed = rec.get("changed") or []
        # 12~16이 만든 최종 화면 상태 = _assign_timeline 직전(at_before)
        at_before, at_after = rec["at_before"], rec["at_after"]
        # 12~16 시작 시점 = 첫 감시 단계의 before
        first = next((rec["stages"][n][0] for n in _WATCH if n in rec["stages"]), None)

        # (A) 5종이 화면을 바꿨나
        a_changed = (first != at_before) if first is not None else False
        # (B) ★반사실 대조 — 12~16을 스킵했다면 최종 화면이 달랐을까?
        #     cf_after(스킵했을 때) vs at_after(실제) 비교가 유일하게 옳은 판정이다.
        cf = rec.get("cf_after")
        survived = []
        if cf is not None:
            for idx, aa in enumerate(at_after):
                ca = cf[idx] if idx < len(cf) else None
                if ca is None or ca[0] != aa[0]:
                    survived.append((idx, (ca[0] if ca else "(없음)"), aa[0], aa[2]))
        pinned_only = all(s[3] for s in survived)

        print(f"[후보 {i}] 동작한 단계: {', '.join(changed) if changed else '(화면 변경 없음)'}")
        print(f"  (A) 12~16이 화면을 바꿨나 : {'예' if a_changed else '아니오'}")
        if rec.get("cf_err"):
            print(f"  (B) 반사실 대조 실패: {rec['cf_err']}")
        elif cf is None:
            print("  (B) 반사실 대조 없음(pre 상태 미포착)")
        else:
            print(f"  (B) 스킵 시 달라지는 화면 : {len(survived)}건"
                  f"{' — 전부 screen_pinned(CTA)' if survived and pinned_only else ''}")
        for idx, was, now, pin in survived:
            print(f"       비트{idx}: 스킵하면 {was} / 실제 {now}"
                  f"{' [핀]' if pin else ' [★핀 아님]'}")
        verdict_all.append((a_changed, len(survived), pinned_only))

    worked = sum(1 for a, _, _ in verdict_all if a)
    leaked = sum(n for _, n, _ in verdict_all)
    unpinned_leak = sum(1 for a, n, p in verdict_all if n and not p)

    print(f"\n=== 판정 (반사실 대조 기준) ===")
    print(f"12~16이 화면을 바꾼 후보 : {worked}/{len(log)}")
    print(f"스킵 시 달라지는 화면    : {leaked}건 (핀 아닌 것 {unpinned_leak}건)")
    if worked and leaked == 0:
        print("→ [OK] 주장 확인: 5종은 일하지만 최종 화면은 스킵해도 완전히 동일하다.")
    elif worked and unpinned_leak == 0:
        print("→ [OK] 조건부 확인: 달라지는 건 screen_pinned(CTA)뿐 — 조사 (b)4와 일치.")
    elif not worked:
        print("→ [?] 5종이 이 소재에선 화면을 안 바꿨다 — 다른 소재로 재측정 필요.")
    else:
        print("→ [NG] 주장 반증: 스킵하면 핀 아닌 화면도 달라진다. 동작이 바뀐다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
