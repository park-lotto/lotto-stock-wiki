"""감정짤 밈팩 — 짤마다 '국내/해외' 와 '실사/애니' 를 붙인다.

    py tools/meme_pack/classify.py <작업폴더> [--redo]

이 두 구분의 주인은 이 파일이다(REGIONS·KINDS·classify). 결과는 tags.json:
  { id: {"region": "국내"|"해외", "kind": "실사"|"애니", "by": "gemini"} }
사장님이 뷰어에서 고친 값은 state.json 에 따로 저장되고 그쪽이 이긴다(serve.py 가 합친다).
Gemini 에게 표지 그림 12장을 한 장으로 묶어 한 번에 묻는다(짤 1개당 호출 1번보다 12배 싸다).
"""
import argparse
import io
import json
import os
import sys
import time

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_pack  # noqa: E402  (키·모델 고르기는 build_pack 한 곳)
import serve  # noqa: E402

REGIONS = ("국내", "해외")
KINDS = ("실사", "애니")
BATCH, TILE = 12, 260


def _thumb(work, cid):
    for p in (os.path.join(work, "library", "thumbs", f"{cid}.jpg"), os.path.join(work, "sheets", "thumbs", f"{cid}.jpg")):
        if os.path.exists(p):
            return p
    return None


def _sheet(work, batch):
    cols = 4
    rows = (len(batch) + cols - 1) // cols
    sheet = Image.new("RGB", (TILE * cols, TILE * rows), "black")
    dr = ImageDraw.Draw(sheet)
    for k, it in enumerate(batch):
        im = Image.open(_thumb(work, it["id"])).convert("RGB")
        im.thumbnail((TILE, TILE))
        x, y = (k % cols) * TILE, (k // cols) * TILE
        sheet.paste(im, (x + (TILE - im.width) // 2, y + (TILE - im.height) // 2))
        dr.rectangle([x, y, x + 34, y + 20], fill="black")
        dr.text((x + 5, y + 4), f"#{k + 1}", fill="yellow")
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def classify(work, batch):
    """batch(최대 12개) → {id: {region, kind}}. 실패는 예외."""
    from google.genai import types
    titles = "\n".join(f"#{k + 1}: {it['title'][:80]}" for k, it in enumerate(batch))
    prompt = (
        f"그림은 짧은 리액션 영상 {len(batch)}개의 한 장면을 모은 것이다. 칸 왼쪽 위 노란 번호(#1…)가 영상 번호다.\n"
        "영상마다 두 가지를 판정해라.\n"
        "1) kind — '실사': 실제 사람·동물을 카메라로 찍은 영상. '애니': 애니메이션·만화·게임 화면·3D/CG 캐릭터·그림.\n"
        "2) region — '국내': 한국 방송·한국 영화/드라마·한국 유튜브 등 한국 콘텐츠로 보이는 것"
        "(화면에 한글 자막·한국 방송 로고가 있거나, 제목이 한국어이고 화면도 그에 맞는 경우). 그 밖은 전부 '해외'. "
        "확신이 없으면 '해외'.\n"
        f"제목(참고용):\n{titles}\n"
        '출력은 JSON 배열만: [{"no": 1, "kind": "실사", "region": "해외"}, …] — 모든 번호를 빠짐없이.')
    part = types.Part.from_bytes(data=_sheet(work, batch), mime_type="image/jpeg")
    last = "키 없음"
    for attempt in range(len(build_pack._keys()) * len(build_pack.MODELS) or 1):
        key = build_pack._next_key()
        if not key:
            break
        model = build_pack.MODELS[(attempt // max(len(build_pack._keys()), 1)) % len(build_pack.MODELS)]
        try:
            resp = build_pack._client(key).models.generate_content(
                model=model, contents=[prompt, part],
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            rows = json.loads(resp.text)
            out = {}
            for r in rows:
                k = int(r["no"]) - 1
                if 0 <= k < len(batch) and r.get("kind") in KINDS and r.get("region") in REGIONS:
                    out[batch[k]["id"]] = {"kind": r["kind"], "region": r["region"], "by": "gemini"}
            if len(out) == len(batch):
                return out
            last = f"{model}: 답이 {len(out)}/{len(batch)}개뿐"
        except Exception as e:  # 다음 키·모델로. 마지막 오류는 남긴다
            last = f"{model}: {e!r}"[:300]
            if any(c in last for c in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                time.sleep(4)
    raise RuntimeError("Gemini 실패 — " + last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    serve.WORK = work
    path = os.path.join(work, "tags.json")
    tags = {} if a.redo else build_pack._load(path, {})
    todo = [it for it in serve.items() if not it["deleted"] and it["id"] not in tags and _thumb(work, it["id"])]
    fails = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            tags.update(classify(work, batch))
            build_pack._save(path, tags)
        except Exception as e:
            fails += len(batch)
            print(f"[실패] {batch[0]['id']} 외 {len(batch) - 1}개: {e}", file=sys.stderr)
        print(f"{min(i + BATCH, len(todo))}/{len(todo)}", flush=True)
    done = [t for t in tags.values()]
    print(f"대상 {len(todo)} · 실패 {fails} · 누적 {len(tags)} "
          f"(국내 {sum(t['region'] == '국내' for t in done)} / 해외 {sum(t['region'] == '해외' for t in done)} · "
          f"실사 {sum(t['kind'] == '실사' for t in done)} / 애니 {sum(t['kind'] == '애니' for t in done)})")


if __name__ == "__main__":
    main()
