# -*- coding: utf-8 -*-
"""방구석·선물가게(같은 운영자) 칼카피 — 그 채널의 터진 편을 **씨앗**으로 넣고, 실제 고객 제품 재료로 그 틀대로 쓴다(seedflow).
서버: cd /tmp/banggu_pkg && (환경 실어서) python3 try_seedflow_banggu.py --seeds 씨앗_방구석선물가게_6편.json --n 8 --out /tmp/seedflow_banggu.json
작업마다 씨앗을 돌려가며 짝짓는다(제품 i → 씨앗 i mod 6). 씨앗 분석은 씨앗당 1회만(캐시).
검사: seedflow.problems + 방구석 규칙(banggu.rules: 말끝·권하는 말·혼잣말 꼴) — 방구석 틀로 나왔는지 그 자로 잰다.
"""
import argparse, json, sqlite3, sys, time
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", required=True); ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--out", default="/tmp/seedflow_banggu.json"); ap.add_argument("--scan", type=int, default=150)
    a = ap.parse_args()
    from google.genai import types
    from shopping_shorts import backbone_assemble as ba, config, usage_meter, vertex_route
    import seedflow as sf
    from banggu import rules as br

    def call(prompt):
        def _vx(cl, m):
            return cl.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")).text
        for wait in (0, 10, 25, 45):
            time.sleep(wait)
            ok, got = vertex_route.try_call("script_generate", _vx, what="칼카피씨앗시험")
            if ok:
                time.sleep(2); return got or ""
        raise RuntimeError("버텍스 호출 실패")

    def search_call(prompt):
        """검색이 붙은 호출 — 숨겨진 이야기 조사용. JSON 모드와 검색 도구를 같이 못 쓰므로 글로 받고 parse 가 첫 JSON 객체를 꺼낸다."""
        def _vx(cl, m):
            return cl.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())])).text
        for wait in (0, 10, 25, 45):
            time.sleep(wait)
            ok, got = vertex_route.try_call("script_generate", _vx, what="칼카피조사")
            if ok:
                time.sleep(2); return got or ""
        raise RuntimeError("버텍스(검색) 호출 실패")

    seeds = json.load(open(a.seeds, encoding="utf-8"))
    c = sqlite3.connect("file:%s?mode=ro" % config.DB_PATH, uri=True); c.row_factory = sqlite3.Row
    rows = c.execute("select job_id, extract_json, backbone_main from mix_jobs where extract_json is not null and length(extract_json) > 2000 order by created_at desc limit ?", (a.scan,)).fetchall()
    res, seen, an_cache = [], set(), {}
    with usage_meter.track(op="대본시험", customer_id=0):
        for r in rows:
            if len(res) >= a.n:
                break
            try:
                srcs = ba.sources_from_extract(json.loads(r["extract_json"]))
            except Exception:      # noqa: BLE001
                continue
            seed_src = ba.seed_source(srcs, r["backbone_main"]) if srcs else None
            product = (((seed_src or {}).get("source_brief") or {}).get("product") or "").strip()
            if not product or product in seen or not srcs:
                continue
            seen.add(product)
            scenes = [{"id": x.get("seg_id"), "role": x.get("shot_role") or "", "desc": x.get("scene_desc") or "", "use": x.get("use_point") or "",
                       "feats": x.get("product_benefits") or []} for s in srcs for x in (s.get("segments") or []) if x.get("seg_id")][:90]
            sd = seeds[len(res) % len(seeds)]
            try:
                if sd["name"] not in an_cache:
                    an_cache[sd["name"]] = sf.analyze_seed(sd["text"], call)
                out = sf.run(product, sd["text"], scenes, call, search_call=search_call, seed_an=an_cache[sd["name"]], log=lambda *_: None)
                an, pts, sc, bad, n = out["seed"], out["points"], out["script"], out["problems"], out["attempts"]
            except (RuntimeError, ValueError) as e:
                print("건너뜀 %s: %s" % (product, e)); seen.discard(product); continue
            lines = [{"role": L.get("beat") or "", "text": L.get("text") or ""} for L in sc.get("lines") or [] if (L.get("text") or "").strip()]
            bg = {"kind": "hidden", "title": sc.get("title") or "", "lines": lines, "comment": ""}
            src_txt = sd["text"] + " " + " ".join(p["text"] for p in pts) + " " + " ".join(s["desc"] + " " + s["use"] for s in scenes)
            bg_rej = [list(i) for i in br.rejects(br.lint(bg, {"source_text": src_txt, "seed_text": sd["text"]})) if i.rule not in ("bg_copy", "bg_lines", "bg_length", "bg_title_len")]
            body = " ".join(L["text"] for L in lines)
            row = {"job": r["job_id"], "product": product, "seed_name": sd["name"], "videos": len(srcs), "scenes": len(scenes), "seed": an, "points": pts, "facts": out["facts"], "story": out["story"],
                   "script": sc, "problems": bad, "attempts": n, "banggu_rejects": bg_rej, "copy_share": round(sf.gram_share(body, sd["text"]), 2), "chars": sf.chars(body)}
            res.append(row)
            print("\n##### %s ← 씨앗 %s | 영상 %d · 장면 %d | 대본 %d자 · 씨앗과 겹침 %.0f%% · 시도 %d · 흐름 문제 %d · 방구석 규칙 어김 %d" % (
                product, sd["name"], len(srcs), len(scenes), row["chars"], row["copy_share"] * 100, n, len(bad), len(bg_rej)))
            print("[틀] " + " → ".join(b["name"] for b in an.get("beats") or []) + " | " + (an.get("tone") or ""))
            print("[포인트] %d개 — 새것 %d · %s" % (len(pts), sum(1 for p in pts if not p["in_seed"]), {o: sum(1 for p in pts if p["origin"] == o) for o in sf.ORIGINS}))
            print("[숨겨진 이야기] %d개" % len(out["facts"]))
            for f in out["facts"]:
                print("   %s. (%s) %s — %s" % (f["id"], f.get("kind") or "", f["text"], (f.get("source") or "")[:60]))
            st = out["story"]
            print("[썰] %s · 주인공 %s · 숨은 이야기 씀=%s" % (st.get("type"), st.get("cast"), st.get("uses_fact")))
            for b in st.get("beats") or []:
                print("   (%s) %s   ← %s" % (b.get("step"), b.get("text"), ",".join(b.get("uses") or [])))
            if st.get("dramatized"):
                print("   꾸민 서술: " + " / ".join(st["dramatized"]))
            print("[대본]\n  (훅) " + (sc.get("title") or ""))
            for L in sc.get("lines") or []:
                if (L.get("text") or "").strip() != (sc.get("title") or "").strip():
                    print("  (%s) %s   ← 장면 %s" % (L.get("beat"), L.get("text"), ",".join(str(x) for x in (L.get("cuts") or [])[:2]) or "-"))
            for b in bad:
                print("  ! " + b)
            for i in bg_rej:
                print("  ! 방구석 규칙 %s «%s» %s" % (i[0], i[3], i[4]))
    json.dump({"jobs": res}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n===== %d건 · 흐름 문제 없음 %d · 방구석 규칙 통과 %d · 씨앗과 겹침 중앙 %.0f%%" % (
        len(res), sum(1 for r in res if not r["problems"]), sum(1 for r in res if not r["banggu_rejects"]),
        100 * sorted(r["copy_share"] for r in res)[len(res) // 2] if res else 0))


if __name__ == "__main__":
    main()
