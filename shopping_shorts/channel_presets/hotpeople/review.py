# -*- coding: utf-8 -*-
"""검수 — 나온 mp4를 실제로 잰다. 길이 · 컷마다 슬롯이 비지 않았나 · 자막 잉크가 있나 · 자막이 화면 밖으로 안 나갔나.
눈으로 볼 시트(review.png: 컷마다 가운데 프레임)도 만든다 — 숫자 통과 ≠ 결과물 통과(0순위-A1).
"""
import json
import os
import subprocess

import numpy as np
from PIL import Image

from . import spec


def _frame(mp4, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) != spec.CANVAS_W * spec.CANVAS_H * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(spec.CANVAS_H, spec.CANVAS_W, 3)


def slot_cuts(mp4):
    """완성 mp4 슬롯의 컷 시각(scene>0.3, 0.2초 이후) — tools/hotpeople/measure/cuts.py 와 같은 자."""
    vf = f"crop={spec.SLOT_W}:{spec.SLOT_H}:{spec.SLOT_X}:{spec.SLOT_Y},select='gt(scene,0.3)',metadata=print:file=-"
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", vf, "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stdout
    return [float(l.split("pts_time:")[1]) for l in r.splitlines() if "pts_time:" in l and float(l.split("pts_time:")[1]) > 0.2]


def inner_cuts(mp4, secs, tol=0.1, cuts=None):
    """★칼카피 1 결과물 검사 — 자막 경계에서 tol 초 넘게 떨어진 컷(= 자막 안에서 화면이 바뀐 것)의 시각 목록."""
    cuts = slot_cuts(mp4) if cuts is None else cuts
    bounds, t = [], 0.0
    for s in secs:
        t += s
        bounds.append(t)
    return [round(c, 2) for c in cuts if min(abs(c - b) for b in bounds) > tol]


