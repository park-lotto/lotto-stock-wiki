# -*- coding: utf-8 -*-
"""방구석 칼카피 대본 — 라이브 작업의 실제 원본 영상 재료로 버텍스 시험.

서버에서(핫패치 금지 — 묶음을 /tmp/banggu_pkg/banggu/ 에 올려 부른다. 라이브 폴더는 읽기만):
  scp -r shopping_shorts/channel_presets/banggu  ubuntu@…:/tmp/banggu_pkg/
  scp tools/calcopy/try_banggu_live.py ubuntu@…:/tmp/banggu_pkg/
  cd /tmp/banggu_pkg && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && python3 try_banggu_live.py --n 10 --out /tmp/banggu_live.json

재는 것:
  ① 작업마다 담긴 영상 수 · 한국어 말이 있는 영상 수 · 쓸 수 있는 화면 길이
  ② 재료 추출을 **씨앗 1개만** 넣었을 때와 **담긴 영상 전부** 넣었을 때 — 인용 검증을 통과한 칸·쓸 수 있는 갈래가 어떻게 달라지나
  ③ 쓸 수 있는 갈래마다 대본 1편 — 규칙 반려 수·고쳐 쓴 횟수·최종 문장
★어색함의 최종 판정은 사람이 읽고 한다. 여기 숫자는 거르는 그물이다.
"""
import argparse, json, sqlite3, sys

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
# ★이 파일은 /tmp/banggu_pkg/ 안에 두고 거기서 실행한다 — /tmp 바로 아래에서 돌리면 스크립트 폴더(/tmp)가 찾는 길 맨 앞에 와서
#   /tmp 의 남의 스크립트가 라이브러리 이름을 가린다(2026-10-06 두 번: /tmp/h2.py 가 httpx 의 h2 대신 불려 실행됨).


