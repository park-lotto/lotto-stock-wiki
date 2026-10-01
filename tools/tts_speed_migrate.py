"""저장된 성우 속도를 새 기본값(voice_presets.default_speed)으로 바꾼다 — 관제 049 (2026-10-01).

사장님 결정: "기존 고객 저장 속도도 전원 덮어쓰기" (미나 1.35 · 그 외 1.25).
대상: 고객 성우 기억(customers.last_voice_json · 사장님 cid 0 pref) + 작업별 성우(mix_jobs.voice_json).
★회원 데이터라 실행 전 사장님 승인. 기본은 미리보기(쓰지 않음), --apply 로만 쓴다.
--apply 는 옛 값을 JSON 으로 남긴다(되돌리기용).

    python3 tools/tts_speed_migrate.py --db shopping_shorts/data/reference.db            # 미리보기
    python3 tools/tts_speed_migrate.py --db shopping_shorts/data/reference.db --apply    # 실제 적용
"""
import argparse
import collections
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shopping_shorts.store import Store          # noqa: E402
from shopping_shorts import voice_presets        # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    store = Store(a.db)
    changes = store.rewrite_voice_speeds(voice_presets.default_speed, apply=False)
    cnt = collections.Counter((k, old, new) for k, _i, _v, old, new in changes)
    print(f"바뀔 행 {len(changes)}개 (고객 {sum(1 for c in changes if c[0]=='customer')} · "
          f"작업 {sum(1 for c in changes if c[0]=='job')} · 사장님 {sum(1 for c in changes if c[0]=='owner_pref')})")
    for (k, old, new), n in sorted(cnt.items(), key=lambda x: -x[1])[:20]:
        print(f"  {k:10s} {old} → {new} : {n}")
    if not a.apply:
        print("미리보기만 했다 — 쓰려면 --apply")
        return 0
    backup = os.path.join(os.path.dirname(os.path.abspath(a.db)),
                          f"tts_speed_migrate_backup_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump([list(c) for c in changes], f, ensure_ascii=False)
    done = store.rewrite_voice_speeds(voice_presets.default_speed, apply=True)
    left = store.rewrite_voice_speeds(voice_presets.default_speed, apply=False)
    print(f"적용 {len(done)}행 · 남은 불일치 {len(left)}행 · 옛 값 백업 {backup}")
    return 0 if not left else 1


if __name__ == "__main__":
    sys.exit(main())
