# 스토리보드 전수 검사(2026-10-04 사장님 "내가 하나씩 만들어보면서 하기보다 전체적으로 확인 — 대본 문제있는 거"):
#   작업 × (스타일 묶음 전부 + AI 자동)을 실제 3.6으로 만들고(storyboard_trial._board 그대로) 두 가지로 잰다.
#   ① 코드 검사: 칸 수·빈 칸·장면 모자람·장면 겹침·없는 번호·문장 길이·{} 남음·같은 접속어 연달아·검수가 지운 제품 사실 수
#   ② 스타일 충실도(3.6 판정 1번): 그 스타일의 상황·인물·흐름 글대로 썼나(가족갈등이면 가족 인물·갈등이 나오나) 1~5점 + 문제
# 서버에서: python3 /tmp/audit_boards.py <job> [<job> ...]   → /tmp/sb_audit.json + 표
import io, json, os, re, sqlite3, sys, time, contextlib
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.getcwd())
DB = "shopping_shorts/data/reference.db"
from shopping_shorts import storyboard as T   # 판단은 라이브 모듈 한 곳(관제 120)
sg, narr_secs = T.sg, T.narr_secs

S_JUDGE = {"type": "object", "properties": {"score": {"type": "integer"}, "story_ok": {"type": "boolean"},
                                            "problems": {"type": "array", "items": {"type": "string"}}}, "required": ["score", "problems"]}
P_JUDGE = """너는 쇼핑 쇼츠 대본 스타일 감수자다. 아래 대본이 [스타일]대로 쓰였는지 판정하라.
[스타일] %s
- 상황: %s
- 등장인물: %s
- 감정 흐름: %s
- 칸 흐름: %s
- 첫 줄 틀 예: %s
[대본] (칸 | 문장)
%s
판정: score 1~5(5 = 이 스타일 그대로, 3 = 흐름은 맞는데 스타일 색이 약함, 1 = 다른 스타일). story_ok = 등장인물·상황·감정 흐름이 살아 있나.
problems: 구체적으로(몇 번 칸이 무엇이 어긋났나). 어색한 문장·끊기는 이음·역할 못 하는 칸도 적어라. 없으면 빈 배열. JSON만."""
CONJ = ("심지어", "게다가", "근데", "그래서", "알고 보니", "덕분에")


def code_check(bd, segs, roles, creative):
    sl = bd.get("slots") or []
    pr = []
    if not creative and len(sl) != len(roles):
        pr.append("칸 수 %d (스타일 %d)" % (len(sl), len(roles)))
    seen = {}
    for i, x in enumerate(sl, 1):
        line, ids = (x.get("line") or "").strip(), x.get("ids") or []
        if not line:
            pr.append("%d칸 빈 문장" % i)
        if len(line) > 50:
            pr.append("%d칸 문장 %d자" % (i, len(line)))
        if "{" in line or "[" in line:
            pr.append("%d칸 틀 글자 남음" % i)
        if not ids:
            pr.append("%d칸 장면 없음" % i)
        bad = [c for c in ids if c not in segs]
        if bad:
            pr.append("%d칸 없는 번호 %s" % (i, bad))
        for c in ids:
            if c in seen:
                pr.append("%d칸 장면 겹침(%d칸과)" % (i, seen[c]))
            seen.setdefault(c, i)
        have, need = sum(segs.get(c, 0) for c in ids), narr_secs(line)
        if have * 1.2 < need - 0.2:
            pr.append("%d칸 장면 모자람 %.1f/%.1f초" % (i, have, need))
    for i in range(1, len(sl)):
        a, b = (sl[i - 1].get("line") or ""), (sl[i].get("line") or "")
        for c in CONJ:
            if a.startswith(c) and b.startswith(c):
                pr.append("%d·%d칸 '%s' 연달아" % (i, i + 1, c))
    if len(bd.get("fixed") or []) >= 3:
        pr.append("검수가 %d칸 고침(지어낸 사실 많음)" % len(bd["fixed"]))
    return pr


