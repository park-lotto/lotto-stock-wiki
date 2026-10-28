# -*- coding: utf-8 -*-
"""스파인에서 문장틀을 뺀다 — 백업을 먼저 남기고, 칸마다 최소 3개는 남긴다(2026-09-18).

  서버: cd /tmp/ab && python3 tools/spine_presets/drop_templates.py drop.json [--apply]
  drop.json = {"69": {"howto": ["버튼만 눌러주면 {효능2}보러", ...]}}
  ★스파인 DB는 라이브가 즉시 읽는다 — 칸 이름은 안 바꾼다. 백업은 /tmp/spine_backup_drop_<초까지>.json
"""
import io, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
MIN_PER_ROLE = 3


def main():
    want = json.load(io.open(sys.argv[1], encoding="utf-8")); apply = "--apply" in sys.argv
    from shopping_shorts.store import Store
    st = Store(DB)
    sps = {s["id"]: s for s in st.list_spines(status="approved")}
    if apply:
        bk = "/tmp/spine_backup_drop_%s.json" % time.strftime("%m%d_%H%M%S")
        json.dump({i: {"beat_roles": sps[int(i)].get("beat_roles"), "templates": sps[int(i)].get("templates")} for i in want},
                  open(bk, "w"), ensure_ascii=False)
        print("백업", bk)
    for sid, roles in want.items():
        tpl = {k: list(v) for k, v in (sps[int(sid)].get("templates") or {}).items()}
        for r, bad in roles.items():
            keep = [t for t in tpl.get(r) or [] if t not in bad]
            gone = len(tpl.get(r) or []) - len(keep)
            if len(keep) < MIN_PER_ROLE:
                print(f"[{sid}] {r} 빼면 {len(keep)}개 — 건너뜀"); continue
            tpl[r] = keep
            print(f"[{sid}] {r} -{gone} → {len(keep)}개")
        if apply:
            st.set_spine_style(int(sid), templates=tpl)
    print("APPLIED" if apply else "(미적용 — --apply로 반영)")


if __name__ == "__main__":
    main()
