# -*- coding: utf-8 -*-
"""씨앗 흐름(shopping_shorts/seedflow.py) — 라이브 작업의 실제 씨앗·해외 영상 장면 태깅으로 버텍스 시험.

서버에서(라이브 폴더는 읽기만 — 파일은 /tmp/banggu_pkg/ 에 올려 거기서 실행):
  scp shopping_shorts/seedflow.py tools/calcopy/try_seedflow_live.py ubuntu@…:/tmp/banggu_pkg/
  cd /tmp/banggu_pkg && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && python3 try_seedflow_live.py --n 8 --out /tmp/seedflow_live.json
보는 것: 씨앗에서 뽑은 홀린 요인 · 포인트(새것 몇 개, 어디서 왔나) · 대본(줄마다 붙은 장면) · 남은 문제 · 씨앗과 겹치는 정도.
"""
import argparse, json, sqlite3, sys, time

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8); ap.add_argument("--out", default="/tmp/seedflow_live.json"); ap.add_argument("--scan", type=int, default=150)
    a = ap.parse_args()
    from google.genai import types
    from shopping_shorts import backbone_assemble as ba, config, usage_meter, vertex_route
    import seedflow as sf

    def call(prompt):
        def _vx(cl, m):
            return cl.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")).text
        for wait in (0, 10, 25, 45):
            time.sleep(wait)
            ok, got = vertex_route.try_call("script_generate", _vx, what="씨앗흐름시험")
            if ok:
                time.sleep(2); return got or ""
        raise RuntimeError("버텍스 호출 실패")

    c = sqlite3.connect("file:%s?mode=ro" % config.DB_PATH, uri=True); c.row_factory = sqlite3.Row
    rows = c.execute("select job_id, extract_json, backbone_main from mix_jobs where extract_json is not null and length(extract_json) > 2000 "
                     "order by created_at desc limit ?", (a.scan,)).fetchall()
    res, seen = [], set()
    with usage_meter.track(op="대본시험", customer_id=0):
        for r in rows:
            if len(res) >= a.n:
                break
            try:
                srcs = ba.sources_from_extract(json.loads(r["extract_json"]))
            except Exception:      # noqa: BLE001
                continue
            seed = ba.seed_source(srcs, r["backbone_main"]) if srcs else None
            seed_txt = ((seed or {}).get("full_text_ko") or (seed or {}).get("full_text") or "").strip()
            product = (((seed or {}).get("source_brief") or {}).get("product") or "").strip()
            others = [s for s in srcs or [] if s is not seed]
            if len(seed_txt) < 60 or not product or product in seen or not others:
                continue
            seen.add(product)
            scenes = [{"id": x.get("seg_id"), "role": x.get("shot_role") or "", "desc": x.get("scene_desc") or "", "use": x.get("use_point") or "",
                       "feats": x.get("product_benefits") or []} for s in others for x in (s.get("segments") or []) if x.get("seg_id")][:90]
            logs = []
            try:
                out = sf.run(product, seed_txt, scenes, call, log=logs.append)
            except (RuntimeError, ValueError) as e:
                print("건너뜀 %s: %s" % (product, e)); seen.discard(product); continue
            pts, sc = out["points"], out["script"]
            body = " ".join(L.get("text") or "" for L in sc.get("lines") or [])
            row = {"job": r["job_id"], "product": product, "videos": len(srcs), "scenes": len(scenes), "seed": seed_txt, **out,
                   "copy_share": round(sf.gram_share(body, seed_txt), 2), "chars": sf.chars(body), "seed_chars": sf.chars(seed_txt)}
            res.append(row)
            print("\n##### %s | 영상 %d · 장면 %d | 씨앗 %d자 → 대본 %d자 · 씨앗과 겹침 %.0f%% · 시도 %d · 남은 문제 %d" % (
                product, len(srcs), len(scenes), row["seed_chars"], row["chars"], row["copy_share"] * 100, out["attempts"], len(out["problems"])))
            print("[씨앗] " + seed_txt[:420])
            print("[틀] " + " → ".join(b["name"] for b in out["seed"].get("beats") or []) + " | " + (out["seed"].get("tone") or "") + " · " + (out["seed"].get("voice") or ""))
            for h in out["seed"].get("hooked") or []:
                print("[홀린 요인] " + h["why"])
            print("[포인트] %d개 — 새것 %d · 어디서: %s" % (len(pts), sum(1 for p in pts if not p["in_seed"]),
                                                   {o: sum(1 for p in pts if p["origin"] == o) for o in sf.ORIGINS}))
            for p in pts:
                print("   %d. (%s/%s%s) %s — %s | 장면 %d" % (p["id"], p.get("kind"), p["origin"], "" if p["in_seed"] else "·새", p["text"], p.get("hook") or "", len(p["cuts"])))
            print("[대본]\n  (훅) " + (sc.get("title") or ""))
            for L in sc.get("lines") or []:
                print("  (%s) %s   ← 포인트 %s · 장면 %s" % (L.get("beat"), L.get("text"), L.get("points") or [], ",".join(str(x) for x in (L.get("cuts") or [])[:3]) or "-"))
            for b in out["problems"]:
                print("  ! " + b)
    json.dump({"jobs": res}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if res:
        import statistics as st
        print("\n===== %d건: 포인트 중앙 %s개(새것 %s) · 일반지식 포인트 합 %d · 씨앗과 겹침 중앙 %.0f%% · 문제 없이 끝난 대본 %d · 장면 없는 줄 비율 %.0f%%" % (
            len(res), st.median(len(r["points"]) for r in res), st.median(sum(1 for p in r["points"] if not p["in_seed"]) for r in res),
            sum(1 for r in res for p in r["points"] if p["origin"] == "일반지식"), st.median(r["copy_share"] for r in res) * 100,
            sum(1 for r in res if not r["problems"]),
            100 * sum(1 for r in res for L in r["script"].get("lines") or [] if not L.get("cuts")) / max(1, sum(len(r["script"].get("lines") or []) for r in res))))


if __name__ == "__main__":
    main()
