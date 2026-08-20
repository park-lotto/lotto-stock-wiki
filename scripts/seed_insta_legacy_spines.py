# -*- coding: utf-8 -*-
"""spine 52·53·54를 조립 규격으로 갱신한다 (2026-08-20).

정본은 `tools/script_lab/insta_legacy_spines.py`다 — 여기서 **읽어다** 넣는다.
문장을 이 파일에 다시 적지 마라(0순위-B).

## ★기존 행을 갱신한다 — 새 행을 만들지 않는다

같은 축이 두 행이 되면 어느 쪽이 맞는지 아무도 모른다. `spine_id`로 그 행을 직접 짚는다.

## 되돌리는 법

`out/spine_52_53_54_backup_20260820.json`에 바꾸기 전 상태가 그대로 있다.
    python scripts/seed_insta_legacy_spines.py --restore

실행:
    python scripts/seed_insta_legacy_spines.py            # 미리보기
    python scripts/seed_insta_legacy_spines.py --apply    # 실제 갱신
    python scripts/seed_insta_legacy_spines.py --restore  # 백업으로 되돌리기
"""
import io
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from shopping_shorts.app import DB_PATH, INSTA_CATEGORIES          # noqa: E402
from shopping_shorts.store import Store                            # noqa: E402
from shopping_shorts.spine_fill import SLOT_NAMES, slots_in, fill  # noqa: E402
from tools.script_lab.insta_legacy_spines import LEGACY_SPINES     # noqa: E402

BACKUP = BASE / "out" / "spine_52_53_54_backup_20260820.json"


def check(sp):
    """심기 전 검사 — 모르는 슬롯은 pick_template이 조용히 건너뛴다(spine_fill.py:312)."""
    bad = []
    for role, tpls in sp["templates"].items():
        for t in tpls:
            for n in slots_in(t):
                if n not in SLOT_NAMES:
                    bad.append("%s: 모르는 슬롯 {%s} — %s" % (role, n, t))
    for role in sp["beat_roles"]:
        if role not in sp["templates"]:
            bad.append("%s: 템플릿이 없다" % role)
        elif not any(not slots_in(t) for t in sp["templates"][role]):
            bad.append("%s: 슬롯 없는 폴백이 없다(재료 부족 시 칸이 빈다)" % role)
    # 조립 경로에 걸리는가 — 여기서 안 막으면 "심었는데 안 돈다"가 된다
    if not any(c in INSTA_CATEGORIES for c in sp["fit_categories"]):
        bad.append("fit_categories에 INSTA_CATEGORIES 이름이 없다 → 조립 경로 OFF "
                   "(app.INSTA_CATEGORIES=%s)" % (INSTA_CATEGORIES,))
    return bad


def restore(st):
    rows = json.loads(io.open(BACKUP, encoding="utf-8").read())
    for r in rows:
        st.set_spine_style(
            r["id"],
            beat_roles=json.loads(r["beat_roles_json"] or "[]"),
            templates=json.loads(r["templates_json"] or "{}"),
            chars_per_30s=r["chars_per_30s"],
            no_cta=r["no_cta"],
            fit_categories=json.loads(r["fit_categories_json"] or "[]"),
        )
        print("↩ spine %s (%s) 되돌림" % (r["id"], r["name"]))
    return 0


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    st = Store(DB_PATH)
    if "--restore" in sys.argv:
        return restore(st)

    apply = "--apply" in sys.argv
    existing = {s.get("id"): s for s in st.list_spines()}
    print("DB : %s" % DB_PATH)
    print("INSTA_CATEGORIES : %s\n" % (INSTA_CATEGORIES,))

    fail = False
    for sp in LEGACY_SPINES:
        sid = sp["spine_id"]
        old = existing.get(sid)
        bad = check(sp)
        print("[%s] %s" % (sid, sp["name"]))
        if old is None:
            print("   ✗ 그 행이 DB에 없다 — 건너뛴다")
            fail = True
            continue
        print("   칸   : %d개 → %d개  (%s)"
              % (len(old.get("beat_roles") or []), len(sp["beat_roles"]),
                 " → ".join(sp["beat_roles"])))
        print("   밀도 : %s → %d자/30초" % (old.get("chars_per_30s"), sp["chars_per_30s"]))
        print("   fit  : %s → %s" % (old.get("fit_categories"), sp["fit_categories"]))
        if bad:
            fail = True
            for b in bad:
                print("   ✗ %s" % b)
        else:
            # 슬롯 없이도 전 칸이 차는지(최악의 경우) 실제로 조립해 본다
            beats, missing = fill(sp, {})
            print("   ✓ 검사 통과 · 재료 0개로도 %d/%d칸 조립"
                  % (len(beats), len(sp["beat_roles"])))
            if missing:
                print("   ⚠ 재료 0개일 때 빈 칸: %s" % missing)

    if fail:
        print("\n✗ 검사에서 걸렸다. 고치기 전엔 안 심는다.")
        return 1
    if not apply:
        print("\n(미리보기다. 실제로 갱신하려면 --apply / 되돌리려면 --restore)")
        return 0

    for sp in LEGACY_SPINES:
        st.set_spine_style(
            sp["spine_id"],
            beat_roles=sp["beat_roles"],
            templates=sp["templates"],
            chars_per_30s=sp["chars_per_30s"],
            no_cta=sp["no_cta"],
            fit_categories=sp["fit_categories"],
        )
        print("✅ spine %s (%s) 갱신" % (sp["spine_id"], sp["name"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
