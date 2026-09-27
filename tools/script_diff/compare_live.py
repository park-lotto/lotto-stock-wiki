# -*- coding: utf-8 -*-
"""라이브 옛 대본 vs 새 대본 — 같은 작업·같은 씨앗·같은 스타일로 새 코드를 돌려 JSON으로 남긴다(사람이 읽고 판정용).
  (서버, repo 폴더에서, env 적재 후) python3 tools/script_diff/compare_live.py <dump.json> <out.json> [--yt-only] [--limit N]
  입력 = tools/script_diff/dump_works.py 결과(old_drafts = 그 작업에 실제로 나갔던 라이브 대본). DB에는 아무것도 안 쓴다.

2026-09-27 사장님 "테스트 잘하고 올리자 / 이걸(공식 문장 확장) 활용해서 한번 만들어보자".
"""
import sys, os, json, time, pathlib, argparse
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser(); ap.add_argument("dump"); ap.add_argument("out")
ap.add_argument("--yt-only", action="store_true"); ap.add_argument("--ig-only", action="store_true"); ap.add_argument("--limit", type=int, default=0)
args = ap.parse_args()
os.chdir(ROOT)
from shopping_shorts import story_writer as sw

D = json.load(open(args.dump, encoding="utf-8"))
res = []
for w in D["works"]:
    spines = [D["spines"][str(i)] for i in w["style_ids"] if D["spines"].get(str(i))][:1]
    if args.yt_only and not (spines and spines[0].get("no_cta")):
        continue
    if args.ig_only and not (spines and not spines[0].get("no_cta")):
        continue
    t0 = time.time()
    try:
        drafts, why = sw.make_drafts(spines, w["job"], 25, job_id=w["job_id"], preset="short",
                                     seed_text=w["seed_text"], seed_product=w["product"])
    except Exception as e:      # noqa: BLE001
        drafts, why = [], "예외 %r" % e
    secs = round(time.time() - t0, 1)

    def beats(d):
        return [{"role": b.get("role"), "text": b.get("text"), "segs": b.get("src_segs") or []} for b in d.get("beats") or []]
    res.append({"work_id": w["work_id"], "product": w["product"], "seed": w["seed_text"][:600],
                "style": (spines[0].get("name") if spines else ""), "why": why, "secs": secs,
                "old": [{"name": d.get("style_name"), "beats": beats(d)} for d in w.get("old_drafts") or []],
                "new": [{"name": d.get("style_name"), "beats": beats(d), "pinned": (d.get("writer_note") or {}).get("pinned") or {},
                         "retry": bool((d.get("writer_note") or {}).get("retry")), "problems": (d.get("writer_note") or {}).get("problems"),
                         "auth": (d.get("writer_note") or {}).get("auth"), "chars": d.get("chars"), "sec": d.get("sec"),
                         "seed_points": d.get("seed_points") or []}
                        for d in drafts]})
    print("%s %s %.1fs %s" % (w["work_id"], w["product"][:20], secs, why or "ok"), file=sys.stderr)
    if args.limit and len(res) >= args.limit:
        break
json.dump(res, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("works", len(res))
