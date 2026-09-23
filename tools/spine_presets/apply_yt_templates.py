# -*- coding: utf-8 -*-
"""썰 히트작 제목 분석으로 다시 쓴 유튜브 스파인 문장틀을 DB에 적용한다 (2026-09-23 사장님 "샘플이 너무 단순").
  python3 tools/spine_presets/apply_yt_templates.py [--db 경로] [--dry]
틀 원본: tools/spine_presets/yt_templates_2026-09-23.json ( "_base"는 공용 블록을 깔고 그 위에 덮는다 ).
★스파인 DB 편집은 라이브 즉시 반영이다(메모리 reference_스파인DB편집은_라이브즉시반영) — --dry로 먼저 본다.
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("LSW_ROOT") or os.path.abspath(os.path.join(HERE, "..", "..")))


def expand(spec, sid):
    d = spec["spines"][sid]
    out = dict(spec.get(d.get("_base") or "", {}) or {})
    out.update({k: v for k, v in d.items() if not k.startswith("_")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    ap.add_argument("--spec", default=os.path.join(HERE, "yt_templates_2026-09-23.json"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    from shopping_shorts.store import Store
    st = Store(a.db)
    have = {s["id"]: s for s in st.list_spines()}
    for sid in spec["spines"]:
        sp = have.get(int(sid))
        if not sp:
            print("없는 스파인", sid); continue
        roles = sp.get("beat_roles") or []
        tp = expand(spec, sid)
        missing = [r for r in roles if r not in tp]
        extra = [k for k in tp if k not in roles]
        print("%s %-26s 칸 %d · 빈 칸 %s · 역할 밖 %s" % (sid, (sp.get("name") or "")[:26], len(tp), missing or "-", extra or "-"))
        if not a.dry:
            st.set_spine_style(int(sid), templates=tp)
    print("dry-run" if a.dry else "적용 완료", len(spec["spines"]), "개")


if __name__ == "__main__":
    main()
