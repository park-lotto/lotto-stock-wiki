"""과적재 실측 — 비트당 클립 수 / 계획 길이 대 목표 / 비트당 메시지 수.

핸드오프 진단(2026-08-01): 전개 문장 하나에 칸막이+젖은용품+구멍걸이+33색+사은품 5종이
다 들어가고 클립이 9개(CTA도 7개)라 카탈로그 낭독이 된다. 계획 40.2초인데 목표는 30초라
26초로 압축돼 말이 뭉갠다.

여기서 재는 것:
  · 비트당 클립 수(primary + alternates) — config.MAX_CLIPS_PER_BEAT=3이 실제로 지켜지나
  · 계획 총 길이(나레이션 음절 기준 추정) 대 target_seconds
  · 비트당 나레이션 길이/문장 수 — '한 문장에 메시지 여러 개'의 대리 지표
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts import mix_pipeline                                  # noqa: E402
from shopping_shorts.edit_plan import build_scene_first_plan              # noqa: E402
from shopping_shorts import config                                        # noqa: E402

FIXTURE = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/fixture_live.json"
TARGET = 30
N_CANDIDATES = 3
_SYL = getattr(config, "SYLLABLES_PER_SEC", None)


def _live_args(store, source_scripts):
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
    store = Store(DB_PATH)
    args = _live_args(store, source_scripts)

    cap = getattr(config, "MAX_CLIPS_PER_BEAT", 3)
    print(f"소재: {os.path.basename(FIXTURE)} · 목표 {TARGET}초 · 클립상한(config) {cap}")

    sf = build_scene_first_plan(source_scripts, "", TARGET, n_candidates=N_CANDIDATES,
                                video_type=None, **args)
    cands = sf.get("candidates") or []
    if not cands:
        print("[x] 후보 0개 — 측정 불가(키 소진/폴백)")
        return 1

    from shopping_shorts.edit_plan import _SYLLABLES_PER_SEC
    worst = []
    for i, c in enumerate(cands):
        beats = (c["plan"].get("beats") or [])
        rows = []
        total_chars = 0
        for b in beats:
            n_clip = 1 + len(b.get("alternates") or [])
            narr = (b.get("narration") or "")
            total_chars += len(narr)
            # 문장 수 = 종결부호 기준(대리 지표)
            n_sent = max(1, sum(narr.count(x) for x in ".!?") or 1)
            rows.append((b.get("role", ""), n_clip, len(narr), n_sent))
        est = total_chars / _SYLLABLES_PER_SEC if _SYLLABLES_PER_SEC else 0
        over = [r for r in rows if r[1] > cap]
        print(f"\n[{i}]{'★' if c.get('recommended') else ' '} 비트 {len(beats)} · "
              f"추정길이 {est:.1f}초 (목표 {TARGET} · {'초과' if est > TARGET else 'OK'}) · "
              f"상한초과 비트 {len(over)}개")
        from shopping_shorts import backbone
        for b, (role, n_clip, n_ch, n_sent) in zip(beats, rows):
            mark = "  <- 상한초과" if n_clip > cap else ""
            have = backbone.clip_seconds(b)
            need = backbone.narration_seconds(b.get("narration") or "")
            # 상한(cap)까지만 남겼을 때의 화면 길이 — 프리즈 위험 판정용
            segs = [b.get("primary")] + list(b.get("alternates") or [])
            capped = round(sum((s.get("end",0)-s.get("start",0)) for s in segs[:cap] if s), 2)
            short = " ★부족" if capped < need else ""
            print(f"     [{role:<4}] 클립 {n_clip:>2} · {n_ch:>3}자 · 화면 {have:>5.1f}s / "
                  f"필요 {need:>4.1f}s · 상한적용시 {capped:>5.1f}s{short}{mark}")
        worst.append((len(over), est))

    max_over = max(w[0] for w in worst)
    max_est = max(w[1] for w in worst)
    print(f"\n=== 요약 ===")
    print(f"상한({cap}) 초과 비트가 있는 후보: {sum(1 for w in worst if w[0])}/{len(worst)}"
          f" · 최대 초과 비트 수 {max_over}")
    print(f"추정길이 목표({TARGET}초) 초과 후보: {sum(1 for w in worst if w[1] > TARGET)}"
          f"/{len(worst)} · 최대 {max_est:.1f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
