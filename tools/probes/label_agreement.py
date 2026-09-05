# -*- coding: utf-8 -*-
"""[프로브] 목표표 3번 — 결(shot_role)·쓰임(label)이 묘사(scene_desc)·변화(change)와 맞는가(텍스트만, 영상당 모델 1회).
사용: py tools/probes/label_agreement.py <job_id> [video_id]
  기본은 DB의 기존 추출(extract_json)을 잰다. B1 결과를 재려면: --b1 <result.json 경로>(b1_extract_probe.py 산출)
08-31 실측(라이브 라벨 7~28%만 일치)이 출발점. 판정은 관대하니 상대 비교로만."""
import sys, os, json, sqlite3, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT); os.chdir(ROOT)
from shopping_shorts import keyroute, shot_roles, comment_gen
from shopping_shorts.config import DB_PATH
from google import genai
from google.genai import types

args = [a for a in sys.argv[1:] if not a.startswith("--")]
JOB = args[0] if args else "409f894230c6"
ONLY = args[1] if len(args) > 1 else None
B1_PATH = sys.argv[sys.argv.index("--b1") + 1] if "--b1" in sys.argv else None
key = comment_gen._current_key_and_idx()[0] or keyroute.gemini_keys("general")[0]
CLI = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=150_000))
GUIDE = shot_roles.guide_block()


def judge(segs):
    items = [{"no": i + 1, "scene_desc": s.get("scene_desc", ""), "change": s.get("change", ""),
              "shot_role": s.get("shot_role", ""), "label": s.get("label", "")} for i, s in enumerate(segs)]
    prompt = ("아래는 영상 구간마다 AI가 적은 [묘사(scene_desc)·변화(change)]와 거기에 붙인 [결(shot_role)·쓰임(label)]이다. "
              "묘사·변화를 사실로 보고, 결과 쓰임이 그 묘사에 **맞게 붙었는지** 항목마다 판정해라.\n결 어휘 정의:\n" + GUIDE + "\n"
              "판정 규칙: role_ok = 결이 묘사와 맞으면 true(묘사에 근거가 없거나 반대면 false). "
              "label_ok = 쓰임이 '왜 이 장면이 여기 있나'를 묘사에 맞게 12자 안팎으로 잡았으면 true(빈칸·묘사 반복·묘사와 다른 내용이면 false). "
              "묘사가 비어 있으면 둘 다 false.\n" + json.dumps(items, ensure_ascii=False)
              + '\n출력은 JSON {"items":[{"no":1,"role_ok":true,"label_ok":true,"why":"한 줄"}]} 만.')
    for model in ("gemini-3.1-flash-lite", "gemini-3.5-flash"):
        try:
            r = CLI.models.generate_content(model=model, contents=[prompt],
                                            config=types.GenerateContentConfig(response_mime_type="application/json"))
            return (json.loads(r.text) or {}).get("items") or []
        except Exception as e:      # noqa: BLE001
            print("  판정 실패", model, str(e)[:60]); time.sleep(5)
    return []


def tally(name, segs):
    res = judge(segs)
    by = {int(x.get("no", 0)): x for x in res if isinstance(x, dict)}
    n = len(segs)
    ro = sum(1 for i in range(n) if by.get(i + 1, {}).get("role_ok"))
    lo = sum(1 for i in range(n) if by.get(i + 1, {}).get("label_ok"))
    empty = sum(1 for s in segs if not (s.get("scene_desc") or "").strip())
    print(f"  {name}: 구간 {n} | 결 맞음 {ro}/{n} ({ro*100//max(1,n)}%) | 쓰임 맞음 {lo}/{n} ({lo*100//max(1,n)}%) | 빈 묘사 {empty}")
    return ro, lo, n


ex = json.loads(sqlite3.connect(DB_PATH).execute("select extract_json from mix_jobs where job_id=?", (JOB,)).fetchone()[0])
b1 = json.load(open(B1_PATH, encoding="utf-8")) if B1_PATH else None
tot = {}
for vid in ex:
    if ONLY and vid != ONLY:
        continue
    print(f"[{vid}]")
    sets = [("기존", ex[vid].get("segments") or [])]
    if b1 and vid in b1:
        sets.append(("B1", b1[vid].get("segments") or []))
    for name, segs in sets:
        ro, lo, n = tally(name, segs)
        t = tot.setdefault(name, [0, 0, 0]); t[0] += ro; t[1] += lo; t[2] += n
        time.sleep(4)
for name, (ro, lo, n) in tot.items():
    print(f"합계 {name}: 결 {ro}/{n} ({ro*100//max(1,n)}%) · 쓰임 {lo}/{n} ({lo*100//max(1,n)}%)")
