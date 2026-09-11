"""볼케이노 작업 폴더 → 중립 재료 목록(manifest.json)

볼케이노(volcano MCP)가 렌더 직전에 남긴 파일들을 읽어, 우리 렌더러가 쓰기 좋은
하나의 JSON으로 정리한다. 서버·실행기 코드는 건드리지 않고 **읽기만** 한다.

읽는 것:
  timing.json        컷별 시작(t)·길이(d)·문장·색·역할·이미지 슬롯, 카드 끝 시각, 슬러그
  next_payload.json  제목(title)·오프닝 문장(intro_text)·밈 경로(groups[].meme)·효과음 배치(sfx_plan)
  tts/NN.wav         00 = 오프닝 카드, 01.. = 본문 컷 (timing.groups[i-1] ↔ tts/{i:02d}.wav)
  img43/NN.png       이미지 슬롯(1부터)

쓰는 법:
  py tools/volcano_bridge/extract.py <볼케이노 작업폴더> [-o manifest.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _abs(workdir: str, rel: str) -> str:
    return os.path.normpath(os.path.join(workdir, rel)).replace("\\", "/")


def extract(workdir: str) -> dict:
    workdir = os.path.abspath(workdir)
    timing = json.load(open(os.path.join(workdir, "timing.json"), encoding="utf-8"))
    payload = json.load(open(os.path.join(workdir, "next_payload.json"), encoding="utf-8"))

    groups_t = timing["groups"]
    groups_p = payload.get("groups") or []
    if len(groups_p) != len(groups_t):
        raise SystemExit(f"컷 수가 다르다: timing {len(groups_t)} vs payload {len(groups_p)}")

    imgdir = payload.get("imgdir") or "img43"
    images = {}
    img_root = os.path.join(workdir, imgdir)
    if os.path.isdir(img_root):
        for f in sorted(os.listdir(img_root)):
            stem, ext = os.path.splitext(f)
            if ext.lower() in (".png", ".jpg", ".jpeg") and stem.isdigit():
                images[int(stem)] = _abs(workdir, f"{imgdir}/{f}")

    sfx_by_cut = {}
    for s in payload.get("sfx_plan") or []:
        sfx_by_cut[int(s["cut"])] = {"file": s["file"].replace("\\", "/"), "gain": float(s.get("gain", 1.0))}

    cuts = []
    for gt, gp in zip(groups_t, groups_p):
        i = int(gt["i"])
        wav = _abs(workdir, f"tts/{i:02d}.wav")
        if not os.path.exists(wav):
            raise SystemExit(f"음성 파일 없음: {wav}")
        meme = gp.get("meme")
        img_slot = gt.get("img")
        cut = {
            "i": i,
            "start": round(float(gt["t"]), 3),
            "dur": round(float(gt["d"]), 3),
            "text": gt.get("text") or gp.get("text"),
            "lines": gt.get("lines") or [gt.get("text")],
            "color": gt.get("color") or gp.get("color"),
            "role": gt.get("role") or gp.get("role"),
            "wav": wav,
            "image": images.get(int(img_slot)) if img_slot else None,
            "image_slot": int(img_slot) if img_slot else None,
            "meme": _abs(workdir, meme) if meme else None,
            "meme_emotion": gp.get("meme_emotion"),
            # sfx_plan의 cut 번호는 0=카드, 1..=본문 컷 i 와 같다
            "sfx": sfx_by_cut.get(i),
        }
        if cut["image"] is None and cut["meme"] is None:
            raise SystemExit(f"컷 {i}: 이미지도 밈도 없다")
        cuts.append(cut)

    card_img = timing.get("card_img") or payload.get("card_img") or 1
    manifest = {
        "source": "volcano",
        "workdir": workdir.replace("\\", "/"),
        "slug": timing.get("slug") or payload.get("slug"),
        "title": payload.get("title") or {},
        "total": float(timing["total"]),
        "card": {
            "start": 0.0,
            "dur": round(float(timing["card_end"]), 3),
            "text": payload.get("intro_text") or (payload.get("title") or {}).get("card"),
            "wav": _abs(workdir, "tts/00.wav"),
            "image": images.get(int(card_img)),
            "sfx": sfx_by_cut.get(0),
        },
        "cuts": cuts,
        "images": {str(k): v for k, v in images.items()},
        "fonts_dir": _abs(workdir, "fonts"),
    }
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("-o", "--out", default=None, help="저장 경로(기본: <workdir>/bridge/manifest.json)")
    a = ap.parse_args(argv)
    m = extract(a.workdir)
    out = a.out or os.path.join(a.workdir, "bridge", "manifest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(m, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"manifest: {out}  컷 {len(m['cuts'])}  총 {m['total']}s  이미지 {len(m['images'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
