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
from shopping_shorts.edit_plan import build_scene_first_plan  # noqa: E402

FIXTURE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fixture.json"
TARGET = 30


def main():
    with open(FIXTURE, encoding="utf-8") as f:
        raw = json.load(f)
    source_scripts = list(raw.values())
    print(f"소스 {len(source_scripts)}개 / 세그 합계 "
          f"{sum(len(s.get('segments') or []) for s in source_scripts)}")

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
        # 소스 안에서의 시간순 역전
        rev = 0
        seen = {}
        for sid in ids:
            if not sid or "-" not in str(sid):
                continue
            src, _, idx = str(sid).rpartition("-")
            try:
                idx = int(idx)
            except ValueError:
                continue
            if src in seen and idx < seen[src]:
                rev += 1
            seen[src] = idx
        cta_last = "cta" in str(beats[-1].get("role", "")).lower() if beats else False
        slot = plan.get("slot_source")
        ok = (dup == 0 and rev == 0 and cta_last and slot == "gemini")
        bad += 0 if ok else 1
        print(f"\n[{i}] 비트 {len(beats)} · 중복 {dup} · 순서역전 {rev} · "
              f"CTA끝 {cta_last} · slot_source={slot} → {'OK' if ok else 'NG'}")
        for b in beats:
            print(f"   {(b.get('primary') or {}).get('seg_id'):<16} "
                  f"[{b.get('role','')}] fit={b.get('fit')} "
                  f"{(b.get('narration') or '')[:44]}")
    print(f"\n=== 후보 {len(cands)}개 중 NG {bad}개 ===")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
