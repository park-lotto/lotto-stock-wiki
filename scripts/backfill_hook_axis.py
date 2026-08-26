# -*- coding: utf-8 -*-
"""이미 저장된 전사에 **훅 문형 축**을 채운다 (2026-08-20).

## 왜 필요한가

`store.save_script`가 2026-08-20부터 축을 같이 저장하지만, 그 전에 들어온 전사
600여 편은 `hook_axis`가 비어 있다. 화면이 담기 단계에서 축을 보여주려면 채워야 한다.

## 언제 다시 돌리나

**축 판정 규칙(`shopping_shorts/hook_axis.py`의 AXES)을 고칠 때마다** 다시 돌려라.
안 돌리면 DB에 옛 규칙으로 판정한 값이 남아 라이브 선택과 화면이 어긋난다(0순위-B).

실행:
    python scripts/backfill_hook_axis.py            # 무엇이 바뀌는지만 보여준다
    python scripts/backfill_hook_axis.py --apply    # 실제로 채운다
"""
import io
import json
import sys
import collections
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from shopping_shorts.app import DB_PATH               # noqa: E402
from shopping_shorts.store import Store               # noqa: E402
from shopping_shorts import hook_axis as hx           # noqa: E402


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    apply = "--apply" in sys.argv
    st = Store(DB_PATH)          # 스키마 마이그레이션(hook_axis 컬럼)이 여기서 돈다

    rows = []
    with st._conn() as c:
        for r in c.execute("SELECT shortcode, script_json, hook_axis FROM script_extracts"):
            rows.append((r[0], r[1], r[2]))

    changed, same, cnt = [], 0, collections.Counter()
    for sc, raw, old in rows:
        try:
            script = json.loads(raw or "{}")
        except Exception:      # noqa: BLE001 — 깨진 행 하나가 전체를 막지 않는다
            continue
        new = hx.axis_of(script) or None
        cnt[new or "(미분류)"] += 1
        if (old or None) == new:
            same += 1
        else:
            changed.append((sc, old, new))

    print("전사 %d편 · 이미 맞는 것 %d · 바뀔 것 %d" % (len(rows), same, len(changed)))
    print("판정 분포:")
    for k, v in cnt.most_common():
        spine = hx.AXIS_TO_SPINE.get(k, "")
        print("   %-10s %4d편  → %s" % (k, v, spine or "(스파인 매핑 없음 — 폴백)"))
    mapped = sum(v for k, v in cnt.items() if k in hx.AXIS_TO_SPINE)
    print("스파인이 정해지는 편수: %d / %d (%d%%)"
          % (mapped, len(rows), mapped * 100 // max(1, len(rows))))

    if not apply:
        print("\n(미리보기다. 실제로 채우려면 --apply)")
        return 0

    with st._conn() as c:
        for sc, _old, new in changed:
            c.execute("UPDATE script_extracts SET hook_axis=? WHERE shortcode=?", (new, sc))
    print("\n✅ %d편 갱신" % len(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
