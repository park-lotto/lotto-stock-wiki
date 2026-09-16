# -*- coding: utf-8 -*-
"""백본-먼저 실증 1편 — 한셉트 제로 MK2 (2026-09-16, 사장님 지시 "대본 쓰고 매칭해서 렌더까지")

기존 job 68dc7e13dc23의 재료(URL 7편·추출 캐시)를 그대로 쓰는 새 job을 만들어
확정 대본(given_script) + 줄별 컷 지정(beat_sources) + 상속(inherit_scenes)으로 돌린다.
대본은 out/특징정리_한셉트제로MK2.html의 특징 묶음에서 고른 순서. 컷은 서브 우선, 펜촉·필기만 원본.
"""
import sys, uuid, json, sqlite3
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
WORK = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
BASE = "68dc7e13dc23"

# 줄마다 마침표 하나 — script_sentences가 문장 단위로 쪼개므로 줄 수 == beat_sources 수여야 상속이 탄다
LINES = [
    ("hook",     "펜 찾을 때마다 가방 뒤지는 거 진짜 답답했잖아요.",           ["grab_tiktok_0ddb76bd6a20-0"]),
    ("size",     "근데 이건 그냥 카드지갑에 들어가요, 카드 한 장 두께라서.",    ["tjhKrXqsTGI-3"]),
    ("joint",    "접착제 하나 없이 금속만 맞물려서 카드랑 펜을 왔다 갔다 해요.", ["grab_tiktok_422b8d23dc83-2"]),
    ("hexagon",  "접어 올리면 손에 딱 잡히는 육각형 펜이 돼요.",               ["grab_tiktok_be4dc25f404e-0", "grab_tiktok_be4dc25f404e-1"]),
    ("nib",      "안에 숨어 있던 펜촉이 튀어나오고 바로 써져요.",              ["tjhKrXqsTGI-11", "tjhKrXqsTGI-13"]),
    ("parts",    "이 얇은 카드 한 장에 부품이 54개래요.",                     ["grab_tiktok_0ddb76bd6a20-1"]),
    ("precise",  "정밀하게 맞물려서 흔들림도 없고요.",                        ["grab_tiktok_0ddb76bd6a20-2"]),
    ("stand",    "다 쓰면 책상 거치대에 세워두면 돼요.",                      ["grab_tiktok_8f40be06511a-4"]),
    ("cta",      "이름 궁금하면 댓글에 카드 남겨주세요.",                     ["grab_tiktok_0ddb76bd6a20-6"]),
]

st = Store(DB)
base = st.get_mix_job(BASE)
assert base, "기준 job 없음"
urls = base["urls"]
print("재료 URL", len(urls), "편")

given = "\n".join(t for _, t, _ in LINES)
beat_sources = [{"role": r, "seg": segs[0], "segs": segs} for r, _, segs in LINES]
job_id = "bb" + uuid.uuid4().hex[:10]
st.create_mix_job(job_id, urls, 25, "free",
                  given_script=given,
                  script_structure={"beat_sources": beat_sources, "inherit_scenes": True},
                  customer_id=0)
print("새 job:", job_id)
print("대본 글자수:", sum(len(t) for _, t, _ in LINES), "/ 줄", len(LINES), "/ 지정 컷", sum(len(s) for _, _, s in LINES))

mix_pipeline.run_mix_job(job_id, DB, WORK)
j = st.get_mix_job(job_id)
print("run_mix_job 뒤 status:", j.get("status"), "| error:", (j.get("error") or "")[:200])
print("JOB_ID=" + job_id)
