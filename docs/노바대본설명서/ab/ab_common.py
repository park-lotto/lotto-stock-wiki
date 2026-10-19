"""A/B 공용 — 숏템메이커 코드 import, 버텍스 호출(숏템 _call_json 자리를 바꿔 끼움), 서버 표 사본 DB.
숏템메이커 저장소·서버 파일은 고치지 않는다. 서버 표는 server_tables.json(읽기 전용 SELECT 로 받은 spine 승인 26 · pattern_source · pattern_item 승인)."""
import json, os, sqlite3, sys, time

REPO = r"C:\Users\TheRose\Desktop\로또의 주식"
CALCOPY = os.path.join(REPO, ".tracks", "칼카피숏템엔진")
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT, LOCATION, MODEL = "project-74eaf695-8229-44a1-876", "global", "gemini-3.6-flash"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from google import genai
from google.genai import types

_CL = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
CALLS = []     # [{tag, ok, sec, chars_in}] — 호출 수 기록


def vertex_json(prompt, schema=None, tag=""):
    t0 = time.time()
    cfg = dict(response_mime_type="application/json")
    if schema:
        cfg["response_schema"] = schema
    last = None
    for _ in range(3):
        try:
            r = _CL.models.generate_content(model=MODEL, contents=prompt, config=types.GenerateContentConfig(**cfg))
            d = json.loads(r.text)
            CALLS.append({"tag": tag, "ok": True, "sec": round(time.time() - t0, 1), "chars_in": len(prompt)})
            return d
        except Exception as e:      # noqa: BLE001 — 재시도 후 실패를 기록
            last = repr(e)[:200]
            time.sleep(3)
    CALLS.append({"tag": tag, "ok": False, "err": last, "chars_in": len(prompt)})
    return {}


PROMPTS = []   # 숏템 코드가 모델에 보낸 프롬프트 원문(태그와 함께) — A 조립 확인용


def patch_shortem():
    """숏템메이커 script_generate._call_json(대본생성 깔때기)을 같은 버텍스 모델 호출로 바꿔 끼운다.
    라이브도 storyboard 는 sg._call_json(..., vertex=True) → vertex_route.try_call(같은 모델·response_schema) 이다."""
    from shopping_shorts import script_generate as sg

    def _cj(prompt, schema, note=None, model=None, vertex=True, vertex_op="script_generate"):
        PROMPTS.append(prompt)
        d = vertex_json(prompt, schema, tag=vertex_op)
        if note is not None:
            note["auth"] = "vertex:" + MODEL
        return d or {}
    sg._call_json = _cj
    return sg


def server_db():
    """server_tables.json → 로컬 사본 sqlite(이 폴더). storyboard._families·winners_block·parts_block 이 읽는다."""
    path = os.path.join(HERE, "shortem_server_copy.db")
    if os.path.exists(path):
        return path
    d = json.load(open(os.path.join(HERE, "server_tables.json"), encoding="utf-8"))
    db = sqlite3.connect(path)
    for t, v in d.items():
        db.execute(v["create"])
        q = "insert into %s (%s) values (%s)" % (t, ",".join(v["cols"]), ",".join("?" * len(v["cols"])))
        db.executemany(q, v["rows"])
    db.commit()
    db.close()
    return path
