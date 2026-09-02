# -*- coding: utf-8 -*-
"""세그먼트별 대표 프레임 추출 — C안(이미지 보고 고르기)의 재료.

기존 seg_thumbs가 25장뿐이라 나머지는 원본 mp4에서 직접 뽑는다.
구간 중앙 시각의 프레임 1장. 모델에 넣을 것이므로 작게(가로 384) 줄인다.
"""
import io, json, os, subprocess, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
JOB = r"C:/Users/CH/Desktop/로또의 주식/shopping_shorts/data/mix_jobs/409f894230c6"
OUT = os.path.join(_HERE, "frames"); os.makedirs(OUT, exist_ok=True)
FFMPEG = "ffmpeg"

d = json.load(io.open(os.path.join(_HERE, "job_409f894230c6.json"), encoding="utf-8"))

def _probe(mp4):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", mp4], capture_output=True, text=True, timeout=30)
        return float((r.stdout or "0").strip())
    except Exception:
        return 0.0

_dur = {}
for _src in (d["extract"] or {}):
    _m = os.path.join(JOB, _src, "%s.mp4" % _src)
    if os.path.exists(_m):
        _dur[_src] = _probe(_m)
print("영상 길이:", {k: round(v, 1) for k, v in _dur.items()})
made = skipped = failed = 0
for src, v in (d["extract"] or {}).items():
    mp4 = os.path.join(JOB, src, "%s.mp4" % src)
    if not os.path.exists(mp4):
        print("영상 없음:", mp4); continue
    for s in (v or {}).get("segments") or []:
        sid = s["seg_id"]
        if "pad" in sid.lower():      # 빈칸 더미는 그림이 없다
            skipped += 1; continue
        out = os.path.join(OUT, "%s.jpg" % sid)
        if os.path.exists(out):
            made += 1; continue
        st, en = float(s.get("start") or 0), float(s.get("end") or 0)
        mid = st + max((en - st) / 2.0, 0.0)
        # ★일부 세그는 시각이 영상 길이를 넘는다(실측: s1-10 start=100s인데 영상 78.5s).
        #   데이터 자체의 문제 — 끝에서 0.5초 앞으로 당겨 최선을 다하고, 그래도 안 되면 건너뛴다.
        if _dur.get(src) and mid >= _dur[src]:
            mid = max(_dur[src] - 0.5, 0.0)
        r = subprocess.run(
            [FFMPEG, "-nostdin", "-loglevel", "error", "-ss", "%.2f" % mid, "-i", mp4,
             "-frames:v", "1", "-vf", "scale=384:-2,format=yuvj420p", "-q:v", "5", "-y", out],
            capture_output=True, text=True, timeout=90)
        if r.returncode == 0 and os.path.exists(out):
            made += 1
        else:
            failed += 1
            print("실패", sid, (r.stderr or "")[:80])
print("프레임 %d장 · pad건너뜀 %d · 실패 %d" % (made, skipped, failed))
