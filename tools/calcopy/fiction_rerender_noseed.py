# -*- coding: utf-8 -*-
"""픽션 썰 재렌더 — 씨앗영상 빼고. 이전 작업의 대본·목소리·꾸미기를 그대로 쓰고 재료 링크에서 씨앗만 뺀다.
서버에서(환경파일 실어서):
  python3 fiction_rerender_noseed.py new <이전작업> <씨앗url>     → 새 작업을 대기열에 넣는다(워커가 매칭·녹음)
  python3 fiction_rerender_noseed.py roles <이전작업> <새작업>     → 이전 작업에서 역할 목소리가 붙은 줄을 같은 대사 줄에 다시 붙이고 렌더
  python3 fiction_rerender_noseed.py check <새작업> <씨앗url>      → 컷에 씨앗 장면이 하나라도 있는지
"""
import sys, json, uuid
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import config, mix_pipeline

st = Store(config.DB_PATH)
from pathlib import Path
WORK = Path(config.DB_PATH).parent / "mix_jobs"


def _seed_vids(job, seed_url):
    key = seed_url.rstrip("/").split("/")[-1].split("v=")[-1]
    return {k for k, v in (job.get("extract") or {}).items()
            if isinstance(v, dict) and key in json.dumps(v, ensure_ascii=False)[:20000]} | {key}


def new(prev, seed_url):
    src = st.get_mix_job(prev)
    urls = [u for u in src["urls"] if u != seed_url]
    assert len(urls) == len(src["urls"]) - 1, "씨앗 링크가 목록에 없다"
    nid = uuid.uuid4().hex[:12]
    st.create_mix_job(nid, urls, src.get("target_seconds") or 25, src.get("structure") or "free",
                      subtitle_removal=False, given_script=src["given_script"], customer_id=0)
    st.update_mix_job(nid, voice=src.get("voice"), deco=src.get("deco"),
                      caption_style=src.get("caption_style"), headcopy=src.get("headcopy"))
    st.enqueue("mix", {"job_id": nid})
    print("NEW", nid, "재료", len(urls))


def roles(prev, nid):
    old = {b["narration"].strip(): b["voice_override"] for b in st.get_mix_job(prev)["edit_plan"]["beats"] if b.get("voice_override")}
    for b in st.get_mix_job(nid)["edit_plan"]["beats"]:
        ov = old.get((b.get("narration") or "").strip())
        if ov:
            mix_pipeline.resynth_one_beat(nid, b["beat_idx"], ov, config.DB_PATH, WORK)
            print("역할 목소리", b["beat_idx"], ov["voice_id"], b["narration"][:20])
    print(mix_pipeline.run_render(nid, config.DB_PATH, WORK, skip_clean=True))


def check(nid, seed_url):
    j = st.get_mix_job(nid)
    seeds = _seed_vids(j, seed_url)
    for b in j["edit_plan"]["beats"]:
        segs = [s for s in [b.get("primary")] + (b.get("alternates") or []) + (b.get("scene_override") or []) if isinstance(s, dict)]
        bad = [s["seg_id"] for s in segs if any(x in (s.get("seg_id") or "") or x == s.get("video_id") for x in seeds)]
        print(b["beat_idx"], (b.get("primary") or {}).get("seg_id"), "씨앗!" + str(bad) if bad else "ok", (b.get("narration") or "")[:24])


if __name__ == "__main__":
    {"new": new, "roles": roles, "check": check}[sys.argv[1]](*sys.argv[2:])
