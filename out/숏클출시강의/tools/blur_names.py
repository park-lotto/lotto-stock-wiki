"""영상·그림 속 채널 이름만 살짝 흐리게(10-30 사장님 "영상에서 나오는 모든 채널의 이름은 살짝 흐리게 / 출처는 지우지 말고").

쓰기: py blur_names.py <public 폴더> <작업.json>
작업.json = {"families": {"이름": [[x0,y0,x1,y1](0~1 비율), ...]}, "files": {"op/c2.mp4": ["TOP_LABEL"], ...},
             "boxes": {"p8/phone.mp4": [[t0, t1, x0, y0, x1, y1](픽셀), ...]}}
원본은 <public>/_pre_blur/ 에 한 번만 보관하고, 매번 원본에서 다시 만든다(두 번 흐려지지 않게).
흐림 세기 = 상자 높이의 18%(최소 3) 가우시안 — 글자는 못 읽고 자리는 보이는 정도.
"""
import json, os, shutil, subprocess, sys

PUB, CFG = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
BK = os.path.join(PUB, "_pre_blur")


def size(p):
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", p],
                          capture_output=True, text=True).stdout.strip().split(",")[:2]
    return int(w), int(h)


def run(rel, boxes):
    """boxes = [(t0|None, t1|None, x, y, w, h)] 픽셀."""
    src = os.path.join(BK, rel); dst = os.path.join(PUB, rel)
    if not os.path.exists(src):
        os.makedirs(os.path.dirname(src), exist_ok=True); shutil.copy(dst, src)
    chain, last = ["[0:v]format=gbrp[rgb]"], "rgb"   # RGB 로 흐린다(yuv420 작은 상자에서 가장자리 초록 줄이 생겼다, 10-30 실측)
    W, H = size(src)
    for k, (t0, t1, x, y, w, h) in enumerate(boxes):
        x, y = max(0, min(x, W - 4)), max(0, min(y, H - 4)); w, h = max(2, min(w, W - x)) & ~1, max(2, min(h, H - y)) & ~1  # 화면 밖으로 나간 상자 자르기
        s = max(3.0, h * 0.18)
        en = f":enable='between(t,{t0},{t1})'" if t0 is not None else ""
        chain.append(f"[rgb{k}]crop={w}:{h}:{x}:{y},gblur=sigma={s:.1f}[b{k}];[{last}][b{k}]overlay={x}:{y}{en}[o{k}]")
        last = f"o{k}"
    n = len(boxes)
    chain[0] = "[0:v]format=gbrp,split=" + str(n + 1) + "[rgb]" + "".join(f"[rgb{k}]" for k in range(n))
    img = rel.lower().endswith((".jpg", ".png"))
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(chain), "-map", f"[{last}]"]
    if img:
        cmd += ["-frames:v", "1", "-update", "1"]
    else:
        cmd += ["-map", "0:a?", "-c:a", "copy", "-c:v", "h264_nvenc", "-cq", "19", "-pix_fmt", "yuv420p"]
    subprocess.run(cmd + [dst], check=True)
    print("흐림", rel, len(boxes), "곳")


for rel, fams in CFG.get("files", {}).items():
    p = os.path.join(BK, rel) if os.path.exists(os.path.join(BK, rel)) else os.path.join(PUB, rel)
    W, H = size(p)
    bx = []
    for fam in fams:
        for x0, y0, x1, y1 in CFG["families"][fam]:
            x, y = int(x0 * W) & ~1, int(y0 * H) & ~1
            bx.append((None, None, x, y, (int((x1 - x0) * W) & ~1) or 2, (int((y1 - y0) * H) & ~1) or 2))
    run(rel, bx)
for rel, bb in CFG.get("boxes", {}).items():
    run(rel, [(t0, t1, int(x0) & ~1, int(y0) & ~1, int(x1 - x0) & ~1, int(y1 - y0) & ~1) for t0, t1, x0, y0, x1, y1 in bb])