def slot_frame(mp4, t):
    """완성 mp4 t초의 슬롯만(BGR). ★faces_text.py 와 같은 자리에서 자른다(ffmpeg crop → 같은 픽셀)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", "-vf",
                          f"crop={spec.SLOT_W}:{spec.SLOT_H}:{spec.SLOT_X}:{spec.SLOT_Y}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, timeout=120).stdout
    if len(raw) != spec.SLOT_W * spec.SLOT_H * 3:
        raise RuntimeError(f"review.slot_frame: {os.path.basename(mp4)} {t:.2f}s 프레임 실패")
    return np.frombuffer(raw, np.uint8).reshape(spec.SLOT_H, spec.SLOT_W, 3).copy()


def content_rows(mp4, secs, anchor):
    """★완성본 컷마다(가운데 프레임 슬롯) 자로 잰다 → [{i, face, face_h, cx_off, who, sub_like}]. i 는 0부터(자막 번호와 같다).
    anchor = footage 소스 자가 정한 주인공 임베딩 — 완성본 안에서 다시 정하지 않는다(v001처럼 다른 선수가 더 많으면 뒤집힌다)."""
    from shopping_shorts.channelkit import vision
    rows, t = [], 0.0
    for i, s in enumerate(secs):
        lk = vision.look(slot_frame(mp4, t + s / 2))
        t += s
        rows.append({"i": i, "face": lk["face"], "face_h": lk["face_h"], "cx_off": lk["cx_off"],
                     "who": vision.who(lk["box"], lk["emb"], anchor), "sub_like": lk["sub_like"]})
    return rows


def content_gate(rows, subjects, bad_final):
    """★내용 관문의 유일한 판단(칼카피 규칙 7~10 + 장면 검사). rows = content_rows, subjects = 자막마다 rules.subject,
    bad_final = footage 장면 검사 **다시 고른 뒤** 틀린 자막 번호(None = 검사 안 함 → 통과 못 한다).
    → checks 목록. block=False 인 것은 보고만 한다."""
    import statistics as st
    from shopping_shorts.channelkit import vision
    n = max(1, len(rows))
    face = sum(1 for r in rows if r["face"]) / n
    main = [r["i"] for r in rows if r["who"] == vision.WHO_MAIN]
    sub = [r["i"] for r in rows if r["sub_like"]]
    other_main = [r["i"] for r, s in zip(rows, subjects) if s == "main" and r["who"] == vision.WHO_OTHER]
    offs = [abs(r["cx_off"]) for r in rows if r["cx_off"] is not None]
    cx = round(st.median(offs), 3) if offs else None
    vb = None if bad_final is None else len(bad_final) / max(1, len(subjects))
    return [
        {"name": f"⑦ 얼굴 보이는 컷 ≥ {spec.GATE_FACE_VISIBLE_MIN:.0%}", "ok": face >= spec.GATE_FACE_VISIBLE_MIN,
         "got": round(face, 3), "block": True},
        {"name": f"⑧ 자막꼴 박힌 글자 컷 ≤ {spec.GATE_SUBTITLE_LIKE_MAX}", "ok": len(sub) <= spec.GATE_SUBTITLE_LIKE_MAX,
         "got": sub, "block": True},
        {"name": f"⑩ 주인공 자막에 다른 사람 컷 ≤ {spec.GATE_OTHER_ON_MAIN_MAX}", "ok": len(other_main) <= spec.GATE_OTHER_ON_MAIN_MAX,
         "got": other_main, "block": True},
        {"name": f"장면 검사 최종 틀림 ≤ {spec.GATE_VERIFY_BAD_MAX:.0%}", "ok": vb is not None and vb <= spec.GATE_VERIFY_BAD_MAX,
         "got": "검사 안 함" if vb is None else {"ratio": round(vb, 3), "bad": bad_final}, "block": True},
        {"name": f"⑨ 얼굴 중심 편차 중앙 ≤ {spec.FACE_CENTER_MAX} (보고만)", "ok": cx is None or cx <= spec.FACE_CENTER_MAX,
         "got": cx, "block": False},
        {"name": "주인공 보이는 컷 비율 (보고만 — 원본 9편 14~64%, 중앙 32%)", "ok": True,
         "got": {"ratio": round(len(main) / n, 3), "cuts": main}, "block": False},
    ]


def clear_out(wd):
    """렌더 전에 out/ 의 지난 결과(final.mp4·FAILED.json)를 지운다 — 옛 완성본이 새 실패 옆에 남지 않게."""
    for f in ("final.mp4", "FAILED.json"):
        p = os.path.join(wd, "out", f)
        if os.path.exists(p):
            os.remove(p)


def finalize(rep, wd, unchecked_mp4):
    """★out/ 에 무엇을 쓸지의 유일한 판단. 통과 → render/unchecked.mp4 를 out/final.mp4 로 옮긴다.
    막힘 → out/FAILED.json(막은 검사·값)만 쓰고 final.mp4 는 **만들지 않는다**. → final 경로 또는 None."""
    import shutil
    os.makedirs(os.path.join(wd, "out"), exist_ok=True)
    clear_out(wd)
    if rep["ok"]:
        dst = os.path.join(wd, "out", "final.mp4")
        shutil.move(unchecked_mp4, dst)
        return dst
    bad = [c for c in rep["checks"] if not c["ok"] and c.get("block", True)]
    with open(os.path.join(wd, "out", "FAILED.json"), "w", encoding="utf-8") as fh:
        json.dump({"why": [c["name"] for c in bad], "checks": bad, "all_checks": rep["checks"], "sheet": rep.get("sheet"),
                   "unchecked_mp4": unchecked_mp4}, fh, ensure_ascii=False, indent=1)
    return None


def run(mp4, render, wd, script=None, footage=None):
    """검수 → {"ok", "checks", "duration", "sheet", "content"}. ok = block 검사 전부 통과.
    script·footage 가 없으면 내용 관문을 못 돈다 → 그 자체가 막힘(조용히 넘기지 않는다)."""
    checks, frames = [], []
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                    "-of", "json", mp4], capture_output=True, text=True).stdout or "{}")
    dur = float(pr.get("format", {}).get("duration") or 0)
    kinds = [s.get("codec_type") for s in pr.get("streams") or []]
    v = next((s for s in pr.get("streams") or [] if s.get("codec_type") == "video"), {})
    checks.append({"name": "크기 1080x1920", "ok": (v.get("width"), v.get("height")) == (spec.CANVAS_W, spec.CANVAS_H)})
    checks.append({"name": f"길이 {spec.DURATION_MIN:.0f}~{spec.DURATION_MAX:.0f}초", "ok": spec.DURATION_MIN <= dur <= spec.DURATION_MAX, "got": round(dur, 2)})
    checks.append({"name": "소리 트랙", "ok": "audio" in kinds})
    t, blank, noink, overflow = 0.0, [], [], []
    for c in render["cuts"]:
        mid = t + c["sec"] / 2
        t += c["sec"]
        a = _frame(mp4, mid)
        if a is None:
            blank.append(c["i"]); continue
        frames.append(a)
        slot = a[spec.SLOT_Y + 10:spec.SLOT_Y + spec.SLOT_H - 10].astype(int)
        if slot.mean() < 15 or slot.std() < 6:
            blank.append(c["i"])
        band = a[spec.SLOT_Y + spec.SLOT_H:spec.SLOT_Y + spec.SLOT_H + 260]
        if (band.max(axis=2) < 90).mean() < 0.003:
            noink.append(c["i"])
        edge = np.concatenate([band[:, :20], band[:, -20:]], axis=1)
        if (edge.max(axis=2) < 90).mean() > 0.002:
            overflow.append(c["i"])
    checks.append({"name": "슬롯이 빈 컷 0", "ok": not blank, "got": blank})
    checks.append({"name": "자막 없는 컷 0", "ok": not noink, "got": noink})
    checks.append({"name": "자막 화면 밖 0", "ok": not overflow, "got": overflow})
    cuts = slot_cuts(mp4)
    inner = inner_cuts(mp4, [c["sec"] for c in render["cuts"]], cuts=cuts)
    # 자막 하나 = 컷 하나라 컷 수는 자막 수를 못 넘는다 — 넘으면 경계 근처 이중 컷(빈 첫 프레임 등, v3 1차 37컷)
    checks.append({"name": "컷 수 ≤ 자막 수", "ok": len(cuts) + 1 <= len(render["cuts"]), "got": len(cuts) + 1})
    checks.append({"name": f"자막 안 컷 {spec.SUB_INNER_CUTS_MAX} 이하", "ok": len(inner) <= spec.SUB_INNER_CUTS_MAX, "got": inner})
    # ── 내용 관문 (우상혁 v001 사고: 숫자만 보고 내용을 안 봤다) ──
    rows = None
    anchor_p = (footage or {}).get("anchor")
    if script is None or not anchor_p or not os.path.exists(anchor_p):
        checks.append({"name": "내용 관문 실행", "ok": False, "got": f"대본/주인공 임베딩 없음({anchor_p})", "block": True})
    else:
        from . import rules
        rows = content_rows(mp4, [c["sec"] for c in render["cuts"]], np.load(anchor_p))
        subjects = [rules.subject(g) for g in script["groups"]][:len(rows)]
        checks += content_gate(rows, subjects, ((footage or {}).get("verify") or {}).get("bad_final"))
    sheet = None
    if frames:
        from PIL import ImageDraw, ImageFont
        font = ImageFont.truetype(spec.LOGO_NAME_FONT, 20)
        th = [Image.fromarray(f).resize((216, 384)) for f in frames]
        cols = 8
        sh = Image.new("RGB", (cols * 220, ((len(th) + cols - 1) // cols) * 412), "white")
        d = ImageDraw.Draw(sh)
        for i, im in enumerate(th):
            x, y = (i % cols) * 220, (i // cols) * 412
            sh.paste(im, (x, y))
            if rows and i < len(rows):
                r = rows[i]
                from shopping_shorts.channelkit import vision
                bad = r["who"] == vision.WHO_OTHER or r["sub_like"]
                d.text((x + 4, y + 386), f"{i} {r['who']}" + (" 자막" if r["sub_like"] else ""), font=font,
                       fill=(220, 0, 0) if bad else (0, 0, 0))
        os.makedirs(os.path.join(wd, "out"), exist_ok=True)
        sheet = os.path.join(wd, "out", "review.png")
        sh.save(sheet)
    return {"ok": all(c["ok"] for c in checks if c.get("block", True)), "checks": checks, "duration": round(dur, 2),
            "sheet": sheet, "content": rows}
