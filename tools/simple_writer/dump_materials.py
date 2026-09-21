# -*- coding: utf-8 -*-
"""[서버용] 작업의 **실제 재료**를 JSON으로 내놓는다 — 단순 필자 하네스의 입력 (2026-09-21).
읽기 전용(DB에 아무것도 안 쓴다 · 모델 호출 0회). 라이브 프로그램이 재료를 읽는 것과 같은 함수로 읽는다.
    cd /home/ubuntu/lotto-stock-wiki && python3 /home/ubuntu/patchcheck/dump_materials.py --works a,b,c [--cid 0]"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [os.getcwd()] + [p for p in sys.path if os.path.abspath(p or ".") != _HERE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", required=True)
    ap.add_argument("--cid", type=int, default=0)
    a = ap.parse_args()
    from shopping_shorts import app as A, backbone_assemble as ba
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)
    out = []
    for wid in [w.strip() for w in a.works.split(",") if w.strip()]:
        row = {"work": wid}
        try:
            work = store.get_produce_work(wid, customer_id=a.cid)
            if not work:
                raise ValueError("work 없음")
            jid = str(work.get("job_id") or "").strip()
            job = A._enrich_job_extract(store.get_mix_job(jid), store) if jid else None
            if not (job or {}).get("extract"):
                job = dict(job or {}, extract=A._extract_from_work(wid, a.cid, store))
            srcs = ba.sources_from_extract((job or {}).get("extract") or {})
            seed = ba.seed_source(srcs, (job or {}).get("backbone_main"))
            if not seed:
                raise ValueError("씨앗 없음")
            vis = ba._drop_seed(srcs, seed)                      # 화면은 씨앗 영상을 안 쓴다(라이브와 같은 규칙)
            idx = ba._seg_index(vis)
            vids = {}
            for sid, v in sorted(idx.items()):
                if (v.get("secs") or 0) > 0:
                    vids.setdefault(v.get("vid"), []).append(
                        {"sid": sid, "secs": v["secs"], "desc": v.get("desc") or "", "say": (v.get("text") or "")[:60]})
            row.update(title=(work.get("title") or "")[:40], seed_vid=seed.get("video_id"),
                       seed_text=(seed.get("full_text") or "").strip(),
                       product=((seed.get("source_brief") or {}).get("product") or ""), videos=vids)
        except Exception as e:      # noqa: BLE001 — 한 건 실패가 나머지를 막으면 안 된다
            row["error"] = repr(e)[:160]
        out.append(row)
    sys.stdout.write("@@JSON@@" + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
