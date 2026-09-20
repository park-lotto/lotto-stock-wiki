# 히트작 한 편 = 스파인 한 개(원문형) — 2026-09-20 사장님 확정.
# 스파인이 담는 것: 히트작 원문(칸 표시) · 칸 순서 · 훅 고정 문구 · 말투 · 유형. 문장은 생성 때 원문을 보고 새로 쓴다.
# (빈칸 문장틀 조립은 문장이 깨져 폐기 — 실측 09-19~20)
#
# 사용(서버):  python3 import_origin_spines.py tpl.json <유형> [--top 5] [--apply]
import json, re, sqlite3, sys

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
TONE = {"youtube": "반말", "instagram": "존댓말"}
BAD = re.compile(r"[ㅋㅎㅠㅜ]{2,}|https?://")


# 뜻이 깨진 전사(자동 받아쓰기 오류) — 이런 원문을 틀로 쓰면 대본이 통째로 부실해진다(09-20 사장님 지적)
TYPO = re.compile(r"방람|재왕절|육가맘|우열하게|입차려|깊사|어던|불리기|수탁|바위를 터지|모국 넓|조물")
MIN_CELL = 10          # 칸 하나가 이보다 짧으면 조각(예: "방수도")
KINDS = {"훅", "계기", "불편", "전환", "작동", "심지어", "감정", "CTA", "유래·권위", "사회증거"}


def reject(x):
    """틀로 쓸 수 없는 이유(없으면 ""). 부실한 원문은 아무리 조회수가 높아도 스파인으로 안 쓴다."""
    cells = [c for c in x["cells"] if (c.get("original") or "").strip()]
    text = " ".join(c["original"] for c in cells)
    hook = next((c for c in cells if c["role"] == "훅" and not c.get("why_bad")), None)
    if hook is None:
        return "훅 틀 검증 실패"
    if BAD.search(text):
        return "이모지·링크"
    if len(text) < 150:
        return "원문 %d자(150 미만)" % len(text)
    if len(cells) < 6:
        return "칸 %d개(6 미만)" % len(cells)
    if len({c["role"] for c in cells} & KINDS) < 4:
        return "칸 종류 부족"
    short = [c["role"] for c in cells[:-1] if len(re.sub(r"\s", "", c["original"])) < MIN_CELL]
    if short:
        return "잘린 조각 칸 %s" % short
    n_typo = len(TYPO.findall(text))
    if n_typo >= 1:
        return "전사 오타 %d곳" % n_typo
    return ""


def usable(x):
    return not reject(x)


def main():
    tpl, typ = sys.argv[1], sys.argv[2]
    a = sys.argv[3:]
    top = int(a[a.index("--top") + 1]) if "--top" in a else 5
    apply = "--apply" in a
    ALL = sorted(json.load(open(tpl, encoding="utf-8")), key=lambda x: -x["views"])
    D = [x for x in ALL if usable(x)]
    print("틀 자격: %d/%d 통과" % (len(D), len(ALL)))
    for x in ALL[:top + 6]:
        if reject(x):
            print("   버림 %-9s %s… — %s" % (format(x["views"], ","), (x["text"] or "")[:26], reject(x)))
    con = sqlite3.connect(DB) if apply else None
    for x in D[:top]:
        cells = [c for c in x["cells"] if (c.get("original") or "").strip()]
        hook = next(c for c in cells if c["role"] == "훅" and not c.get("why_bad"))
        tone = TONE.get(x.get("platform") or "", "섞임")
        head = re.sub(r"\s+", " ", cells[0]["original"])[:16]
        name = "히트작 %s 「%s…」" % (typ, head)
        origin = {"cells": [{"role": c["role"], "text": c["original"]} for c in cells],
                  "views": x["views"], "user": x.get("user") or "", "hit_id": x["id"], "hook_tpl": hook["template"]}
        payload = dict(name=name,
                       beat_roles_json=json.dumps([c["role"] for c in cells], ensure_ascii=False),
                       templates_json=json.dumps({"_origin": origin, "title": [hook["template"]]}, ensure_ascii=False),
                       fit_categories_json=json.dumps([typ], ensure_ascii=False),
                       voice_json=json.dumps({"tone": tone}, ensure_ascii=False),
                       situation_type="원문형 — %s %s회 대본을 틀로(2026-09-20)" % (x.get("user") or "", x["views"]),
                       hook_3s=1, no_cta=0 if any(c["role"] == "CTA" for c in cells) else 1, status="pending")
        print("%s | %s | 칸 %d | %s회" % (name, tone, len(cells), format(x["views"], ",")))
        if not apply:
            continue
        row = con.execute("select id from spine where name=?", (name,)).fetchone()
        if row:
            con.execute("update spine set %s, updated_at=datetime('now') where id=?" % ",".join("%s=?" % k for k in payload),
                        list(payload.values()) + [row[0]])
            print("   갱신 id=%d" % row[0])
        else:
            con.execute("insert into spine (%s,created_at,updated_at) values (%s,datetime('now'),datetime('now'))"
                        % (",".join(payload), ",".join(["?"] * len(payload))), list(payload.values()))
            print("   새로 넣음 id=%d" % con.execute("select last_insert_rowid()").fetchone()[0])
    if con:
        con.commit()


if __name__ == "__main__":
    main()
