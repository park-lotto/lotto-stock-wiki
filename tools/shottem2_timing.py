# -*- coding: utf-8 -*-
"""숏템하우스 2편 — 씬 대사 txt + TTS mp3 → 문단별 타임코드 JSON

원리:
  ① mp3에서 무음 구간을 검출해 '확실한 문장 경계'(앵커)를 얻는다
  ② 대사 문단을 글자수 비례로 배분해 대략 위치를 잡는다
  ③ 각 문단 경계를 가장 가까운 앵커로 스냅한다(허용 오차 안에서만)

왜 이렇게 하나: 무음 검출만으로는 문단 수와 안 맞고(짧은 쉼은 안 잡힘),
글자수 비례만으로는 실제 낭독과 어긋난다. 둘을 합치면 둘 다 보완된다.

쓰기:
  py tools/shottem2_timing.py <씬txt> <mp3> [출력json]
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def probe_duration(mp3: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp3)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return float(out.stdout.strip())


def detect_anchors(mp3: Path, noise: int = 30, dur: float = 0.25):
    """무음 구간의 중간점 = 문장 경계 후보"""
    out = subprocess.run(
        ["ffmpeg", "-i", str(mp3), "-af",
         "silencedetect=noise=-%ddB:d=%s" % (noise, dur), "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    log = out.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
    anchors = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else s
        anchors.append(round((s + e) / 2, 3))
    return anchors


def paragraphs(txt: Path):
    raw = txt.read_text(encoding="utf-8")
    out = []
    for p in raw.split("\n\n"):
        p = re.sub(r"\[[a-z]+\]", "", p).strip()
        if p:
            out.append(p)
    return out


def build(txt: Path, mp3: Path, tol: float = 1.1):
    total = probe_duration(mp3)
    anchors = detect_anchors(mp3)
    paras = paragraphs(txt)

    # 글자수(공백 제외) 비례 누적
    lens = [len(re.sub(r"\s", "", p)) for p in paras]
    tot = sum(lens)
    bounds = [0.0]
    acc = 0
    for n in lens[:-1]:
        acc += n
        bounds.append(round(total * acc / tot, 3))
    bounds.append(round(total, 3))

    # 앵커 스냅 — 단조 증가를 깨지 않는 범위에서만
    snapped = [0.0]
    used = set()
    for i in range(1, len(bounds) - 1):
        b = bounds[i]
        cand = [a for a in anchors
                if abs(a - b) <= tol and a > snapped[-1] + 0.25 and a not in used]
        if cand:
            best = min(cand, key=lambda a: abs(a - b))
            used.add(best)
            snapped.append(best)
        else:
            snapped.append(max(b, snapped[-1] + 0.25))
    snapped.append(round(total, 3))

    segs = []
    for i, p in enumerate(paras):
        segs.append({
            "i": i,
            "start": round(snapped[i], 3),
            "end": round(snapped[i + 1], 3),
            "dur": round(snapped[i + 1] - snapped[i], 3),
            "f_start": int(round(snapped[i] * 30)),
            "f_dur": int(round((snapped[i + 1] - snapped[i]) * 30)),
            "snapped": snapped[i] in used,
            "text": p.replace("\n", " "),
        })
    return {
        "audio": mp3.name,
        "total": round(total, 3),
        "total_frames": int(round(total * 30)),
        "anchors": anchors,
        "segments": segs,
    }


if __name__ == "__main__":
    txt, mp3 = Path(sys.argv[1]), Path(sys.argv[2])
    data = build(txt, mp3)
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else txt.with_suffix(".timing.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("%s  %.2fs  %d문단  앵커 %d개" %
          (out.name, data["total"], len(data["segments"]), len(data["anchors"])))
    for s in data["segments"]:
        print("  %6.2f–%6.2f  %5.2fs %s %s" %
              (s["start"], s["end"], s["dur"], "*" if s["snapped"] else " ", s["text"][:38]))
