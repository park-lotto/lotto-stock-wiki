"""Task 7 최종 재실측 — 라이브 설정 그대로(2026-08-01).

라이브 실측값(서버 reference.db settings + 코드 기본값):
  ping_pong_enabled=1 · bank_enabled=1 · backbone_base_enabled=1 · frame_extract_enabled=0
  REWRITE_MIX=1(기본) · BLOCK_MIX=1(기본)   ← 서버 env에 두 키 없음 = 기본값이 라이브

실측 소재는 서버 script_extracts에서 받은 실제 태깅 2건(합 33세그) — 짧은 소재에서
안 드러났던 F1·F2 결함을 보려고 긴 것으로 골랐다.

검사(스펙 Task 7 Step 2):
  1) 화면 중복 없음 — primary seg_id 중복 0
  2) 화면이 원본 시간순인가 — 소스 안에서 시간순 역전 쌍 개수
  3) CTA가 마지막인가 / slot_source가 gemini인가(조용한 폴백 검출)
"""
import json
import os
import sys

os.environ.setdefault("REWRITE_MIX", "1")
os.environ.setdefault("BLOCK_MIX", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shopping_shorts.edit_plan import (  # noqa: E402
    build_scene_first_plan, _build_inventory, _build_source_sentence_sets)


def _seg_idx(seg_id):
    try:
        return int(str(seg_id).rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return -1

FIXTURE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fixture.json"
TARGET = 30


def main():
    with open(FIXTURE, encoding="utf-8") as f:
        raw = json.load(f)
    source_scripts = list(raw.values())
    print(f"소스 {len(source_scripts)}개 / 세그 합계 "
          f"{sum(len(s.get('segments') or []) for s in source_scripts)}")

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

    sf = build_scene_first_plan(
        source_scripts, "", TARGET,
        ping_pong=True,        # 라이브 ping_pong_enabled=1
        backbone_base=True,    # 라이브 backbone_base_enabled=1
        judge=True,            # bank_enabled=1 → 라이브에서 심사 켜짐
        is_recipe=False,
    )
    cands = sf.get("candidates") or []
    print(f"후보 {len(cands)}개")
    if not cands:
        print("❌ 후보 0개 — 폴백 경로")
        return 1

    bad = 0
    for i, c in enumerate(cands):
        plan = c["plan"]
        beats = plan.get("beats") or []
        ids = [(b.get("primary") or {}).get("seg_id") for b in beats]
        dup = len(ids) - len(set(ids))
        # 시간순 역전 — **세트 사이**만 본다.
        # 세트 안 순서는 말맞춤(_order_clips_by_words, 2026-07-31)이 일부러 바꾼다
        # ("말에 맞는 컷을 비트 안에서 앞으로") — 그걸 역전으로 세면 의도된 설계를
        # 버그로 오판한다(2026-08-01 1차 실측에서 실제로 그렇게 셌다).
        rev = rev_in_set = 0
        seen = {}
        for sid in ids:
            st = set_of.get(sid)
            if st is None:
                continue
            src, idx = st
            if src in seen:
                prev_set, prev_idx = seen[src]
                if idx < prev_set:
                    rev += 1
                elif idx == prev_set and _seg_idx(sid) < prev_idx:
                    rev_in_set += 1
            seen[src] = (idx, _seg_idx(sid))
        cta_last = "cta" in str(beats[-1].get("role", "")).lower() if beats else False
        slot = plan.get("slot_source")
        srcs = len({set_of[x][0] for x in ids if x in set_of})
        ok = (dup == 0 and rev == 0 and cta_last and slot == "gemini"
              and srcs == len(source_scripts))
        bad += 0 if ok else 1
        print(f"\n[{i}] 비트 {len(beats)} · 중복 {dup} · 세트간역전 {rev} · "
              f"소스 {srcs}/{len(source_scripts)} · "
              f"CTA끝 {cta_last} · slot_source={slot} · 세트내재배치 {rev_in_set}(말맞춤)"
              f" → {'OK' if ok else 'NG'}")
        for b in beats:
            print(f"   {(b.get('primary') or {}).get('seg_id'):<16} "
                  f"[{b.get('role','')}] fit={b.get('fit')} "
                  f"{(b.get('narration') or '')[:44]}")
    print(f"\n=== 후보 {len(cands)}개 중 NG {bad}개 ===")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
