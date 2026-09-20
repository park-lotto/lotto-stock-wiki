# -*- coding: utf-8 -*-
"""[프로브] 1단계 정확도 측정 — 잡의 소스 전 세그먼트를 프레임 대조(맞음/부분/틀림).
사용: py tools/probes/stage1_frame_accuracy.py <job_id> [video_id]   → out/probes/frames_<job>/result.json
전제: shopping_shorts/data/reference.db의 mix_jobs.extract_json + data/mix_jobs/<job>/<vid>/<vid>.mp4. 서버에서도 그대로 돈다.
tag_qa_frames의 _extract_frames/score_verdicts는 그대로 쓰고, 판정 호출만 스키마 없는 JSON으로 부른다
(2026-09-04 실측: 스키마 강제 호출은 4/4 504). 라이브는 안 건드린다."""
import sys, json, os, sqlite3, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = str(Path(__file__).resolve().parents[2])   # 저장소 루트 — 어느 PC/서버든
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from shopping_shorts import tag_qa_frames as T
from shopping_shorts.config import DB_PATH
from shopping_shorts import keyroute
from google import genai
from google.genai import types

KEY = keyroute.gemini_keys("general")[0]          # 로컬엔 SHORTS 풀 0개 → 예비풀 키
CLI = genai.Client(api_key=KEY, http_options=types.HttpOptions(timeout=150_000))

RULE = ("★묘사는 수 초짜리 구간 전체의 요약이고 이미지는 그 구간의 중간 한 장이다. "
        "묘사의 동작이 이 한 장에 다 담기지 않은 것은 정상이며 감점 사유가 아니다.\n"
        "판정: '맞음'=묘사의 주 대상이 화면의 주 대상과 같고 그 구간의 한 장면으로 자연스럽다 / "
        "'부분'=대상은 맞지만 묘사가 화면과 모순된다 / '틀림'=주 대상 자체가 다르다"
        "(배경 소품을 주제품처럼 적었으면 틀림).\n"
        '출력은 JSON 객체 {"verdicts": [{"image_no": 1부터, "verdict": "맞음|부분|틀림", '
        '"reason": "한국어 한 줄"}]} 만. 모든 이미지를 빠짐없이.')


def judge(frame_paths, picked):
    lines = "\n".join(f"{n+1}번 이미지의 묘사: {(s.get('scene_desc') or '(없음)')}"
                      for n, (_, s) in enumerate(picked))
    prompt = (f"영상에서 뽑은 프레임 {len(frame_paths)}장이다(순서대로). 각 이미지가 아래 묘사와 "
              f"맞는지 판정해라.\n{lines}\n\n" + RULE)
    parts = [prompt] + [types.Part.from_bytes(data=open(fp, "rb").read(), mime_type="image/jpeg")
                        for fp in frame_paths]
    for model in ("gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"):
        try:
            r = CLI.models.generate_content(
                model=model, contents=parts,
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            d = json.loads(r.text)
            v = d.get("verdicts") if isinstance(d, dict) else d
            if v:
                print(f"  (판정 모델 {model})")
                return v
        except Exception as e:  # noqa: BLE001
            print(f"  판정 실패 {model}: {str(e)[:80]}")
            time.sleep(6)
    return []


JOB = sys.argv[1] if len(sys.argv) > 1 else "409f894230c6"
ONLY = sys.argv[2] if len(sys.argv) > 2 else None
c = sqlite3.connect(DB_PATH)
row = c.execute("select extract_json from mix_jobs where job_id=?", (JOB,)).fetchone()
ex = json.loads(row[0] or "{}")
tmp = os.path.join(ROOT, "out", "probes", "frames_" + JOB)
os.makedirs(tmp, exist_ok=True)
tot = {"맞음": 0, "부분": 0, "틀림": 0}
rows = []
for vid, e in ex.items():
    if ONLY and vid != ONLY:
        continue
    segs = e.get("segments") or []
    picked = [(i, s) for i, s in enumerate(segs) if T._usable(s)]
    vpath = os.path.join(ROOT, "shopping_shorts", "data", "mix_jobs", JOB, vid, vid + ".mp4")
    if not os.path.exists(vpath):
        print(f"[{vid}] mp4 없음 — 건너뜀")
        continue
    d = os.path.join(tmp, vid)
    os.makedirs(d, exist_ok=True)
    paths, kept = T._extract_frames(vpath, picked, d)
    t0 = time.time()
    verdicts = judge(paths, kept)
    score, detail = T.score_verdicts(verdicts, kept)
    by_no = {int(v.get("image_no", 0)): v for v in (verdicts or [])}
    print(f"\n[{vid}] 세그 {len(segs)} / 대조 {len(kept)} / 점수 {score} / {time.time()-t0:.0f}s")
    for n, (i, s) in enumerate(kept, 1):
        v = by_no.get(n, {})
        vd = v.get("verdict", "?")
        if vd in tot:
            tot[vd] += 1
        L = float(s["end"]) - float(s["start"])
        print(f"  seg{i:>2} {L:5.1f}s {vd:2s} | {(s.get('scene_desc') or '')[:45]} | {v.get('reason', '')[:55]}")
        rows.append({"vid": vid, "seg": i, "len": round(L, 1), "verdict": vd,
                     "desc": s.get("scene_desc"), "reason": v.get("reason")})
    time.sleep(4)
n = sum(tot.values()) or 1
print(f"\n합계 {sum(tot.values())}건: 맞음 {tot['맞음']} ({tot['맞음']*100//n}%) / 부분 {tot['부분']} / 틀림 {tot['틀림']}")
json.dump(rows, open(os.path.join(tmp, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