def scene_text(src):
    rows = []
    for x in (src.get("segments") or [])[:40]:
        bits = [x.get("scene_desc") or "", x.get("use_point") or ""] + [str(b) for b in (x.get("product_benefits") or [])[:2]]
        t = " / ".join(b.strip() for b in bits if b and b.strip())
        if t:
            rows.append(t)
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10); ap.add_argument("--out", default="/tmp/banggu_live.json"); ap.add_argument("--scan", type=int, default=150)
    a = ap.parse_args()
    from google.genai import types
    from shopping_shorts import backbone_assemble as ba, config, usage_meter, vertex_route
    from banggu import material as mat, rules, script, spec

    def call(prompt):
        def _vx(cl, m):
            return cl.models.generate_content(model=m, contents=prompt,
                                              config=types.GenerateContentConfig(response_mime_type="application/json")).text
        import time
        for wait in (0, 10, 25, 45):          # 429(분당 한도)는 잠깐 쉬면 풀린다 — 실측 2026-10-06
            time.sleep(wait)
            ok, got = vertex_route.try_call("script_generate", _vx, what="칼카피시험")
            if ok:
                time.sleep(2)
                return got or ""
        raise RuntimeError("버텍스 호출 실패 — 키풀로 넘기지 않는다(시험은 버텍스 결과만 본다)")

    c = sqlite3.connect("file:%s?mode=ro" % config.DB_PATH, uri=True); c.row_factory = sqlite3.Row
    rows = c.execute("select job_id, extract_json, backbone_main, created_at from mix_jobs "
                     "where extract_json is not null and length(extract_json) > 2000 order by created_at desc limit ?", (a.scan,)).fetchall()
    res, seen, stats = [], set(), []
    with usage_meter.track(op="대본시험", customer_id=0):
        print("vertex on =", vertex_route.on("script_generate"), "model =", vertex_route.model())
        for r in rows:
            try:
                srcs = ba.sources_from_extract(json.loads(r["extract_json"]))
            except Exception:      # noqa: BLE001 — 깨진 행은 건너뛴다(개수는 아래 stats 에 안 들어간다)
                continue
            if not srcs:
                continue
            ko = [s for s in srcs if len((s.get("full_text_ko") or s.get("full_text") or "").strip()) >= 60]
            seed = ba.seed_source(srcs, r["backbone_main"])
            seed_txt = ((seed or {}).get("full_text_ko") or (seed or {}).get("full_text") or "").strip()
            vis = ba._drop_seed(srcs, seed) if seed else list(srcs)
            idx = ba._seg_index(vis)
            foot = sum(v["secs"] for v in idx.values() if v["secs"] >= ba.MIN_CUT_SECS)
            stats.append({"job": r["job_id"], "videos": len(srcs), "with_speech": len(ko), "footage_secs": round(foot, 1), "cuts": len(idx)})
            product = (((seed or {}).get("source_brief") or {}).get("product") or "").strip()
            if len(seed_txt) < 60 or not product or product in seen or len(res) >= a.n:
                continue
            seen.add(product)
            others = [s for s in srcs if s is not seed]
            seed_only = [{"id": "seed", "text": seed_txt}]
            every = seed_only + [{"id": s.get("video_id") or "", "text": ((s.get("full_text_ko") or s.get("full_text") or "").strip() + "\n[장면]\n" + scene_text(s)).strip()}
                                 for s in others]
            row = {"job": r["job_id"], "created": r["created_at"], "product": product, "videos": len(srcs), "with_speech": len(ko),
                   "footage_secs": round(foot, 1), "seed_chars": len(seed_txt), "seed": seed_txt[:500]}
            n1, n2 = {}, {}
            try:
                m1 = mat.extract(seed_only, product, call, note=n1)
                m2 = mat.extract_best(every, product, call, note=n2)
            except RuntimeError as e:
                print("  건너뜀:", e); seen.discard(product); continue
            row["seed_only"] = {"kept": sorted(m1), "kinds": mat.eligible(m1), "dropped": n1.get("material_dropped")}
            row["all_videos"] = {"kept": sorted(m2), "kinds": mat.eligible(m2), "dropped": n2.get("material_dropped"), "material": m2}
            print("\n##### %s | %s | 영상 %d(말 있는 것 %d) · 화면 %.0f초" % (r["job_id"], product, len(srcs), len(ko), foot))
            print("  씨앗만 : 칸 %d %s → 갈래 %s" % (len(m1), sorted(m1), [spec.KIND_KO[k] for k in mat.eligible(m1)]))
            print("  합침   : 칸 %d %s → 갈래 %s | 버린 칸 %s" % (len(m2), sorted(m2), [spec.KIND_KO[k] for k in mat.eligible(m2)], n2.get("material_dropped")))
            src_all = "\n".join(s["text"] for s in every)
            row["scripts"] = []
            for kind in mat.eligible(m2):
                logs = []
                try:
                    s, issues, attempts = script.generate(product, kind, m2, call, source_text=src_all, seed_text=seed_txt, log=logs.append)
                except RuntimeError as e:
                    print("  대본 건너뜀:", e); continue
                rej = rules.rejects(issues)
                row["scripts"].append({"kind": kind, "attempts": attempts, "rejects": [list(i) for i in rej],
                                       "warns": [list(i) for i in issues if i.level == rules.WARN], "script": s, "secs": script.seconds(s)})
                print("  --- %s · 시도 %d · 남은 반려 %d · %.1f초" % (spec.KIND_KO[kind], attempts, len(rej), script.seconds(s)))
                print("  " + script.as_text(s).replace("\n", "\n  "))
                for i in rej:
                    print("    ! %s «%s» %s" % (i.rule, i.found, i.why))
            res.append(row)
    json.dump({"jobs": res, "stats": stats}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import statistics as st
    v = [s["videos"] for s in stats]; sp = [s["with_speech"] for s in stats]; f = [s["footage_secs"] for s in stats]
    print("\n===== 최근 작업 %d건: 담긴 영상 수 중앙 %s (최소 %d · 최대 %d) · 말 있는 영상 중앙 %s · 쓸 화면 중앙 %.0f초" % (
        len(stats), st.median(v), min(v), max(v), st.median(sp), st.median(f)))
    import collections
    print("영상 수 분포:", sorted(collections.Counter(v).items()))
    k1 = sum(1 for r in res if r["seed_only"]["kinds"]); k2 = sum(1 for r in res if r["all_videos"]["kinds"])
    print("시험 %d건: 갈래가 하나라도 나온 작업 — 씨앗만 %d · 전부 %d" % (len(res), k1, k2))
    print("칸 수 평균 — 씨앗만 %.1f · 전부 %.1f" % (st.mean(len(r["seed_only"]["kept"]) for r in res), st.mean(len(r["all_videos"]["kept"]) for r in res)))
    sc = [s for r in res for s in r["scripts"]]
    print("대본 %d편: 한 번에 통과 %d · 고쳐 써서 통과 %d · 반려 남음 %d" % (
        len(sc), sum(1 for s in sc if s["attempts"] == 1 and not s["rejects"]), sum(1 for s in sc if s["attempts"] > 1 and not s["rejects"]), sum(1 for s in sc if s["rejects"])))


if __name__ == "__main__":
    main()
