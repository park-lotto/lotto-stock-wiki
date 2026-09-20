# 히트작 칸 템플릿(templatize_hits) → **스파인 DB**에 넣는다 (2026-09-20 사장님 "지금 스파인 만드는 걸로 하자").
# 별도 경로(transpose_hit)로 대본을 뽑으면 스파인의 말투 통제를 안 받아 반말·존댓말이 섞였다 — 그래서 스파인으로 합친다.
#
# 사용(서버):  python3 import_hits_to_spine.py tpl.json <유형> [--name "..."] [--apply]
#   --apply 없으면 화면에만 보여준다(미리보기). 넣을 때는 **status=pending** — 스파인 DB는 라이브가 즉시 읽는다.
# 칸 이름 맞추기: 내 칸(훅·계기…) → 스파인 칸(title·bait…). 말투는 플랫폼으로 가른다(유튜브=반말, 인스타=존댓말).
import json, re, sqlite3, sys

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
ROLE_MAP = {"훅": "title", "계기": "bait", "불편": "limit", "전환": "solve", "작동": "solve",
            "심지어": "more", "유래·권위": "fame", "사회증거": "fame", "감정": "land", "CTA": "cta"}
ORDER = ["title", "bait", "fame", "limit", "reveal", "solve", "more", "twist", "land", "cta"]


BAD = re.compile(r"[ㅋㅎㅠㅜ]{2,}|[🌀-🫿☀-➿]|https?://|@[A-Za-z]")
BRAND = re.compile(r"[A-Za-z]{3,}|다이소|코스트코|무인양품|이케아|쿠팡")


def ok_template(t, role):
    """찌꺼기 거르기 — 원문 그대로라도 남의 사연·이모지·브랜드가 박힌 틀은 다른 제품에 못 쓴다."""
    if not (6 <= len(t) <= 90):
        return False
    if BAD.search(t):
        return False
    if role != "title" and BRAND.search(t):
        return False
    if t.count("{") == 0:                      # 빈칸이 하나도 없으면 남의 제품 이야기일 확률이 높다
        return role in ("cta", "land")
    return True


def collect(tpl_path, platform=None, min_views=0):
    """{role: [문장틀...]} — 원문 검증을 통과한 칸만. 같은 틀은 한 번만."""
    out, seen = {}, set()
    for x in json.load(open(tpl_path, encoding="utf-8")):
        if platform and x.get("platform") != platform:
            continue
        if (x.get("views") or 0) < min_views:
            continue
        for c in x["cells"]:
            if c.get("why_bad") or not c.get("template"):
                continue
            r = ROLE_MAP.get(c["role"])
            t = " ".join(c["template"].split())
            if not r or t in seen or not ok_template(t, r):
                continue
            seen.add(t)
            out.setdefault(r, []).append(t)
    return out


def main():
    tpl, typ = sys.argv[1], sys.argv[2]
    a = sys.argv[3:]
    apply = "--apply" in a
    name = a[a.index("--name") + 1] if "--name" in a else None
    plat = a[a.index("--platform") + 1] if "--platform" in a else None
    tones = {"youtube": "반말", "instagram": "존댓말"}
    tone = tones.get(plat or "", "섞임")
    T = collect(tpl, platform=plat)
    roles = [r for r in ORDER if T.get(r)]
    nm = name or ("히트작 %s%s" % (typ, "(유튜브 반말)" if plat == "youtube" else "(인스타 존댓말)" if plat == "instagram" else ""))
    print("스파인:", nm, "| 말투", tone, "| 칸", len(roles))
    for r in roles:
        print("  %-6s %d개 — 예: %s" % (r, len(T[r]), T[r][0][:60]))
    if not apply:
        print("\n(미리보기만 — 넣으려면 --apply)")
        return
    con = sqlite3.connect(DB)
    cur = con.execute("select id from spine where name=?", (nm,))
    row = cur.fetchone()
    payload = dict(name=nm, beat_roles_json=json.dumps(roles, ensure_ascii=False),
                   templates_json=json.dumps(T, ensure_ascii=False),
                   fit_categories_json=json.dumps([typ], ensure_ascii=False),
                   voice_json=json.dumps({"tone": tone}, ensure_ascii=False),
                   hook_3s=1, no_cta=0 if T.get("cta") else 1, status="pending",
                   situation_type="히트작 원문에서 수확한 칸별 문장틀(2026-09-20)")
    if row:
        con.execute("update spine set %s, updated_at=datetime('now') where id=?" % ",".join("%s=?" % k for k in payload),
                    list(payload.values()) + [row[0]])
        sid = row[0]
    else:
        cols = ",".join(payload) + ",created_at,updated_at"
        con.execute("insert into spine (%s) values (%s)" % (cols, ",".join(["?"] * len(payload)) + ",datetime('now'),datetime('now')"),
                    list(payload.values()))
        sid = con.execute("select last_insert_rowid()").fetchone()[0]
    con.commit()
    print("저장됨 spine id=%d (status=pending)" % sid)


if __name__ == "__main__":
    main()
