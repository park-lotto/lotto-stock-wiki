# -*- coding: utf-8 -*-
"""굿레터 소리 재기(관제 097) — 공용 소리 도구(tools/calcopy/engine/sound) 를 **불러서** 채널 8편을 잰다(사본 아님).
    PYTHONUTF8=1 py channel/goodletter/_tools/sound_run.py <src폴더> <wav폴더> <출력json> [id ...]
편마다: 통합 LUFS·참 피크(ffmpeg ebur128) · 끝 1.2초 RMS(무음 끝 판정) · 말 없는 구간 바닥(BGM 있나: 줄판독 no_caption·줄 사이 0.25초+ 의 100ms RMS 중앙값)
· 효과음 후보(sfx_events.detect, 고립 솟음 broad/tonal) · 우리 효과음 파형 상호상관(sfx_ncc.scan, ncc≥0.45)
· 후보마다 가장 가까운 표식(줄 시작 cap·컷 cut·제품 꼬리표 tag·큰글 big) 거리 — ±0.15초 안이면 그 표식에 붙은 것으로 센다.
제미나이·외부 전송 없음. 귀로 듣지 않으므로 '없음'이 아니라 '후보/확인 불가'로 적는다."""
import sys, os, json, glob, re, subprocess
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/calcopy/engine/sound"))
import sfx_fp as F            # noqa: E402
import sfx_events as E        # noqa: E402
import sfx_ncc as NC          # noqa: E402
SR = F.SR
TOL = 0.15


def lufs(mp4):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = r.stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", s); tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", s)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp else None)


def rms_db(x):
    return float(20 * np.log10(np.sqrt((x.astype(np.float64) ** 2).mean()) + 1e-9)) if len(x) else None


def markers(vid):
    m = {"cap": [], "cut": [], "tag": [], "big": []}
    lr = ROOT / f"channel/goodletter/줄판독/{vid}.json"
    gaps = []
    if lr.exists():
        d = json.loads(lr.read_text(encoding="utf-8"))
        L = d.get("lines") or []
        for i, l in enumerate(L):
            m["cap"].append(float(l["t0"]))
            if "큰글" in str(l.get("variant", "")) or "제품 이름" in str(l.get("variant", "")):
                m["big"].append(float(l["t0"]))
            if i and float(l["t0"]) - float(L[i - 1]["t1"]) >= 0.25:
                gaps.append((float(L[i - 1]["t1"]), float(l["t0"])))
        for nc in d.get("no_caption") or []:
            a, b = (nc.get("t0"), nc.get("t1")) if isinstance(nc, dict) else nc[:2]
            gaps.append((float(a), float(b)))
        for p in d.get("product_tag") or []:
            if p.get("t_in") is not None: m["tag"].append(float(p["t_in"]))
    dj = ROOT / f"channel/goodletter/뜯기/{vid}/뜯기.json"
    if dj.exists():
        m["cut"] = [float(t) for t in (json.loads(dj.read_text(encoding="utf-8")).get("cuts") or {}).get("times") or []]
    return m, gaps


def nearest(t, m):
    best = ("none", 9.0)
    for k, arr in m.items():
        for a in arr:
            if abs(t - a) < best[1]: best = (k, abs(t - a))
    return best


def main(src, wavdir, out, ids):
    os.makedirs(wavdir, exist_ok=True)
    T, _lib = NC.templates()
    res = {}
    for vid in ids:
        mp4 = os.path.join(src, vid + ".mp4"); wav = os.path.join(wavdir, vid + ".wav")
        if not os.path.exists(wav):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-ac", "1", "-ar", str(SR), wav], check=True)
        x = F.load(wav)
        I, TP = lufs(mp4)
        m, gaps = markers(vid)
        ev = E.detect(x)
        ncc = [h for h in NC.scan(x, T, thr=0.45)][:10]
        for e in ev:
            k, d = nearest(e["t"], m); e["near"] = k if d <= TOL else "none"; e["near_d"] = round(d, 2)
        floor = [rms_db(x[int(a * SR):int(b * SR)]) for a, b in gaps if b - a >= 0.25]
        speech = rms_db(x)
        fr = np.array([rms_db(x[i:i + int(0.1 * SR)]) for i in range(0, len(x) - int(0.1 * SR), int(0.1 * SR))])
        fr = fr[fr > -90]   # 완전 무음(디지털 0)은 빼고 — 끝 무음 컷은 end_1p2s_db 로 따로 본다
        res[vid] = {"lufs": I, "true_peak": TP, "dur": round(len(x) / SR, 2), "rms_all_db": round(speech, 1),
                    "end_1p2s_db": round(rms_db(x[-int(1.2 * SR):]), 1),
                    "rms100_p5_p50_p95": [round(float(np.percentile(fr, q)), 1) for q in (5, 50, 95)] if len(fr) else None,
                    "digital_silence_s": round(float(sum(1 for i in range(0, len(x) - int(0.1 * SR), int(0.1 * SR)) if np.abs(x[i:i + int(0.1 * SR)]).max() < 1e-4) * 0.1), 1),
                    "gap_rms_db": [round(v, 1) for v in floor if v is not None],
                    "events": ev, "n_events": len(ev),
                    "events_near": {k: sum(1 for e in ev if e["near"] == k) for k in ("cap", "cut", "tag", "big", "none")},
                    "ncc_top": ncc}
        print(vid, "LUFS", I, "끝", res[vid]["end_1p2s_db"], "틈", res[vid]["gap_rms_db"][:6], "바닥p5/50/95", res[vid]["rms100_p5_p50_p95"], "무음초", res[vid]["digital_silence_s"], "후보", len(ev), res[vid]["events_near"],
              "ncc", [(h["t"], h["file"][-24:], h["ncc"]) for h in ncc[:3]], flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
