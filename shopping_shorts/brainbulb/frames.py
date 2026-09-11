# -*- coding: utf-8 -*-
"""컷별 화면(프레임) 조립 — 검은 캔버스 + 슬롯(26,469,1028×786)에 사진(cover 크롭) 또는 밈(높이 맞춤 가운데).

볼케이노 render_frames/vconcat 구조를 따르되 정지 컷 1장씩만 만든다(흔들림 없음이 실측). 카드 구간은 card_img 슬롯 사진.
사진 크롭은 MVP로 가운데 cover — 볼케이노의 피사체 선택(contain_selected)은 3단계(프레임비전).
"""
import os

from PIL import Image

from . import spec


def _cover(im, w, h):
    sw, sh = im.size
    s = max(w / sw, h / sh)
    im = im.resize((max(1, round(sw * s)), max(1, round(sh * s))), Image.LANCZOS)
    x = (im.width - w) // 2; y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _contain_h(im, h):
    sw, sh = im.size
    s = h / sh
    return im.resize((max(1, round(sw * s)), h), Image.LANCZOS)


def compose(src, out_path, *, kind="img"):
    """src 이미지 → 1080×1920 검은 캔버스 위 슬롯에 배치한 jpg"""
    canvas = Image.new("RGB", (spec.CANVAS_W, spec.CANVAS_H), (0, 0, 0))
    if src and os.path.exists(src):
        im = Image.open(src).convert("RGBA")
        if kind == "meme":
            im = _contain_h(im, spec.SLOT_H)
            if im.width > spec.SLOT_W:
                im = _cover(im, spec.SLOT_W, spec.SLOT_H)
            x = spec.SLOT_X + (spec.SLOT_W - im.width) // 2
            canvas.paste(im, (x, spec.SLOT_Y), im)
        else:
            im = _cover(im, spec.SLOT_W, spec.SLOT_H)
            canvas.paste(im.convert("RGB"), (spec.SLOT_X, spec.SLOT_Y))
    canvas.save(out_path, "JPEG", quality=92)
    return out_path


def meme_path(emotion, meme_dir):
    if not meme_dir or not emotion:
        return None
    n = spec.MEME_FILE.get(emotion)
    if n:
        p = os.path.join(meme_dir, f"{n}.png")
        if os.path.exists(p):
            return p
    # 매핑 없는 감정(기타·만족·피곤): 팩 첫 파일로 폴백
    files = sorted(f for f in os.listdir(meme_dir) if f.lower().endswith(".png")) if os.path.isdir(meme_dir) else []
    return os.path.join(meme_dir, files[0]) if files else None


def build(workdir, timing, script, images, *, meme_dir=None, card_img=None, log=print):
    """→ {"list": ffconcat 경로, "frames": [...], "timeline": [{i, t, d, kind, src}]}"""
    d = os.path.join(workdir, "slot")
    os.makedirs(d, exist_ok=True)
    groups = script["groups"]
    timeline, entries = [], []
    # 카드
    ci = card_img or next((g["img"] for g in groups if isinstance(g.get("img"), int)), None)
    card_src = images.get(str(ci)) if ci is not None else None
    p = compose(card_src, os.path.join(d, "intro.jpg"))
    entries.append((p, timing["card_end"])); timeline.append({"i": 0, "t": 0, "d": timing["card_end"], "kind": "card", "src": card_src})
    memes = 0
    for g, tg in zip(groups, timing["groups"]):
        if g.get("meme"):
            src = meme_path(g["meme"], meme_dir); kind = "meme"; memes += bool(src)
        else:
            src = images.get(str(g.get("img"))); kind = "img"
        p = compose(src, os.path.join(d, f"g{tg['i']:02d}.jpg"), kind=kind)
        entries.append((p, tg["d"])); timeline.append({"i": tg["i"], "t": tg["t"], "d": tg["d"], "kind": kind, "src": src})
    # 마지막 컷은 꼬리 0.1까지 유지
    entries[-1] = (entries[-1][0], round(entries[-1][1] + spec.TAIL_SEC, 3))
    lst = os.path.join(workdir, "vconcat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        fh.write("ffconcat version 1.0\n")
        for path, dur in entries:
            rel = os.path.relpath(path, workdir).replace("\\", "/")
            fh.write(f"file '{rel}'\nduration {dur:.3f}\n")
        fh.write(f"file '{os.path.relpath(entries[-1][0], workdir).replace(chr(92), '/')}'\n")   # concat 마지막 duration 적용용
    log(f"[brainbulb.frames] 프레임 {len(entries)}장 (사진 {sum(1 for t in timeline if t['kind']=='img' and t['src'])}, 밈 {memes})")
    return {"list": lst, "frames": [e[0] for e in entries], "timeline": timeline}
