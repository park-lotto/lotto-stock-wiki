# 옮긴 대본(transpose_hit 결과) → 실제 제작 job → 렌더 (2026-09-19 순서 0 '장면 붙이기' 실증).
# 사용(서버, 라이브 코드로):  python3 transpose_render.py trans.json <index>
#   trans.json 의 한 항목(job=재료 job, cells=[{role,text,segs}])으로 새 job을 만든다.
# 칸 하나 = 대본 한 줄(script_sentences는 줄이 곧 단위) · 줄마다 beat_sources{segs} → 3단계 상속(inherit_scenes)이
# 대사 길이만큼 같은 소스 다음 컷을 이어 붙인다(_extend_refs_to_narration). 반복재생 끝 조각(짧은 끊김)은 앞 줄에 붙인다.
import json, sys, uuid
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
WORK = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"


def lines_of(cells):
    L = []
    for c in cells:
        t = " ".join((c.get("text") or "").split())
        if not t:
            continue
        if L and len(t) <= 8:              # '근데' 같은 반복재생 꼬리 — 한 줄로 서기엔 짧다
            L[-1]["text"] += " " + t
            continue
        L.append({"role": c.get("role") or "", "text": t, "segs": list(c.get("segs") or [])})
    for i, x in enumerate(L):              # 컷 없는 줄은 앞 줄 컷을 이어 쓴다(3단계가 다음 컷으로 늘린다)
        if not x["segs"] and i:
            x["segs"] = L[i - 1]["segs"][-1:]
    return L


def reuse_base_sources(base_job):
    """서버는 유튜브 쇼츠를 새로 못 받는다(데이터센터 IP 차단, 메모리 reference_youtube_shorts_datacenter_block).
    실증 한정: 재료 job 폴더에 이미 받아 둔 sN/*.mp4를 새 job으로 복사해 쓴다. 라이브 코드는 안 바꾼다."""
    import glob, shutil
    from pathlib import Path
    orig = mix_pipeline.download_any

    def fake(url, dest):
        vid = Path(dest).name
        got = sorted(glob.glob("%s/%s/%s/*.mp4" % (WORK, base_job, vid)))
        if got:
            dst = Path(dest) / Path(got[0]).name
            shutil.copy(got[0], dst)
            return str(dst), ""
        return orig(url, dest)
    mix_pipeline.download_any = fake


def main():
    R = json.load(open(sys.argv[1], encoding="utf-8"))
    r = R[int(sys.argv[2])]
    st = Store(DB)
    base = st.get_mix_job(r["job"])
    L = lines_of(r["cells"])
    given = "\n".join(x["text"] for x in L)
    bs = [{"role": x["role"], "seg": (x["segs"] or [""])[0], "segs": x["segs"]} for x in L]
    jid = "bt" + uuid.uuid4().hex[:10]
    st.create_mix_job(jid, base["urls"], 25, "free", given_script=given,
                      script_structure={"beat_sources": bs, "inherit_scenes": True}, customer_id=0)
    st.update_mix_job(jid, subtitle_removal=1)      # 원본 하드자막 제거(렌더가 완성본 1편만 청소, 1콜)
    print("JOB", jid, "줄", len(L), "컷", sum(len(x["segs"]) for x in L), flush=True)
    for x in L:
        print("  [%s] %s  ← %s" % (x["role"], x["text"], x["segs"]), flush=True)
    reuse_base_sources(r["job"])
    mix_pipeline.run_mix_job(jid, DB, WORK)
    j = st.get_mix_job(jid)
    print("mix status", j.get("status"), (j.get("error") or "")[:200], flush=True)
    mix_pipeline.run_render(jid, DB, WORK)
    j = st.get_mix_job(jid)
    print("render status", j.get("status"), (j.get("error") or "")[:200], j.get("output_path") or j.get("final_path") or "", flush=True)


if __name__ == "__main__":
    main()
