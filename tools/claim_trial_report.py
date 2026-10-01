"""주장 번호 시험 2단계 집계·비교 시트(로컬). claim_trial_video.py 가 서버 /tmp/claimv_<job>/ 에 남긴 것을 받아 온 뒤:
  py tools/claim_trial_report.py <받아온 폴더들의 부모>
→ 판정(후보/완성본/같음)·해결 단계 집계 + job마다 '완성본 vs 후보' 비교 시트(sheet_<job>.jpg).
★판정은 버텍스가 A/B 무작위로 본 것이다 — 사람이 표본을 눈으로 확인해야 끝이다(0순위-A1).
"""
import collections
import glob
import json
import os
import sys


def sheet(d, r, out):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 18)
    fb = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 19)
    H = 180
    blocks = []
    for row in r.get("judged") or []:
        ims = []
        for key in ("final_strip", "cand_strip"):
            p = row.get(key)
            p = os.path.join(d, os.path.basename(p)) if p else None
            if p and os.path.exists(p):
                im = Image.open(p)
                ims.append(im.resize((int(im.width * H / im.height), H)))
            else:
                ims.append(None)
        w = max([im.width for im in ims if im] + [400]) + 150
        blk = Image.new("RGB", (w, 34 + 2 * (H + 8) + 24), "white")
        dr = ImageDraw.Draw(blk)
        dr.text((6, 6), "[%d] %s (%.1f초)" % (row["k"], row["text"][:60], row["need"]), fill="black", font=fb)
        y = 34
        for lab, im, col in (("완성본", ims[0], "#c00"), ("후보 #" + ",".join(map(str, row["cand"][:4])), ims[1], "#060")):
            dr.text((6, y + H // 2 - 10), lab, fill=col, font=f)
            if im:
                blk.paste(im, (140, y))
            else:
                dr.text((150, y + H // 2 - 10), "(후보 없음 %s)" % (row.get("unlisted") or ""), fill="#888", font=f)
            y += H + 8
        dr.text((6, y), "판정: %s — %s | %s" % (row.get("verdict", "-"), row.get("why", ""), row["how"]),
                fill="#036", font=f)
        blocks.append(blk)
    if not blocks:
        return None
    W = max(b.width for b in blocks)
    img = Image.new("RGB", (W, sum(b.height + 6 for b in blocks)), "#ccc")
    y = 0
    for b in blocks:
        img.paste(b, (0, y))
        y += b.height + 6
    img.save(out, "JPEG", quality=82)
    return out


def main(root):
    tot_v, tot_h, tot_c = collections.Counter(), collections.Counter(), collections.Counter()
    for d in sorted(glob.glob(os.path.join(root, "claimv_*"))):
        p = os.path.join(d, "result.json")
        if not os.path.exists(p):
            continue
        r = json.load(open(p, encoding="utf-8"))
        rows = r.get("judged") or []
        v = collections.Counter(x.get("verdict", "판정없음") for x in rows)
        h = collections.Counter(x["how"] for x in rows)
        prob = [c for c in r["claims"] if c.get("kind") == "문제"]
        tot_v.update(v)
        tot_h.update(h)
        tot_c["컷"] += len(r["cuts"])
        tot_c["주장붙은컷"] += sum(1 for c in r["cuts"] if c["claims"])
        tot_c["문장(장면필요)"] += len(rows)
        tot_c["목록밖"] += sum(1 for x in rows if x.get("unlisted"))
        print("%s %-22s 컷%3d 주장%2d(문제%d) 문장%2d | 판정 %s | 해결 %s | %.0fs 호출%d" % (
            r["job"], (r.get("product") or "")[:22], len(r["cuts"]), len(r["claims"]), len(prob), len(rows),
            dict(v), dict(h), r["secs"], r["calls"]))
        sheet(d, r, os.path.join(root, "sheet_%s.jpg" % r["job"]))
    print("\n합계 판정:", dict(tot_v))
    print("합계 해결 단계:", dict(tot_h))
    print("합계:", dict(tot_c))


if __name__ == "__main__":
    main(sys.argv[1])
