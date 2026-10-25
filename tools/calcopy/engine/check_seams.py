# -*- coding: utf-8 -*-
"""이음매 검사 — 완성본에서 컷 경계의 ①되감김(같은 소스 화면을 다시 보여줌) ②소리 급변을 잰다 (관제 097, 2026-10-17).

    PYTHONUTF8=1 py tools/calcopy/engine/check_seams.py <mp4> --frame <frame.json> [--win x,y,w,h] [--mask y0,y1] [--json out.json]

왜: 아이템홈 1편 1판 17.75초 — 컷 #16(원본 ~582.82)이 끝나고 #17이 582.45부터 시작해 0.37초를 다시 보여줬고
(입 모양 반복), 같은 순간 원음 꼬리 −27dB → 나레 −10dB(17dB 급등). 검수표 B·compare 는 둘 다 못 잡았다(사장님이 잡음).
계획 표가 아니라 **완성본 영상·소리**를 잰다 — 렌더가 계획과 달라도 잡힌다.

① 되감김: 컷(이웃 프레임 차이 급등) 바로 뒤 프레임을 컷 앞 REWIND_LOOKBACK 초의 프레임들과 그림 일치(ORB+부분 아핀,
   bench.cuts.same_picture_moved — 같은 판단 두 벌 금지)로 대 본다. 가장 잘 맞는 앞 프레임이 마지막 프레임보다
   REWIND_MIN_S 이상 앞이고 일치점이 충분하면 '되감김'. 시간이 앞으로 흐른 정상 컷(크롭·배율만 바뀜)은 마지막 프레임과 가장 잘 맞는다.
①-2 점프 줌: 컷 앞뒤 프레임이 같은 그림(일치점 ≥ JUMP_ZOOM_INLIERS)인데 배율만 바뀜 — 이어지는 한 장면을 확대만 바꿔 자르면
   셀카 흔들림과 겹쳐 '끊긴다'(10-17 2판 11곳, 사장님 '19초부터 끊긴다'). 벤치(사람 편집본) 0.
② 소리 급변: 50ms RMS. 컷 경계 ±0.2초 안에서 '앞 150ms 평균이 조용(≤ JUMP_QUIET_DB)한데 다음 50ms 칸이 JUMP_DB 이상 뜀'.
   ★참고만(판정에 안 씀): 10-17 실측 — 벤치(사람 편집본 MfptnwqlGKs)도 말 시작마다 13~17dB 급등 9곳이 나와 1판 17.8초(18.8dB)와
   갈리지 않았다(바닥 소리 하락·윗소리 상승 지표도 벤치 15.0/13.4 vs 1판 20.5/14.4로 겹침). 소리 끊김은 귀·받아쓰기로 본다.
   되감김은 벤치 0 · 1판 2(17.77초, 0.37초) · 2판 0 으로 갈린다(시험 test_calcopy_check_seams).
자막 띠는 --mask 로 가린다(자막 글자가 컷 너머까지 같아 일치점이 부풀기 때문). 영상 내내 안 변하는 줄(제목 띠)은 자동으로 가린다
— 10-17 실측: 전체 화면 그대로 재면 제목 글자 때문에 1판 되감김을 놓쳤다(0건).
종료코드: 되감김 있거나 점프 줌이 잦거나 몰리면 1.
재보정 10-17: 사람 편집본 9편(만템 8·아이템홈 1) 전부 통과, 우리 1판(되감김)·2판(점프 줌 잦음·몰림) 걸림 — 표본이 9편뿐이라 새 채널은 그 벤치로 다시 확인할 것.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.channelkit.bench import probe  # noqa: E402
from shopping_shorts.channelkit.bench.cuts import same_picture_moved  # noqa: E402

SMALL_W = 270            # 비교용 축소 폭
CUT_DIFF_X = 4.0         # 이웃 프레임 평균 절대차가 중앙값의 이 배수 이상이면 컷 후보
CUT_DIFF_MIN = 6.0       # 그리고 절대값(0~255) 이 이상
REWIND_LOOKBACK = 0.8    # 컷 앞 몇 초까지 대 보나
REWIND_MIN_S = 0.12      # 가장 잘 맞는 앞 프레임이 마지막보다 이만큼 이상 앞이면 되감김
REWIND_INLIERS = 100     # 그 일치점 하한 — 10-17 재보정: 사람 편집(만템 8·아이템홈 1)의 멀티캠 각도 전환은 최대 7.6배·일치점<100
REWIND_RATIO = 5.0       # 마지막 프레임 일치점의 이 배수 이상(우리 1판 진짜 되감김 13~33배)
BOUND_TOL = 0.1          # 계획 컷 경계(bounds)를 아는 호출: 이 폭(초, 3프레임) 밖 되감김 = 이어 자른 한 조각 안(빠른 움직임 오탐, 10-25 ep12 11.3초 = O2 saA 17~21.36 안)
STATIC_ROW_STD = 4.0     # 영상 내내 거의 안 변하는 줄(제목 띠·검은 여백)은 가린다 — 고정 글자가 일치점을 부풀려 되감김을 가림
JUMP_ZOOM_INLIERS = 40    # 컷 앞뒤가 같은 그림(이어지는 한 장면)인데
JUMP_ZOOM_SCALE = 0.06    # 배율만 이만큼 넘게 바뀌면 '점프 줌'(1.67배↔2.0배 = 1.19/0.84)
JZ_MERGE_S = 0.15         # 이 안의 점프 줌은 한 번으로 센다(경계 이중 검출)
JZ_RATE = 0.30            # 초당 점프 줌 상한 — 사람 편집 최대 0.25(만템 3Xb8 5회/20초), 우리 2판 0.46·1판 0.33
JZ_BURST_N, JZ_BURST_S = 3, 3.0   # 3초 안에 3번 이상 몰리면 걸림 — 사람 편집 0편, 2판 12.3~15.27초·1판 0.9~2.63초
RMS_WIN = 0.05
JUMP_QUIET_DB = -22.0
JUMP_DB = 12.0
JUMP_NEAR_CUT = 0.2


def _gray_frames(path: str, win: tuple[int, int, int, int], mask: tuple[int, int] | None):
    x, y, w, h = win
    sh = int(round(SMALL_W * h / w / 2) * 2)
    out = []
    for g in probe.frames(path, f"crop={w}:{h}:{x}:{y},scale={SMALL_W}:{sh}", SMALL_W, sh, "gray"):
        g = g.copy()
        if mask:
            a = max(0, int((mask[0] - y) * sh / h)); b = min(sh, int((mask[1] - y) * sh / h))
            if b > a:
                g[a:b, :] = 0
        out.append(g)
    if out:
        st = np.stack(out).astype(np.float32).std(axis=0).mean(axis=1)
        still = st < STATIC_ROW_STD
        for g in out:
            g[still, :] = 0
    return out


def find_cuts(fr: list[np.ndarray]) -> list[int]:
    """프레임 i 가 새 컷의 첫 프레임인 i 목록."""
    d = np.array([np.abs(fr[i].astype(np.int16) - fr[i - 1].astype(np.int16)).mean() for i in range(1, len(fr))])
    if len(d) == 0:
        return []
    med = float(np.median(d)) or 1e-6
    return [i + 1 for i, v in enumerate(d) if v >= max(CUT_DIFF_MIN, CUT_DIFF_X * med)]


def rewinds(fr: list[np.ndarray], cuts: list[int], fps: float) -> list[dict]:
    back = int(round(REWIND_LOOKBACK * fps))
    out = []
    for c in cuts:
        if c < 2 or c >= len(fr):
            continue
        post = fr[c]
        pre = list(range(max(0, c - back), c))
        sc = [same_picture_moved(fr[j], post)[0] for j in pre]
        if not sc:
            continue
        k = int(np.argmax(sc)); best, last = sc[k], sc[-1]
        lag = (c - 1 - pre[k]) / fps
        if best >= REWIND_INLIERS and lag >= REWIND_MIN_S and best >= REWIND_RATIO * max(last, 1):
            out.append({"t": round(c / fps, 3), "되감김_초": round(lag + 1 / fps, 3), "일치점": best, "마지막_일치점": last})
    return out


def jump_zooms(fr: list[np.ndarray], cuts: list[int], fps: float) -> list[dict]:
    """한 장면이 이어지는데 확대만 바뀐 컷 — 10-17 아이템홈 1편 2판 11곳(벤치 0), 사장님 '19초부터 화면이 끊긴다'."""
    out = []
    for c in cuts:
        if c < 1 or c >= len(fr):
            continue
        n, sc = same_picture_moved(fr[c - 1], fr[c])
        if n >= JUMP_ZOOM_INLIERS and sc and abs(sc - 1) > JUMP_ZOOM_SCALE:
            out.append({"t": round(c / fps, 3), "배율": sc, "일치점": n})
    return out


def rms_db(path: str) -> list[float]:
    sr = 16000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    n = int(sr * RMS_WIN)
    out = []
    for i in range(0, len(a) - n + 1, n):
        r = math.sqrt(float((a[i:i + n] ** 2).mean())) or 1.0
        out.append(20 * math.log10(r / 32768))
    return out


def jumps(db: list[float], cut_ts: list[float]) -> list[dict]:
    out = []
    for i in range(3, len(db)):
        before = sum(db[i - 3:i]) / 3
        if before <= JUMP_QUIET_DB and db[i] - before >= JUMP_DB:
            t = i * RMS_WIN
            near = [c for c in cut_ts if abs(c - t) <= JUMP_NEAR_CUT]
            if near:
                out.append({"t": round(t, 2), "앞150ms": round(before, 1), "뒤50ms": round(db[i], 1),
                            "급등dB": round(db[i] - before, 1), "컷": near[0]})
    return out


def from_frame(frame_json: str) -> tuple[tuple | None, tuple | None]:
    """틀(frame.json)에서 영상 창(video 층)과 자막 띠(caption 층 y ± 줄높이)를 읽는다 — 창·띠 좌표의 주인은 틀이다."""
    d = json.loads(Path(frame_json).read_text(encoding="utf-8"))
    win = mask = None
    for l in d.get("layers", []):
        if l.get("kind") == "video" and win is None:
            win = (int(l["x"]), int(l["y"]), int(l["w"]), int(l["h"]))
        if l.get("kind") == "text" and l.get("role") == "caption" and mask is None:
            lh = float(l.get("line_h") or l.get("size") or 80)
            n = int(l.get("lines") or 1)
            mask = (int(l["y"] - lh), int(l["y"] + lh * (n + 0.4)))
    return win, mask


def split_by_bounds(rw: list[dict], bounds: list[float] | None, tol: float = BOUND_TOL) -> tuple[list[dict], list[dict]]:
    """(판단 주인: 어느 되감김을 세나) bounds = 계획 컷 경계 시각(완성본 초). None·빈 목록 = 경계를 모름 → 전부 센다(옛 판정 그대로 —
    10-25 관문이 timeline 에 cuts 가 없을 때 빈 경계로 걸러 되감김을 통째로 뺐다). 경계를 알면 ±tol 안 것만 센다. 반환 (센 것, 한 조각 안이라 뺀 것)."""
    if not bounds:
        return list(rw), []
    real = [r for r in rw if any(abs(float(r["t"]) - float(b)) <= tol for b in bounds)]
    return real, [r for r in rw if r not in real]


def check(path: str, win=None, mask=None, bounds: list[float] | None = None) -> dict:
    """bounds(선택) = 계획 컷 경계 — 주면 경계 밖 되감김은 '되감김_조각안'으로 빼고 판정 밖(split_by_bounds). 안 주면 옛 판정."""
    inf = probe.info(path)
    fps = inf.get("fps") or 30.0
    win = win or (0, 0, inf["width"], inf["height"])
    fr = _gray_frames(path, win, mask)
    cuts = find_cuts(fr)
    cut_ts = [round(c / fps, 3) for c in cuts]
    rw, inside = split_by_bounds(rewinds(fr, cuts, fps), bounds)
    jz = jump_zooms(fr, cuts, fps)
    jp = jumps(rms_db(path), cut_ts)
    dur = len(fr) / fps if fps else 0
    jz_bad = jz_verdict(jz, dur)
    return {"file": str(path), "fps": fps, "컷": cut_ts, "되감김": rw, "점프줌": jz, "점프줌_판정": jz_bad,
            "소리급변_참고": jp, "ok": not rw and not jz_bad, **({"되감김_조각안": inside, "경계": "계획 컷 경계 ±" + str(BOUND_TOL)} if bounds else {})}


def jz_verdict(jz: list[dict], dur: float) -> str:
    """점프 줌은 사람 편집에도 있다(만템 0~5회) — 횟수 0이 아니라 '잦음·몰림'을 걸른다. 빈 문자열 = 통과."""
    ts = []
    for x in jz:
        if not ts or x["t"] - ts[-1] > JZ_MERGE_S:
            ts.append(x["t"])
    if dur and len(ts) / dur > JZ_RATE:
        return f"잦음 {len(ts)}회/{dur:.1f}초 > {JZ_RATE}/초"
    for i in range(len(ts) - JZ_BURST_N + 1):
        if ts[i + JZ_BURST_N - 1] - ts[i] <= JZ_BURST_S:
            return f"몰림 {JZ_BURST_N}회가 {ts[i]:.2f}~{ts[i + JZ_BURST_N - 1]:.2f}초"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--win", help="x,y,w,h 영상 창(기본 전체)")
    ap.add_argument("--mask", help="y0,y1 자막 띠(가림)")
    ap.add_argument("--frame", help="틀 frame.json — 창·자막 띠를 여기서 읽는다(--win/--mask 가 이긴다)")
    ap.add_argument("--json")
    a = ap.parse_args()
    fw, fm = from_frame(a.frame) if a.frame else (None, None)
    win = tuple(int(v) for v in a.win.split(",")) if a.win else fw
    mask = tuple(int(v) for v in a.mask.split(",")) if a.mask else fm
    if mask is None:
        print("[경보] 자막 띠를 모름(--frame/--mask 없음) — 자막 글자가 컷 너머까지 같으면 되감김 오탐이 난다")
    r = check(a.mp4, win, mask)
    print(f"컷 {len(r['컷'])} · 되감김 {len(r['되감김'])} · 점프줌 {len(r['점프줌'])}({r['점프줌_판정'] or '드묾'}) → {'통과' if r['ok'] else '걸림'} (소리급변 참고 {len(r['소리급변_참고'])})")
    for x in r["점프줌"]:
        print("  점프줌", x)
    for x in r["되감김"]:
        print("  되감김", x)
    for x in r["소리급변_참고"]:
        print("  (참고) 소리급변", x)
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
