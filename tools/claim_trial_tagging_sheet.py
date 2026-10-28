# -*- coding: utf-8 -*-
"""claim_trial_tagging 결과(live/old/new 폴더) → 줄별 프레임 시트 jpg + 요약 (로컬, 카드 051).

    py tools/claim_trial_tagging_sheet.py <부모폴더> <job>
부모폴더 안에 tagtrial_<job>_live / _old / _new 가 있어야 한다(없는 모드는 건너뜀).
시트: 모드마다 한 장 — 줄 글 + 역할 + 고른 컷 프레임(컷당 2장) + 컷 설명.  사람이 보고 줄마다 맞음/틀림을 적는다.
"""
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/malgun.ttf"


def _font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:      # noqa: BLE001
        return ImageFont.load_default()


def render(folder, out_path, h=150):
    d = json.load(io.open(os.path.join(folder, "result.json"), encoding="utf-8"))
    rows = d.get("rows") or []
    f1, f2 = _font(18), _font(13)
    W = 1500
    blocks = []
    for r in rows:
        ims = []
        for p in r.get("frames") or []:
            lp = os.path.join(folder, os.path.basename(p))
            if os.path.exists(lp):
                im = Image.open(lp).convert("RGB")
                ims.append(im.resize((max(1, int(im.width * h / im.height)), h)))
        bh = 26 + h + 18 * max(1, len(r.get("descs") or [])) + 14
        blk = Image.new("RGB", (W, bh), "white")
        dr = ImageDraw.Draw(blk)
        dr.text((6, 4), "[%d] (%s) %s" % (r["i"], r.get("role") or "", (r.get("text") or "")[:70]), fill="black", font=f1)
        x = 6
        for im in ims:
            if x + im.width > W:
                break
            blk.paste(im, (x, 26))
            x += im.width + 4
        y = 26 + h + 2
        for ds in (r.get("descs") or []):
            dr.text((6, y), ds[:150], fill=(60, 60, 60), font=f2)
            y += 18
        blocks.append(blk)
    if not blocks:
        return None
    sheet = Image.new("RGB", (W, sum(b.height + 6 for b in blocks) + 30), (235, 235, 235))
    dr = ImageDraw.Draw(sheet)
    dr.text((6, 6), "%s · %s · 줄 %d · %ss" % (d.get("job"), d.get("mode"), len(rows), d.get("secs")), fill="black", font=f1)
    y = 30
    for b in blocks:
        sheet.paste(b, (0, y))
        y += b.height + 6
    sheet.save(out_path, "JPEG", quality=85)
    return out_path


def main():
    parent, jid = sys.argv[1], sys.argv[2]
    for mode in ("live", "old", "new"):
        folder = os.path.join(parent, "tagtrial_%s_%s" % (jid, mode))
        if not os.path.isdir(folder):
            print(mode, "없음")
            continue
        out = render(folder, os.path.join(parent, "sheet_%s_%s.jpg" % (jid, mode)))
        d = json.load(io.open(os.path.join(folder, "result.json"), encoding="utf-8"))
        print(mode, "→", out, "| 줄", len(d.get("rows") or []), "| 스파인", (d.get("spine") or {}).get("name") if d.get("spine") else "-")
        for r in d.get("rows") or []:
            print("   [%d] %s | %s" % (r["i"], (r.get("text") or "")[:34], " / ".join(x[:38] for x in (r.get("descs") or [])[:3])))


if __name__ == "__main__":
    main()
