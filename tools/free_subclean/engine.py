# -*- coding: utf-8 -*-
"""무료 자막 지우기 — 회원 PC GPU + LaMa(Apache-2.0). 자리(spot)는 회원 Claude 가 그림을 보고 정하고, 글자 모양은 여기서 프레임마다 찾는다 (관제 301).

실측(11-01, RTX 3060, 720×1280): 장당 0.1~0.15초 · GPU 메모리 0.5GB. 작은 자막은 VMake 와 비슷, 복잡한 배경의 큰 글자는 뭉개진다.
지시서·실행기는 무거운 라이브러리를 몰라도 되게, torch 는 전용 가상환경(HOME/v)에서 이 파일을 다른 프로세스로 돌린다.
    py tools/free_subclean/engine.py install                   # 가상환경·모델 설치(약 3GB 내려받기)
    py tools/free_subclean/engine.py check
spot = {"bands":[{"y0":0.74,"y1":0.81,"big":false}], "emoji":[[x0,x1,y0,y1]]} — 전부 화면 비율(0~1). big = 테두리 있는 큰 글자.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home() / ".shortem" / "free_subclean"
MARK = HOME / "ready.json"
TORCH_INDEX = "https://download.pytorch.org/whl/cu126"
MODEL_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
CHECK = "import torch,cv2;assert torch.cuda.is_available();print(torch.cuda.get_device_name(0))"


def py_path() -> Path:
    v = os.environ.get("SHORTEM_FREE_PY")
    return Path(v) if v else HOME / "v" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def installed() -> bool:
    """이 PC 에서 무료 엔진을 쓸 수 있나 — 설치 표식(또는 시험용 SHORTEM_FREE_PY)만 본다. 판단 주인 = vmake_clean.ready."""
    return py_path().exists() and (MARK.exists() or bool(os.environ.get("SHORTEM_FREE_PY")))


def model_path() -> Path:
    return HOME / "big-lama.pt"


def install(log=print) -> dict:
    HOME.mkdir(parents=True, exist_ok=True)
    if not py_path().exists():
        subprocess.run([sys.executable, "-m", "venv", str(HOME / "v")], check=True, stdin=subprocess.DEVNULL)
    pip = [str(py_path()), "-m", "pip", "-q", "install"]
    subprocess.run(pip + ["torch", "--index-url", TORCH_INDEX], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(pip + ["numpy", "opencv-python-headless"], check=True, stdin=subprocess.DEVNULL)
    if not model_path().exists():
        log("모델 내려받는 중")
        tmp = model_path().with_suffix(".part")
        subprocess.run([str(py_path()), "-c", f"import urllib.request as u;u.urlretrieve({MODEL_URL!r},{str(tmp)!r})"], check=True, stdin=subprocess.DEVNULL)
        tmp.replace(model_path())
    r = subprocess.run([str(py_path()), "-c", CHECK], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return {"ok": False, "why": "NVIDIA GPU 를 쓸 수 없어요", "detail": r.stderr[-300:]}
    MARK.write_text(json.dumps({"gpu": r.stdout.strip()}, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "gpu": r.stdout.strip()}


def clean_file(src: Path, dst: Path, spot: dict, timeout: int = 1800) -> dict:
    """영상 한 조각을 지운다(소리 없음 출력). 돈 0. 실패하면 RuntimeError."""
    r = subprocess.run([str(py_path()), str(Path(__file__).resolve()), "_run", str(src), str(dst), json.dumps(spot)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "")[-300:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def _run(src: str, dst: str, spot: dict) -> dict:
    import time
    import cv2
    import numpy as np
    import torch
    d = torch.device("cuda")
    mp = model_path()
    net = torch.jit.load(str(mp), map_location=d).eval()
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    bands = spot.get("bands") or []
    emo = spot.get("emoji") or []
    t0 = time.time()

    def mask(f):
        h, w = f.shape[:2]
        m = np.zeros((h, w), "uint8")
        for b in bands:
            a, e = int(b["y0"] * h), int(b["y1"] * h)
            g = cv2.cvtColor(f[a:e], cv2.COLOR_BGR2GRAY)
            t = ((cv2.morphologyEx(g, cv2.MORPH_TOPHAT, ker) > 40) * 255).astype("uint8")
            n, lab, s, _ = cv2.connectedComponentsWithStats(t)
            for k in range(1, n):
                if s[k, 4] < 10:
                    t[lab == k] = 0
            if b.get("big"):       # 테두리까지 — 안쪽 글자만 지우면 검은 덩어리가 남는다(양배추 편 실측)
                t = cv2.dilate(t, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
            m[a:e] = np.maximum(m[a:e], t)
        for x0, x1, y0, y1 in emo:  # 색 이모지는 지정한 자리에서만 — 띠 전체에 걸면 제품의 빨간 버튼까지 지운다(슬리퍼 편 실측)
            a, e, c, r = int(y0 * h), int(y1 * h), int(x0 * w), int(x1 * w)
            hs = cv2.cvtColor(f[a:e, c:r], cv2.COLOR_BGR2HSV)
            m[a:e, c:r] = np.maximum(m[a:e, c:r], ((hs[..., 1] > 110) & (hs[..., 2] > 100)) * 255)
        return m

    def fill(im, mk):
        pd = lambda x: cv2.copyMakeBorder(x, 0, (8 - x.shape[0] % 8) % 8, 0, (8 - x.shape[1] % 8) % 8, cv2.BORDER_REFLECT)
        i = torch.from_numpy(pd(im[:, :, ::-1].copy()) / 255.).permute(2, 0, 1)[None].float().to(d)
        k = torch.from_numpy((pd(mk) > 0) * 1.)[None, None].float().to(d)
        with torch.no_grad():
            o = net(i, k)[0].permute(1, 2, 0).cpu().numpy()
        o = (o.clip(0, 1) * 255).astype("uint8")[:im.shape[0], :im.shape[1], ::-1]
        a = im.copy()
        a[mk > 0] = o[mk > 0]
        return a

    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(cap.get(3)), int(cap.get(4))
    pipe = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                             "-an", "-c:v", "libx264", "-crf", "15", "-preset", "veryfast", "-pix_fmt", "yuv420p", dst], stdin=subprocess.PIPE)
    n, done = 0, 0                                     # 앞뒤 2프레임 마스크를 합친다 — 놓친 프레임의 번쩍임 방지
    regions = [(max(0, int(b["y0"] * h) - 48), min(h, int(b["y1"] * h) + 48)) for b in bands]
    regions += [(max(0, int(q[2] * h) - 48), min(h, int(q[3] * h) + 48)) for q in emo]

    def flush(f, ms):
        nonlocal done
        u = cv2.dilate(np.maximum.reduce(ms), np.ones((9, 9), "uint8"))
        r = f.copy()
        hit = False
        for a, e in regions:
            if u[a:e].any():
                r[a:e] = fill(r[a:e], u[a:e])
                hit = True
        done += hit
        pipe.stdin.write(r.tobytes())

    buf, base, ptr = [], 0, 0                                   # buf[0] = base 번째 프레임
    while True:
        ok, f = cap.read()
        if ok:
            buf.append((f, mask(f)))
            n += 1
        while ptr < n and (not ok or ptr + 2 < n):
            i = ptr - base
            flush(buf[i][0], [x[1] for x in buf[max(0, i - 2):i + 3]])
            ptr += 1
            if ptr - base > 2:
                buf.pop(0)
                base += 1
        if not ok:
            break
    pipe.stdin.close()
    pipe.wait()
    return {"frames": n, "erased": done, "sec": round(time.time() - t0, 1)}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["_run"]:
        print(json.dumps(_run(a[1], a[2], json.loads(a[3]))))
    elif a[:1] == ["install"]:
        print(json.dumps(install(), ensure_ascii=False))
    elif a[:1] == ["check"]:
        print(json.dumps({"installed": installed(), "py": str(py_path())}, ensure_ascii=False))
    else:
        print(__doc__)
