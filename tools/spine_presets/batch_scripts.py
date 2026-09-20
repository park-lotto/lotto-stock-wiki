# 새 방식(백본 조립기) 대본만 여러 job × 여러 스타일로 뽑아 센다 — 렌더 없음.
# (2026-09-18 사장님 "대본 1개만 나오고 헛소리 나오던 거 해결되나 / 테스트 계속 돌려")
#
# 사용(서버):  python3 batch_scripts.py [job_id ...]      인자 없으면 최근 job 12개 + 문제 job 3개
# 잰다:  대본 나옴 여부 · 줄 수 · 걸린 초 · 근거 없는 수치(재료에 없는 숫자) · 재료에 없는 나라 · 슬롯 새어나옴
import sys, re, time, json, sqlite3
sys.path.insert(0, "/tmp/ab")
from shopping_shorts.store import Store
from shopping_shorts import backbone_assemble as ba

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
PROBLEM = ["68dc7e13dc23", "26698eb0a362", "b6e3a1a86122"]   # 볼펜(1안) · 팬케이크(무관 장면) · 얼음정수기(0안 502)
STYLES = ["제품정체형", "발명품형", "오용형"]
NUM = re.compile(r"[0-9]+(?:[.,][0-9]+)? ?(?:만|천|억|%|명|개|배|년|달|주|원|초|분)?|수천억|수백억|수백만|수천만")
# ★과장 표현(떼돈·바이럴·품절·돈방석 등)은 스타일이다 — 세지 않는다(2026-09-18 사장님 "많이 써도 된다, 더 후킹 강한 것도 가능").
#   구체적인 가짜 사실(매출·구매자 수·숫자)만 잡는다. 숫자는 NUM이 따로 잡는다.
CLAIM = re.compile(r"매출|구매하")
COUNTRY = re.compile(r"프랑스|독일|일본|미국|중국|영국|이탈리아|스웨덴|스위스|캐나다|호주|대만|베트남|태국|러시아|스페인|네덜란드|덴마크|핀란드|노르웨이")


def recent(n):
    con = sqlite3.connect(DB)
    rows = con.execute("select job_id from mix_jobs where length(extract_json)>2000 and job_id not like 'bb%' and job_id not like 'old%' order by created_at desc limit ?", (n,)).fetchall()
    return [r[0] for r in rows]


def check(st, jid):
    job = st.get_mix_job(jid)
    if not job:
        return [{"job": jid, "style": "-", "ok": False, "why": "제작 job 없음(건너뜀)", "skip": True}]
    srcs = ba.sources_from_extract(job.get("extract") or {})
    if not srcs:
        return [{"job": jid, "style": "-", "ok": False, "why": "재료 없음"}]
    src_text = " ".join((s.get("full_text") or "") + " " + " ".join(
        (g.get("scene_desc") or "") + (g.get("text") or "") for g in (s.get("segments") or [])) for s in srcs)
    ko = lambda t: sum(1 for c in t if "가" <= c <= "힣") / max(1, sum(1 for c in t if c.isalpha()))
    kor = [s for s in srcs if ko(s.get("full_text") or "") > 0.7]
    bb = max(kor or srcs, key=lambda s: len((s.get("full_text") or "").strip()))
    out = []
    for style in STYLES:
        note, t0 = {}, time.time()
        try:
            given, bs, meta = ba.assemble(srcs, bb["video_id"], st, style=style, seed="batch" + jid + style, note=note)
        except Exception as e:
            given, meta, note = None, {}, {"error": repr(e)[:200]}
        sec = round(time.time() - t0, 1)
        if not given:
            out.append({"job": jid, "style": style, "ok": False, "sec": sec, "why": json.dumps(note, ensure_ascii=False)[:200]})
            continue
        lines = [l for l in given.split("\n") if l.strip()]
        nums = [m.group(0) for l in lines for m in NUM.finditer(l) if m.group(0).strip() and m.group(0).split()[0] not in src_text]
        ctry = [m.group(0) for l in lines for m in COUNTRY.finditer(l) if m.group(0) not in src_text]
        leak = [l for l in lines if "{" in l or "}" in l]
        claim = [m.group(0) for l in lines for m in CLAIM.finditer(l) if m.group(0) not in src_text]
        out.append({"job": jid, "style": style, "ok": True, "sec": sec, "spine": (meta.get("spine") or {}).get("name"),
                    "n": len(lines), "fake_num": nums, "country": ctry, "claim": claim, "leak": len(leak), "lines": lines})
    return out


if __name__ == "__main__":
    st = Store(DB)
    jobs = [a for a in sys.argv[1:]] or (PROBLEM + [j for j in recent(15) if j not in PROBLEM][:12])
    allr = []
    for j in jobs:
        for r in check(st, j):
            allr.append(r)
            flag = "" if not r["ok"] else " ".join(x for x in [
                ("수치%s" % r["fake_num"]) if r["fake_num"] else "", ("나라%s" % r["country"]) if r["country"] else "", ("주장%s" % r["claim"]) if r["claim"] else "",
                ("슬롯%d" % r["leak"]) if r["leak"] else ""] if x)
            print("== %s %-6s %s %ss %s %s" % (r["job"], r["style"], "OK" if r["ok"] else "없음", r.get("sec"),
                                             ("%d줄 %s" % (r["n"], r["spine"])) if r["ok"] else r.get("why"), flag), flush=True)
            for l in r.get("lines") or []:
                print("     ", l, flush=True)
    allr = [r for r in allr if not r.get("skip")]
    ok = [r for r in allr if r["ok"]]
    bad = [r for r in ok if r["fake_num"] or r["country"] or r.get("claim") or r["leak"]]
    print("\n요약: 시도 %d · 대본 나옴 %d · 없음 %d · 근거없는말 걸림 %d" % (len(allr), len(ok), len(allr) - len(ok), len(bad)))
    json.dump(allr, open("/tmp/batch_scripts.json", "w"), ensure_ascii=False, indent=1)
