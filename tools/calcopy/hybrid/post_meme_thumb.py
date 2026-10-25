# -*- coding: utf-8 -*-
"""납품된 하이브리드 완성본 고치기 — 짤 팝업 1개 + 맨 앞 2프레임 썸네일 카드 (관제 097, 2026-10-24 사장님).

사장님 10-24 숏템리폿 3편: "중요한 부분에 짤 한 개 정도 넣고, 맨 앞 썸네일은 썰템홈샷·잇템로그에서 하는 대로 그대로 적용".
- 썸네일 판정(3안·좋은 조건·축) 주인 = thumb_rule.check · 그리기 장치(원·화살표·?·글·꼬리표) = thumb.py 의 것을 그대로 부른다.
  다른 점은 장면 하나 — 렌더 컷 조각이 정리돼 없으니 **완성본 그 프레임**(제목 띠 포함 1080×1920)에서 뽑는다(= 본편에 실제로 나온 장면, 낚시 없음).
- 짤 = 짤 팩(C:/숏템_칼카피/packs/meme/meme_pack) 토막을 장면 창 위쪽에 흰 테 팝업(0.15초 커짐)으로 — 아래 자막은 가리지 않는다. 효과음 1발 같이.
- 맨 앞 2프레임 = thumb.THUMB_FRAMES. 음량은 끝에 다시 재서 TP ≤ -1.5 를 지킨다.

  py tools/calcopy/hybrid/post_meme_thumb.py thumbs <fix.json>   # thumb/A·B·C.jpg + 시트.jpg, pick 무작위 고정
  py tools/calcopy/hybrid/post_meme_thumb.py apply  <fix.json>   # 짤·효과음·카드 입힌 out 영상 + 1초 시트

fix.json = {"video": 원 완성본, "out": 새 완성본, "ep": 편 번호(꼬리표 ㅋㅋ/ㅎㅎ), "window": [0,560,1080,1360],
            "thumb": {"options": [{id, axis, mood, why, t(완성본 초 — 제목 띠), file?/ss?/crop?(자막 없는 창 장면 — 본편이 쓴 원본 그 초), zoom?[x,y,w,h 창 안], circle?, arrow?, q?, text[{lines,xy,px}]}], "pick"?},
            "memes": [{"file", "ss", "dur", "t"(완성본에 뜨는 초), "crop"?[x,y,w,h], "width"?(780), "cy"?(창 안 세로 중심 450), "why",
                       "sfx"?: 파일, "sfx_db"?: -8}]}
좌표: 썸네일 circle·q·text·arrow 는 **1080×1920 전체 화면** 기준(제목 띠 0~560 포함).
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import thumb as TH  # noqa: E402
from tools.calcopy.hybrid import thumb_rule  # noqa: E402
from tools.calcopy.hybrid.render_bench import _font  # noqa: E402
from tools.calcopy.engine.encoder import venc  # noqa: E402 — 인코더 주인(GPU 있으면 NVENC, 화질 같게, 98 #79)
from tools.calcopy.engine import encoder as ENC  # noqa: E402

W, H = 1080, 1920


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _save(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def frame_at(video, t: float):
    from PIL import Image
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    if len(raw) != W * H * 3:
        raise SystemExit(f"프레임을 못 뽑음: {video} @{t}")
    return Image.frombytes("RGB", (W, H), raw)


def card(fix: dict, opt: dict, out: Path) -> Path:
    from PIL import Image, ImageDraw
    im = frame_at(fix["video"], float(opt["t"])).convert("RGBA")
    x0, y0, ww, wh = fix.get("window", [0, 560, 1080, 1360])
    if opt.get("file"):      # 자막 없는 장면 = 본편이 쓴 원본 영상 그 초·크롭(잇템로그 썸네일.json 과 같은 꼴) → 창에만 끼운다
        fx, fy, fw, fh = opt["crop"]
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{float(opt['ss']):.3f}", "-i", opt["file"], "-frames:v", "1", "-vf",
                              f"crop={fw}:{fh}:{fx}:{fy},scale={ww}:{wh}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        if len(raw) != ww * wh * 3:
            raise SystemExit(f"썸네일 장면 프레임을 못 뽑음: {opt['file']} @{opt['ss']}")
        im.paste(Image.frombytes("RGB", (ww, wh), raw).convert("RGBA"), (x0, y0))
    if opt.get("zoom"):
        zx, zy, zw, zh = opt["zoom"]
        win = im.crop((x0, y0, x0 + ww, y0 + wh)).crop((zx, zy, zx + zw, zy + zh)).resize((ww, wh), Image.LANCZOS)
        im.paste(win, (x0, y0))
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for cx, cy, r in opt.get("circle") or []:
        d.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], outline=(0, 0, 0, 200), width=20)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=TH.CARD_RED + (255,), width=13)
    for a, b in opt.get("arrow") or []:
        TH._arrow(d, a, b)
    for cx, cy, px in opt.get("q") or []:
        TH._shadow_text(lay, (cx, cy), ["?"], _font(TH.CARD_FONT, px), (255, 225, 0), max(8, px // 12))
    tag = TH.mood_tag(Path(f"ep{int(fix.get('ep', 1)):02d}"), opt.get("mood"))
    for i, tx in enumerate(opt.get("text") or []):
        lines = list(tx["lines"])
        if i == 0 and tag:
            lines[-1] = f"{lines[-1]} {tag}"
        px = tx.get("px", 120)
        while px > 70 and max(_font(tx.get("font", TH.CARD_FONT), px).getlength(s) for s in lines) > 1000:
            px -= 4
        TH._shadow_text(lay, tx["xy"], lines, _font(tx.get("font", TH.CARD_FONT), px),
                        tuple(tx.get("color", TH.CARD_RED)), tx.get("stroke", 11), rot=tx.get("rot", 0.0))
    im.alpha_composite(lay)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, quality=94)
    return out


def thumbs(fix_path: Path) -> dict:
    from PIL import Image, ImageDraw
    fix = _load(fix_path)
    spec = fix["thumb"]
    bad = thumb_rule.check({**spec, "options": [{**o, "part": 0} for o in spec["options"]]}, n_parts=1)
    if bad:
        raise SystemExit("썸네일 3안 검사 실패:\n- " + "\n- ".join(bad))
    d = fix_path.parent / "thumb"
    outs = [(o, card(fix, o, d / f"{o['id']}.jpg")) for o in spec["options"]]
    tw, th = 432, 768
    sheet = Image.new("RGB", (len(outs) * (tw + 16) + 16, th + 80), (24, 24, 24))
    dd = ImageDraw.Draw(sheet)
    for i, (o, p) in enumerate(outs):
        sheet.paste(Image.open(p).resize((tw, th), Image.LANCZOS), (16 + i * (tw + 16), 64))
        dd.text((16 + i * (tw + 16), 12), f"{o['id']}  {o.get('why', '')}"[:40], font=_font("Pretendard-Bold.otf", 30), fill=(255, 230, 0))
    sheet.save(d / "시트.jpg", quality=90)
    if not spec.get("pick"):
        spec["pick"] = random.choice([o["id"] for o in spec["options"]])
        _save(fix_path, fix)
    print(json.dumps({"sheet": str(d / "시트.jpg"), "pick": spec["pick"]}, ensure_ascii=False))
    return fix


def apply(fix_path: Path) -> None:
    fix = _load(fix_path)
    pick = fix["thumb"].get("pick")
    if not pick:
        raise SystemExit("thumbs 먼저(pick 없음)")
    jpg = fix_path.parent / "thumb" / f"{pick}.jpg"
    x0, y0, ww, wh = fix.get("window", [0, 560, 1080, 1360])
    memes = fix.get("memes") or []
    if not 1 <= len(memes) <= 2:
        raise SystemExit("짤은 1개(많아야 2개) — 사장님 '짤 한 개 정도'")
    ins, fc, a_lbl = ["-i", fix["video"], "-loop", "1", "-i", str(jpg)], [], []
    v = "[0:v]"
    for k, m in enumerate(memes):
        T, du, wd = float(m["t"]), float(m["dur"]), int(m.get("width", 780))
        cy = y0 + int(m.get("cy", 450))
        ins += ["-ss", f"{float(m['ss']):.3f}", "-t", f"{du:.3f}", "-i", m["file"]]
        n = 2 + k
        crop = "crop={2}:{3}:{0}:{1},".format(*m["crop"]) if m.get("crop") else ""
        fc.append(f"[{n}:v]{crop}scale={wd - 24}:-2,pad=iw+24:ih+24:12:12:white,format=rgba,setpts=PTS-STARTPTS+{T}/TB,"
                  f"scale=w='iw*min(1,0.55+0.45*(t-{T})/0.15)':h=-2:eval=frame[m{k}]")
        fc.append(f"{v}[m{k}]overlay=x='(W-w)/2':y='{cy}-h/2':eof_action=pass:eval=frame:enable='between(t,{T},{T + du})'[v{k}]")
        v = f"[v{k}]"
    fc.append(f"[1:v]scale={W}:{H},setsar=1[tc];{v}[tc]overlay=0:0:enable='lt(n,{TH.THUMB_FRAMES})':shortest=1,format=yuv420p[vout]")
    a_in = ["[0:a]"]
    for k, m in enumerate(memes):
        if m.get("sfx"):
            n = sum(1 for x in ins if x == "-i")       # 입력 번호 = 지금까지 -i 개수
            ins += ["-i", m["sfx"]]
            ms = int(float(m["t"]) * 1000)
            fc.append(f"[{n}:a]volume={float(m.get('sfx_db', -8))}dB,adelay={ms}|{ms}[s{k}]")
            a_in.append(f"[s{k}]")
    fc.append(f"{''.join(a_in)}amix=inputs={len(a_in)}:normalize=0:duration=first,alimiter=limit=0.82:level=false[aout]")
    out = Path(fix["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    ENC.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
                    *venc(16, "medium"), "-r", "30", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(out)], check=True)
    sheet = out.with_name(out.stem + "_sheet_1s.jpg")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-vf", "fps=2,scale=216:-1,tile=8x9", "-frames:v", "1", str(sheet)], check=True)
    ln = subprocess.run(["ffmpeg", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True,
                        encoding="utf-8", errors="replace").stderr
    tail = ln[ln.rfind("Summary:"):]
    print(tail)
    print(json.dumps({"out": str(out), "sheet": str(sheet)}, ensure_ascii=False))


if __name__ == "__main__":
    cmd, p = sys.argv[1], Path(sys.argv[2])
    {"thumbs": thumbs, "apply": apply}[cmd](p)
