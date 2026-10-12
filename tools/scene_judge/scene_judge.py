"""후보 영상 장면 자동 판정 — 사람이 영상을 훑어보며 고르던 일을 대신한다.

사용: py tools/scene_judge/scene_judge.py <레퍼런스.mp4> <slots.json> <후보.mp4>... [--out result.json]

1) 후보마다 1초 1장 장면 시트(초 표시 붙임)를 만든다
2) Gemini에 레퍼런스 시트 + 후보 시트 + 칸 요구를 주고
   같은 제품? / 글자 박힘? / 레퍼런스 복제? / 칸별 쓸 구간(초) / 버릴 구간 을 받는다
3) 영상마다 걸린 시간·토큰·원 단위 비용을 적는다
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"
USD_IN, USD_OUT, KRW = 0.30 / 1e6, 2.50 / 1e6, 1400  # 정가(유료 등급) 기준
COLS, MAXSEC = 8, 48


def _env_key():
    for p in (Path(__file__).resolve().parents[2] / ".env",):
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.startswith("GEMINI_API_KEY="):
                return ln.split("=", 1)[1].strip().strip('"')
    raise SystemExit("GEMINI_API_KEY 없음")


def make_sheet(mp4, out_jpg):
    """1초 1장, 칸마다 초 숫자를 박은 시트. 최대 48초."""
    from PIL import Image, ImageDraw
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp4), "-t", str(MAXSEC),
                    "-vf", "fps=1,scale=180:-2", str(tmp / "f%03d.jpg")], check=True)
    frames = sorted(tmp.glob("f*.jpg"))
    w, h = Image.open(frames[0]).size
    rows = (len(frames) + COLS - 1) // COLS
    sheet = Image.new("RGB", (w * COLS, h * rows), "black")
    for i, f in enumerate(frames):
        im = Image.open(f)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 34, 20], fill="yellow")
        d.text((3, 3), f"{i}s", fill="black")
        sheet.paste(im, ((i % COLS) * w, (i // COLS) * h))
    sheet.save(out_jpg, quality=80)
    return len(frames)


def _frames(mp4):
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp4), "-t", str(MAXSEC),
                    "-vf", "fps=1,scale=180:-2", str(tmp / "f%03d.jpg")], check=True)
    return sorted(tmp.glob("f*.jpg"))


PROMPT = """너는 쇼핑 숏폼 편집자다. 첫 이미지는 레퍼런스 영상(이 제품으로 만들 영상)의 1초 1장 시트,
둘째 이미지는 후보 영상 시트다. 칸 위 노란 숫자가 초다.
레퍼런스 제품: {product}
채워야 할 장면 칸:
{slots}

후보 영상을 판정해 JSON만 답하라:
{{"same_product": true/false (레퍼런스와 같은 종류의 제품인가),
 "product_seen": "후보에 보이는 제품 한 줄",
 "burned_text": true/false (화면에 자막·큰 글자가 박혀 있어 그대로 쓰기 어려운가),
 "ref_copy": true/false (레퍼런스와 같은 영상을 재업로드한 것인가),
 "usable": [{{"slot":"칸 기호","from":초,"to":초,"why":"보이는 장면 한 줄"}}],
 "discard": [{{"from":초,"to":초,"why":"채널 프로필·엔딩·다른 제품 등"}}],
 "verdict": "use" | "partial" | "reject"}}
usable 은 실제로 그 칸 장면이 보이는 초만 적는다. 없으면 빈 배열. 짐작 금지."""


def judge(client, ref_jpg, cand_jpg, product, slots):
    slot_txt = "\n".join(f"{k}: {v}" for k, v in slots.items())
    parts = [PROMPT.format(product=product, slots=slot_txt),
             types.Part.from_bytes(data=Path(ref_jpg).read_bytes(), mime_type="image/jpeg"),
             types.Part.from_bytes(data=Path(cand_jpg).read_bytes(), mime_type="image/jpeg")]
    r = client.models.generate_content(model=MODEL, contents=parts,
                                       config=types.GenerateContentConfig(response_mime_type="application/json"))
    u = r.usage_metadata
    tin, tout = u.prompt_token_count or 0, (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
    return json.loads(r.text), tin, tout


def decide(j, spec):
    """최종 판정은 AI 답이 아니라 이 규칙이 정한다.
    제품 칸(spec.product_slots)은 같은 제품일 때만, 나머지 칸(시든 화분·반응 등)은 제품 무관하게 쓴다.
    글자 박힌 영상은 자막제거가 필요하므로 'clean' 으로 표시한다."""
    ps = set(spec.get("product_slots", []))
    bad = [(d["from"], d["to"]) for d in j.get("discard", [])]
    keep = []
    for u in j.get("usable", []):
        if not j.get("same_product") and u["slot"] in ps:
            continue
        for a, b in bad:  # 버릴 구간과 겹치면 그 앞까지만
            if u["from"] < a <= u["to"]:
                u = {**u, "to": a - 1}
        if u["to"] >= u["from"] and not any(a <= u["from"] <= b for a, b in bad):
            keep.append(u)
    j["usable"] = keep
    j["verdict"] = "reject" if not keep else ("clean" if j.get("burned_text") else "use")
    return j


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "scene_judge_result.json"
    if "--out" in sys.argv:
        a.remove(out)
    ref, spec, cands = a[0], json.loads(Path(a[1]).read_text(encoding="utf-8")), a[2:]
    client = genai.Client(api_key=_env_key())
    work = Path(tempfile.mkdtemp())
    ref_jpg = work / "ref.jpg"
    make_sheet(ref, ref_jpg)
    res = []
    for c in cands:
        vid = Path(c).parent.name
        t0 = time.time()
        cj = work / f"{vid}.jpg"
        n = make_sheet(c, cj)
        t1 = time.time()
        j, tin, tout = judge(client, ref_jpg, cj, spec["product"], spec["slots"])
        t2 = time.time()
        decide(j, spec)
        krw = (tin * USD_IN + tout * USD_OUT) * KRW
        res.append({"vid": vid, "secs": n, "sheet_s": round(t1 - t0, 1), "judge_s": round(t2 - t1, 1),
                    "in_tok": tin, "out_tok": tout, "krw": round(krw, 2), **j})
        print(f"{vid} {j.get('verdict'):8} 시트{t1-t0:.1f}s 판정{t2-t1:.1f}s {krw:.1f}원 "
              f"same={j.get('same_product')} copy={j.get('ref_copy')} text={j.get('burned_text')} "
              f"usable={[(u['slot'],u['from'],u['to']) for u in j.get('usable',[])]}", flush=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
