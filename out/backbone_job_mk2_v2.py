# -*- coding: utf-8 -*-
"""백본-먼저 실증 v2 — 로고 컷 교체 + 원본 상단 UI 크롭 (2026-09-16)
v1(bb1cc3402937)에서 눈으로 잡힌 것 둘을 고친다:
  · be4dc2-0/1(상단 53% 일본어 로고 인트로) → 422b8d-1(펜 완성)
  · 원본 tjh-3/11/13(상단 15% 뉴스 UI) → 크롭본으로 소스 파일 교체(seg 타이밍 불변, 해상도 유지)
"""
import sys, uuid, subprocess, shutil, glob, os
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
WORK = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
BASE = "68dc7e13dc23"

LINES = [
    ("hook",    "펜 찾을 때마다 가방 뒤지는 거 진짜 답답했잖아요.",           ["grab_tiktok_0ddb76bd6a20-0"]),
    ("size",    "근데 이건 그냥 카드지갑에 들어가요, 카드 한 장 두께라서.",    ["tjhKrXqsTGI-3"]),
    ("joint",   "접착제 하나 없이 금속만 맞물려서 카드랑 펜을 왔다 갔다 해요.", ["grab_tiktok_422b8d23dc83-2"]),
    ("hexagon", "접어 올리면 손에 딱 잡히는 육각형 펜이 돼요.",               ["grab_tiktok_422b8d23dc83-1"]),
    ("nib",     "안에 숨어 있던 펜촉이 튀어나오고 바로 써져요.",              ["tjhKrXqsTGI-11", "tjhKrXqsTGI-13"]),
    ("parts",   "이 얇은 카드 한 장에 부품이 54개래요.",                     ["grab_tiktok_0ddb76bd6a20-1"]),
    ("precise", "정밀하게 맞물려서 흔들림도 없고요.",                        ["grab_tiktok_0ddb76bd6a20-2"]),
    ("stand",   "다 쓰면 책상 거치대에 세워두면 돼요.",                      ["grab_tiktok_8f40be06511a-4"]),
    ("cta",     "이름 궁금하면 댓글에 카드 남겨주세요.",                     ["grab_tiktok_0ddb76bd6a20-6"]),
]

st = Store(DB)
urls = st.get_mix_job(BASE)["urls"]
given = "\n".join(t for _, t, _ in LINES)
beat_sources = [{"role": r, "seg": s[0], "segs": s} for r, _, s in LINES]
job_id = "bb" + uuid.uuid4().hex[:10]
st.create_mix_job(job_id, urls, 25, "free", given_script=given,
                  script_structure={"beat_sources": beat_sources, "inherit_scenes": True}, customer_id=0)
print("새 job:", job_id)

mix_pipeline.run_mix_job(job_id, DB, WORK)
j = st.get_mix_job(job_id)
print("mix status:", j.get("status"), "| error:", (j.get("error") or "")[:160])
if j.get("status") != "ready_for_review":
    sys.exit("mix 실패")

# 원본(s0)을 상단 165행 잘라낸 크롭본으로 교체 — 9:16 유지(515×915 → 608×1080), seg 타이밍 불변
s0 = glob.glob(f"{WORK}/{job_id}/s0/*.mp4")[0]
bak = s0 + ".orig"
shutil.copy2(s0, bak)
r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", bak,
                    "-vf", "crop=515:915:46:165,scale=608:1080:flags=lanczos",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy",
                    "-movflags", "+faststart", s0], capture_output=True, text=True)
print("크롭:", "OK" if r.returncode == 0 else r.stderr[:300])
os.remove(bak)

mix_pipeline.run_render(job_id, DB, WORK)
j = st.get_mix_job(job_id)
print("RENDER status:", j.get("status"), "| video:", j.get("video_path"), "| error:", (j.get("error") or "")[:160])
print("JOB_ID=" + job_id)