def run_job(jid, db, fams, spines):
    R = json.load(open("/tmp/sbtrial_%s.json" % jid))
    r1 = R["inventory"]
    ex = json.loads(db.execute("select extract_json from mix_jobs where job_id=?", (jid,)).fetchone()[0])
    segs, texts = {}, {}
    for vid, e in ex.items():
        for s in (e or {}).get("segments") or []:
            a, b = float(s.get("start") or 0), float(s.get("end") or 0)
            if b - a < 0.6 or (s.get("is_outro") and not s.get("product_benefits")):
                continue
            segs[s["seg_id"]] = round(b - a, 1)
            texts[s["seg_id"]] = "%s %s" % (s.get("scene_desc") or "", s.get("use_point") or "")
    tag_of = r1.get("tag_of") or {}
    groups_txt = "\n".join("  %s: %s" % (g["name"], ", ".join("%s(%.1f초%s)" % (c, segs.get(c, 0), ("·" + "/".join(tag_of[c])) if tag_of.get(c) else "")
                                                              for c in g["ids"])) for g in r1["groups"])
    pan_of = {str(s.get("family")): s.get("pan") for s in R.get("styles") or []}
    from shopping_shorts.store import Store
    from shopping_shorts import bank_assemble as _bk
    creative = _bk.parts_block(Store(DB))
    top = next((f for n, f, _ in fams if R.get("styles") and n == R["styles"][0].get("family")), fams[0][1])
    work = [("auto", top, True)] + [(str(n), f, False) for n, f, _ in fams]

    def one(w):
        k, fam, cr = w
        t0 = time.time()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                bd = T._board(fam, "" if cr else (pan_of.get(k) or ""), r1, groups_txt, [], segs, texts, creative=creative if cr else None)
        except Exception as e:      # 조용히 넘기지 않는다 — 실패도 결과에 남긴다
            return {"key": k, "name": "AI 자동" if cr else fam["names"][0], "error": repr(e)[:200]}
        secs = round(time.time() - t0)
        roles = list(fam["roles"])
        pr = code_check(bd, segs, roles, cr)
        sp = spines.get(int(fam["ids"][0])) or {}
        lines = "\n".join("%d %s | %s" % (i + 1, x.get("slot"), x.get("line")) for i, x in enumerate(bd.get("slots") or []))
        j = {} if cr else (sg._call_json(P_JUDGE % (", ".join(fam["names"]), sp.get("situation_type") or "", sp.get("character_roles_json") or "",
                                                    sp.get("emotion_arc") or "", " → ".join(fam["chain"]),
                                                    " / ".join((fam["tpl"].get((roles or ["hook"])[0]) or [])[:4]), lines), S_JUDGE, vertex=True) or {})
        return {"key": k, "name": "AI 자동" if cr else fam["names"][0], "secs": secs, "n": len(bd.get("slots") or []), "roles": len(roles),
                "code": pr, "score": j.get("score"), "story_ok": j.get("story_ok"), "judge": j.get("problems") or [],
                "lines": [(x.get("slot"), x.get("line"), x.get("ids")) for x in bd.get("slots") or []], "fixed": bd.get("fixed") or []}

    with ThreadPoolExecutor(6) as ex_:
        return list(ex_.map(one, work))


if __name__ == "__main__":
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    fams = T._families(db)
    cols = [c[1] for c in db.execute("pragma table_info(spine)")]
    spines = {int(r[0]): dict(zip(cols, r)) for r in db.execute("select * from spine where status='approved'")}
    out = {}
    for jid in sys.argv[1:]:
        out[jid] = run_job(jid, db, fams, spines)
    json.dump(out, open("/tmp/sb_audit.json", "w"), ensure_ascii=False)
    for jid, rows in out.items():
        print("\n== %s" % jid)
        for r in rows:
            if r.get("error"):
                print("  %-28s 실패 %s" % (r["name"][:26], r["error"])); continue
            print("  %-28s %2d칸 %3s초 스타일점수 %s 코드문제 %d 감수문제 %d" % (r["name"][:26], r["n"], r["secs"], r.get("score"), len(r["code"]), len(r["judge"])))
