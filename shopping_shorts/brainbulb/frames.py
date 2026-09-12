# -*- coding: utf-8 -*-
"""컷별 화면(프레임) 조립 — 검은 캔버스 + 슬롯(26,469,1028×786)에 사진(cover 크롭) 또는 밈(높이 맞춤 가운데).

볼케이노 render_frames/vconcat 구조를 따르되 정지 컷 1장씩만 만든다(흔들림 없음이 실측). 카드 구간은 card_img 슬롯 사진.
사진 크롭은 MVP로 가운데 cover — 볼케이노의 피사체 선택(contain_selected)은 3단계(프레임비전).
"""
import os

from PIL import Image

from . import spec


def _cover(im, w, h, focus=None):
    """슬롯을 꽉 채우도록 키운 뒤 잘라낸다. `focus`가 있으면 **그 점이 화면에 남도록** 잘린다.

    ★가운데로만 자르면 얼굴이 가장자리로 밀린다(실측 2026-09-13 박위 01번: 얼굴이 폭 300 중 x=250).
      focus는 원본 좌표 (cx, cy) — 얼굴 중심을 넣는다. 얼굴은 눈이 위쪽에 오는 게 자연스러워
      세로로는 정가운데가 아니라 **조금 위**(0.42)에 둔다.
    """
    sw, sh = im.size
    s = max(w / sw, h / sh)
    im = im.resize((max(1, round(sw * s)), max(1, round(sh * s))), Image.LANCZOS)
    if focus:
        x = int(round(focus[0] * s - w / 2))
        y = int(round(focus[1] * s - h * 0.42))
    else:
        x = (im.width - w) // 2
        y = (im.height - h) // 2
    x = max(0, min(x, im.width - w))            # 바깥으로 나가면 가장자리에 붙인다
    y = max(0, min(y, im.height - h))
    return im.crop((x, y, x + w, y + h))


def _face_focus(src):
    """사진 속 가장 큰 얼굴의 중심 → (cx, cy). 얼굴이 없거나 못 재면 None(가운데 자르기)."""
    try:
        from . import photos
        box = photos.face_box(src)
    except Exception:  # noqa: BLE001 — 검출이 안 되면 예전처럼 가운데로 자른다
        return None
    if not box:
        return None
    x, y, w, h = box
    return (x + w / 2, y + h / 2)


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
            im = _cover(im, spec.SLOT_W, spec.SLOT_H, focus=_face_focus(src))
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


def _nearest(images, slot):
    """빈 슬롯은 가장 가까운 번호의 사진으로 메운다 — 한 장이 거부돼도 그 컷만 검게 두지 않는다(실측: 미성년자+무기 거부)."""
    if str(slot) in images:
        return images[str(slot)]
    have = sorted(int(k) for k in images)
    if not have or slot is None:
        return None
    return images[str(min(have, key=lambda k: abs(k - int(slot))))]


def build(workdir, timing, script, images, *, meme_dir=None, card_img=None, log=print):
    """→ {"list": ffconcat 경로, "frames": [...], "timeline": [{i, t, d, kind, src}]}"""
    d = os.path.join(workdir, "slot")
    os.makedirs(d, exist_ok=True)
    groups = script["groups"]
    timeline, entries = [], []
    # 카드
    ci = card_img or next((g["img"] for g in groups if isinstance(g.get("img"), int)), None)
    card_src = _nearest(images, ci) if ci is not None else None
    p = compose(card_src, os.path.join(d, "intro.jpg"))
    entries.append((p, timing["card_end"])); timeline.append({"i": 0, "t": 0, "d": timing["card_end"], "kind": "card", "src": card_src})
    memes = 0
    last_img = card_src            # ★직전 컷의 사진 — 빈 컷을 검게 두지 않으려고 들고 간다
    blanks = 0
    for g, tg in zip(groups, timing["groups"]):
        if g.get("meme"):
            src = meme_path(g["meme"], meme_dir); kind = "meme"; memes += bool(src)
        else:
            src = _nearest(images, g.get("img")); kind = "img"
        if not src:
            # ★슬롯 번호가 없는 컷(CHAR·PUNCH 대사)과 밈 팩이 없는 컷은 src가 None이 된다.
            #   그대로 두면 **화면이 통째로 검게** 나간다(실측 2026-09-13 박위 1차: 상영시간의 50%).
            #   볼케이노 골든은 img 없는 컷 5개가 **전부 밈**이라 빈 컷이 애초에 없다.
            #   우리는 대본이 밈 없는 빈 컷을 만들 수 있으므로 직전 사진을 이어서 쓴다.
            src, kind = last_img, "img"
            blanks += 1
        elif kind == "img":
            last_img = src
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
    black = sum(1 for t in timeline if not t["src"])
    log(f"[brainbulb.frames] 프레임 {len(entries)}장 "
        f"(사진 {sum(1 for t in timeline if t['kind']=='img' and t['src'])}, 밈 {memes}"
        + (f", 직전사진으로 메움 {blanks}" if blanks else "")
        + (f", ★검은 화면 {black}" if black else "") + ")")
    return {"list": lst, "frames": [e[0] for e in entries], "timeline": timeline}
