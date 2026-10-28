# -*- coding: utf-8 -*-
"""사장님 job 5건 — 이븐쇼핑 스파인(55)으로 백본 조립 → 매칭 → 이븐쇼핑 프레임 → 렌더 (2026-09-17)"""
import sys, uuid, traceback
sys.path.insert(0, "/tmp/ab")
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline, backbone_assemble as ba

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
WORK = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
SPINE = 55   # 유튜브 「이건 바로 OO」 = 이븐쇼핑 원형(정체 감췄다 공개)
st = Store(DB)
JOBS = [("e0fb23f90286", "카메라"), ("iba25602b41", "행주"), ("ibe5dd32ec7", "수납함"),
        ("a26d3e9c5875", "미니후드"), ("44112f9a6e64", "레인지후드")]

for base, label in JOBS:
    try:
        job = st.get_mix_job(base)
        sources = ba.sources_from_extract(job.get("extract") or {})
        bb = max(sources, key=lambda s: len((s.get("full_text") or "").strip()))["video_id"]
        note = {}
        given, bs, meta = ba.assemble(sources, bb, st, spine_id=SPINE, target_seconds=25, seed=base, note=note)
        if not given:
            print(f"[{label}] 조립 실패: {meta.get('note')}", flush=True)
            continue
        jid = "bb" + uuid.uuid4().hex[:10]
        st.create_mix_job(jid, job["urls"], 25, "free", given_script=given,
                          script_structure={"beat_sources": bs, "inherit_scenes": True}, customer_id=0)
        n_sub = sum(1 for r in meta["report"] if r["from_sub"])
        print(f"[{label}] job {jid} 백본={bb} 스파인={meta['spine'].get('name')} 줄{len(bs)} 서브줄{n_sub}", flush=True)
        for r in meta["report"]:
            print(f"    {r['need']:.1f}s/{r['have']:.1f}s {'서브' if r['from_sub'] else '원본'} | {r['text']}", flush=True)
        mix_pipeline.run_mix_job(jid, DB, WORK)
        j = st.get_mix_job(jid)
        if j.get("status") != "ready_for_review":
            print(f"[{label}] mix 실패: {(j.get('error') or '')[:150]}", flush=True)
            continue
        title = (meta.get("product") or label)[:18]
        fr = {"preset": "sul_even", "span": "full", "head_block": True, "channel": "숏템메이커",
              "title": title + " 이게 뭐길래", "views": "264만", "comments": "587", "masks": []}
        st.update_mix_job(jid, deco={"extra_texts": [], "motion": None, "watermark": None,
                                     "template": {"span": "full", "frame": fr}})
        mix_pipeline.run_render(jid, DB, WORK)
        j = st.get_mix_job(jid)
        print(f"[{label}] RENDER {j.get('status')} {j.get('video_path')} {(j.get('error') or '')[:100]}", flush=True)
    except Exception as e:
        print(f"[{label}] 예외: {e}\n{traceback.format_exc()[-600:]}", flush=True)
print("BATCH_DONE", flush=True)
