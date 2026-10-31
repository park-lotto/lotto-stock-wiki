# -*- coding: utf-8 -*-
"""방송 강조 자막 결과물 검사(관제 293) — 계산이 아니라 나온 영상 프레임·소리로 본다.

    PYTHONUTF8=1 py -m tools.calcopy.engine.check_broadcast_caption <영상.mp4> <자막.json> [--preset=hot] [--sabotage]

① 자막 시간 안: 글자가 실제로 그려졌고 화면 밖으로 넘치지 않는다(원본 프레임과 차이로 잉크 범위를 잰다)
② 자막 시간 밖: 원본과 그림이 같다 ③ 길이 같다 ④ 소리 패킷이 같다 ⑤ 표식이 남는다
--sabotage = 크기 맞춤을 끄고 돌려 ① 이 실패하는지 본다. 실패가 안 뜨면 이 검사는 아무것도 못 잡는 것이다."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from tools.calcopy.engine import broadcast_caption as BC
from tools.calcopy.engine.ad_mark import _probe

SAFE = 8           # 화면 끝에서 이만큼은 비어야 한다(px)
DIFF = 40          # 잉크로 치는 밝기 차이


def _frame(video, t, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", str(video), "-frames:v", "1", str(dst)], check=True)
    return np.asarray(Image.open(dst).convert("RGB"), dtype=np.int16)


def _dur(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    return float(r.stdout.strip())


def _audio_md5(video):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"], capture_output=True, text=True)
    return r.stdout.strip()


def _ink(a, b):
    m = np.abs(a - b).max(axis=2) > DIFF
    cols = np.where(m.sum(axis=0) > 3)[0]
    rows = np.where(m.sum(axis=1) > 3)[0]
    if not len(cols) or not len(rows):
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1]), int(m.sum())


def check(video, cues, preset="hot"):
    bad = []
    with tempfile.TemporaryDirectory(prefix="bcap_chk_") as tmp:
        t = Path(tmp)
        out = t / "out.mp4"
        BC.render(video, cues, out, preset)
        w, h, comment = _probe(out)
        for i, c in enumerate(cues):
            mid = (c["start"] + c["end"]) / 2
            box = _ink(_frame(video, mid, t / "a.png"), _frame(out, mid, t / "b.png"))
            print(f"자막{i} {c.get('role', 'pop')} {c['text'][:18]!r} 범위 {box}")
            if box is None or box[4] < 2000:
                bad.append(f"자막{i} 안 그려짐")
            elif box[0] < SAFE or box[2] > w - 1 - SAFE or box[1] < SAFE or box[3] > h - 1 - SAFE:
                bad.append(f"자막{i} 화면 끝 넘침 {box[:4]}")
        ts = sorted(c["end"] for c in cues)
        gaps = [x + .4 for x in ts if not any(c["start"] <= x + .4 <= c["end"] for c in cues) and x + .4 < _dur(video)]
        for g in gaps[:3]:
            box = _ink(_frame(video, g, t / "a.png"), _frame(out, g, t / "b.png"))
            if box and box[4] > 2000:
                bad.append(f"{g:.2f}초 자막 밖인데 그림이 다름 {box}")
        d0, d1 = _dur(video), _dur(out)
        print(f"길이 {d0:.3f} → {d1:.3f}")
        if abs(d0 - d1) > .05:
            bad.append("길이 어긋남")
        if _audio_md5(video) != _audio_md5(out):
            bad.append("소리 달라짐")
        if BC.MARK not in comment:
            bad.append("표식 없음")
    return bad


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cues = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    if "--sabotage" in sys.argv:
        BC.MARGIN = -0.6                 # 맞출 폭을 화면보다 넓게 — 넘쳐야 정상
        BC.Sheet.tiles = lambda self, cue: None
    preset = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--preset=")), "hot")
    bad = check(args[0], cues, preset)
    print("문제 없음" if not bad else "문제 %d건: %s" % (len(bad), bad))
    sys.exit(1 if bad else 0)
