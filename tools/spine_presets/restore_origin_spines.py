# 원문형 스파인 덤프 → DB에 넣기/되돌리기 (2026-09-20 사장님 "원문형 스파인도 집에서 받게").
# 서버 DB가 정본이지만, 집·다른 PC에서 그대로 쓰려면 이 덤프를 넣으면 된다. 이름이 같으면 갱신, 없으면 새로 넣는다.
#
# 사용:  python3 restore_origin_spines.py curated/origin_spines_2026-09-20.json [--db <경로>] [--apply]
#   --apply 없으면 몇 개가 새로 들어가고 몇 개가 갱신되는지만 보여준다(미리보기).
import json, os, sqlite3, sys

DEFAULT_DB = os.environ.get("SS_DB", "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
COLS = ["name", "situation_type", "beat_chain_json", "fit_categories_json", "beat_roles_json",
        "templates_json", "voice_json", "no_cta", "hook_3s", "hook_conceal", "status", "appeal", "emotion_arc"]


def main():
    src = sys.argv[1]
    db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else DEFAULT_DB
    apply = "--apply" in sys.argv
    rows = json.load(open(src, encoding="utf-8"))
    con = sqlite3.connect(db)
    new = upd = 0
    for r in rows:
        vals = [r.get(c) for c in COLS]
        got = con.execute("select id from spine where name=?", (r["name"],)).fetchone()
        if got:
            upd += 1
            if apply:
                con.execute("update spine set %s, updated_at=datetime('now') where id=?"
                            % ",".join("%s=?" % c for c in COLS), vals + [got[0]])
        else:
            new += 1
            if apply:
                con.execute("insert into spine (%s,created_at,updated_at) values (%s,datetime('now'),datetime('now'))"
                            % (",".join(COLS), ",".join(["?"] * len(COLS))), vals)
    if apply:
        con.commit()
    print("덤프 %d개 · 새로 넣음 %d · 갱신 %d %s" % (len(rows), new, upd, "" if apply else "(미리보기 — 넣으려면 --apply)"))


if __name__ == "__main__":
    main()
