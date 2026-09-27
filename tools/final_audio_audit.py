# -*- coding: utf-8 -*-
"""편성표(고객이 정한 소리) vs 완성본에서 **파형으로 읽어낸** 소리 — 칸마다 대조한다(2026-09-27, 읽기 전용).

왜: 편집 화면 미리보기(app._pvproxy_build)는 화면+나레이션만 굽는다. BGM·효과음은 완성본 렌더 마지막 단계
  (video_assemble._burn_captions)에서만 얹힌다 → 소리 층은 "미리보기 vs 완성본"으로 못 잰다.
  그래서 기대값은 **렌더가 쓰는 함수 그대로** 만든다(0순위-B — 도구가 계산을 따로 들면 도구가 틀린다):
    칸 시각   = video_assemble._beat_timeline(plan, tts_paths)   (자막·효과음·CTA 자르기와 같은 자)
    효과음    = video_assemble.sfx_events_for(timeline, mix_pipeline._resolve_sfx_paths(...))  (팩 포함)
    BGM       = mix_pipeline.resolve_deco_media(deco, work)["bgm"]  (렌더·캡컷과 같은 함수)
    인트로    = mix_pipeline._intro_choice(job.thumbnail)  (run_render 가 prepend_still 로 앞에 붙이는 무음 구간)
  완성본은 실제 파일에서 소리를 뽑아 **교차상관(NCC)**으로 찾는다 — 예상 시각을 그대로 믿지 않는다.

측정:
  ① 나레이션: 칸 mp3(head_trim 반영, 실효 길이)를 예상 시각 ±0.5초에서 찾는다 → 실제 시작 오차(초).
     못 찾으면(NCC < NARR_MIN) ±2초로 한 번 더 — 찾으면 '창 밖' 오차로 적는다.
  ② 효과음: 완성본에서 찾은 나레이션(칸마다 최소제곱 이득)을 빼 **잔여**를 만들고, 그 잔여에서 효과음 파형을
     예상 시각 ±0.5초로 찾는다(나레이션이 훨씬 커서 원음에서 바로 찾으면 묻힌다).
  ③ BGM: 기대(파일·볼륨)가 있으면 잔여에서 BGM 파형(렌더처럼 aloop 반복)을 찾아 나레이션 대비 이득(dB)을
     잰다. 렌더는 나레이션+BGM 을 같은 amix(normalize 기본)로 섞어 비율 = volume/100 이 기대값이다.
  ④ 길이: 완성본 소리 길이 vs 인트로 + 칸 실효 길이 합.

★읽기 전용: DB 는 sqlite `mode=ro` 로만 연다(쓰기 시도는 예외로 터진다). 렌더·청소·굽기 호출 없음.
  임시 파일을 만들지 않는다(ffmpeg 출력은 파이프로 받는다). 결과만 AUDIO_OUT(기본 /tmp/audio_audit)에 쓴다.

서버: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
      python3 /tmp/audio_audit/final_audio_audit.py [N최근완료=10] [job_id ...]
결과: $AUDIO_OUT/report.txt (job 한 줄 + '== 칸 N · 나레이션 0.15초+ 오차 X · 효과음 누락 Y · BGM 이상 Z ...' 요약)
      $AUDIO_OUT/samples.jsonl (칸·효과음별 원시값)
"""
import json
import math
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SR = 16000                 # 분석 표본율 — 말소리·효과음 시각 판정엔 충분(0.06ms 해상도)
WIN = 0.5                  # 찾는 창 ±초(작업 지시)
WIDE = 2.0                 # 못 찾았을 때 한 번 더 보는 창 ±초
SHIFT_T = 0.15             # 오차 보고 기준(초) — 영상 도구(SHIFT_T)와 같은 값
NARR_MIN = 0.30            # 나레이션 NCC 이 아래면 '못 찾음'
SFX_MIN = 0.25             # 효과음 NCC(잔여 기준) 이 아래면 '누락'
SFX_SHIFT_T = 0.10         # 효과음 타점 오차 보고 기준(초)
SFX_TMPL = 1.0             # 효과음 틀 최대 길이(초) — 앞부분(타점)이 판정의 핵심
SFX_MIN_VOL = 0.05         # 볼륨×보정이 이 아래면 들리지 않아야 정상 → 검사 제외
BGM_DB_T = 3.0             # BGM 실측 비율이 기대에서 이만큼(dB) 벗어나면 이상
BGM_MIN_R = 0.05           # 잔여와 BGM 파형 상관이 이 아래면 'BGM 없음'
LEN_T = 0.10               # 길이 차 보고 기준(초)
STALE_SLACK = 1.0          # mp3 수정 시각이 완성본보다 이만큼 뒤면 '렌더 뒤 음성 바뀜'

OUT = Path(os.getenv("AUDIO_OUT") or "/tmp/audio_audit")


# ── 소리 읽기(임시 파일 없음 — 파이프) ───────────────────────────────────────
def load_audio(path, ss=0.0, t=None, sr=SR, honor_pts=False):
    """모노 float32 [-1,1]. ss·t 는 초(입력 쪽 -ss — 렌더의 `-ss head_trim -i tts` 와 같은 자리).
    honor_pts=True: 완성본용 — 소리 패킷의 **타임스탬프대로** 놓는다(빈틈은 무음으로 채우고 겹침은 자른다,
      첫 표본 = pts 0). 플레이어가 재생하는 자리다. 끄면 표본을 이어 붙이기만 해 빈틈이 사라진다
      (2026-09-27 서버 실측: 1d09aa313fd7 은 칸 경계마다 pts 빈틈 63~84ms — 이어 붙이면 길이가 0.265초 짧게 나왔다)."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if ss and ss > 0:
        cmd += ["-ss", "%.4f" % ss]
    cmd += ["-i", str(path)]
    if t is not None:
        cmd += ["-t", "%.4f" % max(0.0, t)]
    cmd += ["-vn", "-ac", "1"]
    if honor_pts:
        cmd += ["-af", "aresample=%d:async=1:min_hard_comp=0.005:first_pts=0" % sr]
    else:
        cmd += ["-ar", str(sr)]
    cmd += ["-f", "f32le", "-"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 읽기 실패 %s: %s" % (path, r.stderr.decode("utf-8", "replace")[-300:]))
    return np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)


def stream_info(path):
    """(영상 첫 pts, 소리 첫 pts, 소리 pts 빈틈[(시각, 빈틈초)]) — 칸 시각은 **영상 기준**(자막·장면이 영상에 구워진다)이라
    소리 시각에서 (영상 시작 - 소리 시작)을 뺀다. 빈틈 = 패킷 사이 간격 - 패킷 길이 > 5ms."""
    def _q(args):
        r = subprocess.run(["ffprobe", "-v", "error", *args, str(path)], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        return r.stdout.decode("utf-8", "replace").split()
    def _st(sel):
        try:
            v = _q(["-select_streams", sel, "-show_entries", "stream=start_time", "-of", "csv=p=0"])
            return float(v[0]) if v and v[0] not in ("N/A", "") else None
        except Exception:      # noqa: BLE001
            return None
    gaps = []
    try:
        pk = [x.split(",") for x in _q(["-select_streams", "a:0", "-show_entries", "packet=pts_time,duration_time", "-of", "csv=p=0"])]
        pk = [(float(a), float(b)) for a, b, *_ in pk if a not in ("N/A", "") and b not in ("N/A", "")]
        for (p0, d0), (p1, _d1) in zip(pk, pk[1:]):
            if p1 - (p0 + d0) > 0.005:
                gaps.append((round(p0 + d0, 3), round(p1 - p0 - d0, 3)))
    except Exception:      # noqa: BLE001 — 빈틈 표기는 보조
        pass
    return _st("v:0"), _st("a:0"), gaps


# ── 교차상관 ─────────────────────────────────────────────────────────────
def ncc_search(sig, tmpl, center, win):
    """sig 안에서 tmpl 이 **center(표본)에서 시작한다고 예상**할 때 ±win(표본) 안의 최적 시작점.
    → (오프셋 표본 = 실제-예상, 최고 NCC, 그 자리의 최소제곱 이득). NCC 는 창 에너지로 정규화한다."""
    L = len(tmpl)
    tn = float(np.sqrt(np.dot(tmpl, tmpl)))
    if L == 0 or tn < 1e-9:
        return 0, 0.0, 0.0
    a, b = center - win, center + win + L
    seg = np.zeros(b - a)
    s0, s1 = max(0, a), min(len(sig), b)
    if s1 > s0:
        seg[s0 - a:s1 - a] = sig[s0:s1]
    n = 1 << int(math.ceil(math.log2(max(2, len(seg)))))
    corr = np.fft.irfft(np.fft.rfft(seg, n) * np.conj(np.fft.rfft(tmpl, n)), n)[:2 * win + 1]
    cs = np.concatenate([[0.0], np.cumsum(seg * seg)])
    e = cs[L:L + 2 * win + 1] - cs[:2 * win + 1]
    ncc = corr / (np.sqrt(np.maximum(e, 0.0)) * tn + 1e-12)
    k = int(np.argmax(ncc))
    return k - win, float(ncc[k]), float(corr[k] / (tn * tn))


def _place(buf, tmpl, start, gain):
    """buf 에서 start 표본부터 gain*tmpl 을 뺀다(잔여 만들기)."""
    s0, s1 = max(0, start), min(len(buf), start + len(tmpl))
    if s1 > s0:
        buf[s0:s1] -= gain * tmpl[s0 - start:s1 - start]


def _db(x):
    return 20.0 * math.log10(max(float(x), 1e-9))


# ── 한 편 대조(기대값 ctx 는 순수 데이터 — 테스트가 합성 소리로 직접 부른다) ──────────
def video_gray(path, w=36, h=64):
    """완성본 영상을 작은 회색조 프레임으로(표시 순서 그대로, 프레임 복제·버림 없음) → (N,h,w)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-an", "-vf", "scale=%d:%d,format=gray" % (w, h),
                        "-fps_mode", "passthrough", "-f", "rawvideo", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError("영상 읽기 실패: %s" % r.stderr.decode("utf-8", "replace")[-200:])
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    return a[: (len(a) // (w * h)) * w * h].reshape(-1, h, w).astype(np.float32)


CUT_LO, CUT_HI = -0.2, 0.6      # 칸 경계 컷을 찾는 창(계획 프레임 기준 초)


def video_cuts(frames, plan_frames, fps=30):
    """칸 경계마다 화면에서 **실제로 그림이 바뀌는 프레임**을 찾는다.
    화면 가운데 띠(세로 20~70%)의 앞 프레임 대비 차이. 창 안 최대 튐이 전체 중앙값의 4배·8 이상일 때만 컷으로 인정.
    → [{plan, cut(프레임|None), mag, spikes:[(오프셋초, 크기)]}]. ★계획 프레임의 튐(자막·틀 교체)과 그림 컷이
      둘 다 보일 수 있어 튐 목록을 함께 남긴다."""
    if len(frames) < 3:
        return [{"plan": p, "cut": None, "mag": 0.0, "spikes": []} for p in plan_frames]
    h = frames.shape[1]
    band = frames[:, int(h * 0.2):int(h * 0.7), :]
    d = np.zeros(len(band), np.float32)
    d[1:] = np.abs(band[1:] - band[:-1]).mean(axis=(1, 2))
    thr = max(8.0, 4.0 * float(np.median(d[1:])))
    out = []
    for p in plan_frames:
        lo, hi = max(1, p + int(CUT_LO * fps)), min(len(d) - 1, p + int(CUT_HI * fps))
        if hi < lo:
            out.append({"plan": p, "cut": None, "mag": 0.0, "spikes": []})
            continue
        seg = d[lo:hi + 1]
        spikes = [(round((lo + i - p) / fps, 3), round(float(v), 1)) for i, v in enumerate(seg) if v >= thr]
        mx = float(seg.max())
        # 가장 **이른** 큰 튐(창 최대의 60% 이상) — 칸 안의 두 번째 컷(대개 0.5초+ 뒤)을 칸 시작으로 잡지 않게
        big = [i for i, v in enumerate(seg) if v >= thr and v >= 0.6 * mx]
        k = big[0] if big else int(np.argmax(seg))
        out.append({"plan": p, "cut": (lo + k) if seg[k] >= thr else None, "mag": round(float(seg[k]), 1), "spikes": spikes})
    return out


def audit(ctx, want_video=True):
    """ctx = {final, intro, beats:[{idx, tts, head_trim, dur, t0, stale}], sfx:[{path, t, vol, beat}],
              bgm:{path, vol}|None}
    → {rows, sfx, bgm, len, ...}. 판정만 하고 파일은 쓰지 않는다.

    ★기준 소리 = **디코드한 표본을 이어 재생한 것 하나**(ffmpeg -i final -vn, 플레이어처럼). pts대로 놓은 값은 참고 열(err_pts).
    ★세 축(전부 '표시 시각' = 영상 첫 pts(예: 0.021) 포함):
       자막  cap = v0 + 인트로 + t0            (_beat_timeline 실수 누적 — 자막·틀·효과음이 이 자로 구워진다: 코드 기준)
       영상  vid = v0 + (실측 컷 프레임)/30      (완성본에서 그림이 바뀌는 프레임, 못 찾으면 None)
       음성  nar = 디코드 표본에서 찾은 칸 시작
       판정 = |nar - vid| (영상 컷을 못 찾은 칸은 |nar - 계획 프레임|) >= 0.15초."""
    sig = load_audio(ctx["final"], honor_pts=False)
    v0, a0, gaps = stream_info(ctx["final"])
    av = float(v0 or 0.0)
    intro_raw = float(ctx.get("intro") or 0.0)
    intro_cfg = intro_raw
    # 인트로 실측: 설정은 켜져 있어도 prepend_still 이 실패하면 안 붙는다(run_render 는 실패를 로그로만 남긴다).
    #   첫 칸 음성을 0초~(인트로+0.5초) 전체에서 찾아, 설정의 절반보다 앞에서 나오면 '인트로 없음'으로 본다.
    if intro_raw > 0 and ctx["beats"]:
        b0 = ctx["beats"][0]
        tm0 = load_audio(b0["tts"], ss=float(b0.get("head_trim") or 0.0), t=float(b0["dur"]))
        c0 = int(round((intro_raw + av) * SR))
        o0, v0n, _g0 = ncc_search(sig, tm0, c0, int((intro_raw + 0.5) * SR))
        if v0n >= NARR_MIN and (c0 + o0) / SR - av < intro_raw / 2:
            intro_raw = 0.0
    intro = intro_raw + av
    total_exp = intro + sum(float(b["dur"]) for b in ctx["beats"])
    len_exp = intro_raw + sum(float(b["dur"]) for b in ctx["beats"])
    res = sig.copy()
    rows, gains, tms = [], [], []
    w, ww = int(WIN * SR), int(WIDE * SR)
    pred = 0.0          # 수리 전 렌더(칸마다 -t 음성길이 → 영상 프레임 올림)가 만들었을 누적 밀림 — 비교용 예측
    for b in ctx["beats"]:
        tm = load_audio(b["tts"], ss=float(b.get("head_trim") or 0.0), t=float(b["dur"]))
        tms.append(tm)
        exp = intro + float(b["t0"])
        c = int(round(exp * SR))
        off, v, g = ncc_search(sig, tm, c, w)
        wide = False
        if v < NARR_MIN:
            off2, v2, g2 = ncc_search(sig, tm, c, ww)
            if v2 >= NARR_MIN:
                off, v, g, wide = off2, v2, g2, True
        found = v >= NARR_MIN
        if found:
            _place(res, tm, c + off, g)
            gains.append(g)
        plan_f = int(round((intro_raw + float(b["t0"])) * 30))      # 수리 뒤 렌더의 칸 첫 프레임(_render_mix 누적 반올림)
        rows.append({"beat": b["idx"], "cap": round(exp, 3), "nar": round((c + off) / SR, 3) if found else None,
                     "err": round(off / SR, 3) if found else None, "ncc": round(v, 3), "gain": round(g, 4),
                     "wide": wide, "stale": bool(b.get("stale")), "plan_f": plan_f, "pred_prefix": round(pred, 3),
                     "dur": round(float(b["dur"]), 3)})
        d3 = round(float(b["dur"]), 3)
        pred += math.ceil(d3 * 30 - 1e-6) / 30.0 - float(b["dur"])
    g_n = float(np.median(gains)) if gains else 0.0
    # 참고 열: pts대로 놓은 소리에서 같은 칸
    len_pts = None
    try:
        sig_pts = load_audio(ctx["final"], honor_pts=True)
        for row, b, tm in zip(rows, ctx["beats"], tms):
            c = int(round((intro + float(b["t0"])) * SR))
            off, v, _g = ncc_search(sig_pts, tm, c, w)
            if v < NARR_MIN:
                off2, v2, _g2 = ncc_search(sig_pts, tm, c, ww)
                if v2 >= NARR_MIN:
                    off, v = off2, v2
            row["err_pts"] = round(off / SR, 3) if v >= NARR_MIN else None
        len_pts = len(sig_pts) / SR
    except Exception:      # noqa: BLE001 — 참고 열
        pass
    # 영상 축: 칸 경계의 실제 그림 컷
    vinfo = None
    if want_video:
        try:
            fr = video_gray(ctx["final"])
            vc = video_cuts(fr, [r["plan_f"] for r in rows])
            for n_, (r, x) in enumerate(zip(rows, vc)):
                if n_ == 0 and intro_raw <= 0:
                    x = dict(x, cut=None)        # 인트로 없는 첫 칸엔 칸 경계(컷)가 없다
                r["vid"] = round(av + x["cut"] / 30.0, 3) if x["cut"] is not None else None
                r["vid_spikes"] = x["spikes"]
                r["plan_t"] = round(av + r["plan_f"] / 30.0, 3)
                ref = r["vid"] if r["vid"] is not None else r["plan_t"]
                r["ref_kind"] = "영상컷" if r["vid"] is not None else "계획프레임"
                r["err_v"] = round(r["nar"] - ref, 3) if r["nar"] is not None else None
                r["vid_minus_cap"] = round(r["vid"] - r["cap"], 3) if r["vid"] is not None else None
            vinfo = {"frames": int(len(fr))}
        except Exception as e:      # noqa: BLE001
            vinfo = {"why": str(e)[:120]}
    for r in rows:
        if "err_v" not in r:          # 영상 축을 못 쟀으면 계획 프레임 기준
            r["plan_t"] = round(av + r["plan_f"] / 30.0, 3)
            r["err_v"] = round(r["nar"] - r["plan_t"], 3) if r["nar"] is not None else None
            r.setdefault("vid", None)
            r.setdefault("ref_kind", "계획프레임")
    # ② 효과음 — 잔여에서 찾는다
    sfx_rows = []
    for ev in ctx.get("sfx") or []:
        t_exp = intro + float(ev["t"])
        if float(ev.get("vol", 1.0)) < SFX_MIN_VOL or t_exp >= total_exp - 0.05:
            sfx_rows.append({**_ev_pub(ev), "exp": round(t_exp, 3), "skip": True})
            continue
        try:
            tm = load_audio(ev["path"], t=SFX_TMPL)
        except Exception as e:      # noqa: BLE001 — 효과음 파일이 없으면 판정 불가로 적는다(누락과 가른다)
            sfx_rows.append({**_ev_pub(ev), "exp": round(t_exp, 3), "err": None, "ncc": 0.0,
                             "missing_file": True, "why": str(e)[:80]})
            continue
        off, v, g = ncc_search(res, tm, int(round(t_exp * SR)), w)
        ok = v >= SFX_MIN
        sfx_rows.append({**_ev_pub(ev), "exp": round(t_exp, 3), "err": round(off / SR, 3) if ok else None,
                         "ncc": round(v, 3), "rel_db": round(_db(abs(g)) - _db(g_n), 1) if (ok and g_n > 0) else None})
    # ③ BGM — 잔여에서 효과음 자리(±0.6초)를 빼고 BGM 파형 상관·이득
    bg = ctx.get("bgm")
    mask = np.ones(len(res), bool)
    for ev in ctx.get("sfx") or []:
        a = int((intro + float(ev["t"]) - 0.6) * SR)
        mask[max(0, a):max(0, a + int(1.2 * SR))] = False
    mask[:int(intro * SR)] = False
    if bg and bg.get("path"):
        try:
            one = load_audio(bg["path"])
            n_body = max(0, len(sig) - int(round(intro * SR)))
            reps = int(math.ceil(n_body / max(1, len(one)))) if len(one) else 0
            tile = np.tile(one, max(1, reps))[:n_body]
            probe = tile[:int(6 * SR)]
            off, _v, _g = ncc_search(res, probe, int(round(intro * SR)), int(0.3 * SR))
            st = int(round(intro * SR)) + off
            track = np.zeros(len(res))
            s1 = min(len(res), st + len(tile))
            track[max(0, st):s1] = tile[max(0, -st):s1 - st]
            m = mask & (track != 0)
            den = float(np.dot(track[m], track[m]))
            g_b = float(np.dot(res[m], track[m]) / den) if den > 0 else 0.0
            r = float(np.dot(res[m], track[m]) / (math.sqrt(den * float(np.dot(res[m], res[m]))) + 1e-12)) if den > 0 else 0.0
            exp_db = _db(float(bg.get("vol") or 0.0))
            got_db = (_db(abs(g_b)) - _db(g_n)) if (g_n > 0 and g_b > 0) else None
            bad = (r < BGM_MIN_R) or got_db is None or abs(got_db - exp_db) > BGM_DB_T
            bgm_out = {"expect": True, "r": round(r, 3), "rel_db": None if got_db is None else round(got_db, 1),
                       "exp_db": round(exp_db, 1), "start_err": round(off / SR, 3), "bad": bool(bad)}
        except Exception as e:      # noqa: BLE001
            bgm_out = {"expect": True, "bad": True, "why": str(e)[:100]}
    else:
        rm = res[mask]
        rel = (_db(float(np.sqrt(np.mean(rm * rm)))) - _db(g_n * _narr_rms(ctx, g_n))) if (len(rm) and g_n > 0) else None
        bgm_out = {"expect": False, "resid_db": None if rel is None else round(rel, 1), "bad": False}
    dur_got = len(sig) / SR
    last = rows[-1] if rows else None
    # 끝 잘림: 마지막 칸 음성이 소리 끝을 넘어가면 그만큼 잘렸다(칸 길이엔 끝 무음 여백이 조금 들어 있다)
    tail_cut = round((last["nar"] + last["dur"]) - dur_got, 3) if (last and last["nar"] is not None) else None
    tail_db = None      # 잘린 꼬리의 음량(칸 전체 대비 dB) — -30dB 아래면 여백(무음)만 잘린 것, 위면 말이 잘린 것
    if tail_cut and tail_cut > 0.02 and tms:
        t_all = tms[-1]
        cut_n = min(len(t_all), int(tail_cut * SR))
        if cut_n > 0:
            rms_all = float(np.sqrt(np.mean(t_all * t_all))) or 1e-9
            tail = t_all[-cut_n:]
            tail_db = round(_db(float(np.sqrt(np.mean(tail * tail)))) - _db(rms_all), 1)
    return {"av0": round(av, 3), "intro_cfg": intro_cfg, "intro_used": intro_raw, "tail_db": tail_db, "a0": a0, "pts_gaps": gaps, "video": vinfo, "rows": rows, "sfx": sfx_rows, "bgm": bgm_out,
            "g_n_db": round(_db(g_n), 1) if g_n > 0 else None, "tail_cut": tail_cut,
            "len": {"got": round(dur_got, 3), "exp": round(len_exp, 3), "diff": round(dur_got - len_exp, 3),
                    "got_pts": None if len_pts is None else round(len_pts, 3)}}


def _ev_pub(ev):
    return {"beat": ev.get("beat"), "t": round(float(ev["t"]), 3), "file": Path(str(ev["path"])).name,
            "vol": round(float(ev.get("vol", 1.0)), 3)}


_NARR_RMS = {}


def _narr_rms(ctx, _g):
    """칸 mp3 전체의 RMS(잔여 비율 표기용 — 판정엔 안 쓴다)."""
    k = id(ctx)
    if k not in _NARR_RMS:
        xs = [load_audio(b["tts"], ss=float(b.get("head_trim") or 0.0), t=float(b["dur"])) for b in ctx["beats"]]
        x = np.concatenate(xs) if xs else np.zeros(1)
        _NARR_RMS[k] = float(np.sqrt(np.mean(x * x))) if len(x) else 1e-9
    return _NARR_RMS[k]


def judge(r):
    """한 편 결과 → 셈(요약 줄 재료)."""
    rows = r["rows"]
    live = [x for x in rows if not x["stale"]]
    # 판정 = 음성 vs 영상(칸 첫 그림) — 고객이 느끼는 어긋남. 자막 vs 음성은 따로 센다(cap_bad).
    narr_bad = [x for x in live if x.get("err_v") is not None and abs(x["err_v"]) >= SHIFT_T]
    cap_bad = [x for x in live if x["err"] is not None and abs(x["err"]) >= SHIFT_T]
    narr_lost = [x for x in live if x["err"] is None]
    sfx_chk = [x for x in r["sfx"] if not x.get("skip") and not x.get("missing_file")]
    sfx_miss = [x for x in sfx_chk if x["err"] is None]
    sfx_off = [x for x in sfx_chk if x["err"] is not None and abs(x["err"]) >= SFX_SHIFT_T]
    return {"n": len(rows), "narr_bad": narr_bad, "cap_bad": cap_bad, "narr_lost": narr_lost, "stale": [x for x in rows if x["stale"]],
            "sfx_n": len(sfx_chk), "sfx_miss": sfx_miss, "sfx_off": sfx_off,
            "sfx_nofile": [x for x in r["sfx"] if x.get("missing_file")],
            "bgm_bad": 1 if (r["bgm"] or {}).get("bad") else 0,
            "len_bad": 1 if abs(r["len"]["diff"]) >= LEN_T else 0}


# ── 기대값 만들기(서버 — 렌더가 쓰는 함수 그대로) ──────────────────────────────
def ro_store(db):
    """sqlite mode=ro 로만 여는 Store — 스키마 초기화(_init_schema)를 건너뛰고 모든 연결을 읽기 전용으로."""
    from shopping_shorts.store import Store

    class RoStore(Store):
        def __init__(self, p):          # noqa: D401 — 부모 __init__ 은 스키마를 깐다(쓰기) → 부르지 않는다
            self.db_path = Path(p)

        def _conn(self):
            return sqlite3.connect("file:%s?mode=ro" % Path(self.db_path).resolve().as_posix(), uri=True, timeout=15.0)
    return RoStore(db)


def pick_final(job, w):
    """고객이 받는 완성본: DB video_path(있으면) → final.mp4 → 최신 final*.mp4(청소본 final_clean_* 제외)."""
    vp = job.get("video_path")
    if vp and Path(vp).exists():
        return Path(vp)
    if (w / "final.mp4").exists():
        return w / "final.mp4"
    c = [f for f in w.glob("final*.mp4") if not f.name.startswith("final_clean")]
    return max(c, key=lambda f: f.stat().st_mtime) if c else None


def expected(store, jid, root="shopping_shorts/data/mix_jobs"):
    from shopping_shorts import mix_pipeline as mp, video_assemble as va
    job = store.get_mix_job(jid)
    if not job or not job.get("edit_plan"):
        return None, "작업 없음"
    w = Path(root) / jid
    final = pick_final(job, w)
    if not final:
        return None, "완성본 없음"
    plan = job["edit_plan"]
    tts = {k: v for k, v in mp.tts_paths_of(plan).items() if v and Path(v).exists()}
    if not tts:
        return None, "음성 없음"
    tl = va._beat_timeline(plan, tts)
    fm = final.stat().st_mtime
    by = {b["beat_idx"]: b for b in plan["beats"]}
    beats = [{"idx": x["beat_idx"], "tts": tts[x["beat_idx"]], "head_trim": float(x.get("head_trim") or 0.0),
              "dur": float(x["dur"]), "t0": float(x["t0"]),
              "stale": Path(tts[x["beat_idx"]]).stat().st_mtime > fm + STALE_SLACK} for x in tl]
    sfx_paths = mp._resolve_sfx_paths(store, plan, job.get("customer_id", 0), job=job)
    deco = mp.resolve_deco_media(job.get("deco") or {}, w)
    sfx_vol = max(0.0, min(1.0, (deco.get("sfx_volume", 60)) / 100.0))      # = video_assemble._burn_captions
    evs = va.sfx_events_for(tl, sfx_paths)
    # 효과음이 어느 칸 것인지(표기용) — 절대초가 들어가는 칸
    def _beat_at(t):
        for x in tl:
            if x["t0"] - 1e-6 <= t < x["t0"] + x["dur"] - 1e-6:
                return x["beat_idx"]
        return tl[-1]["beat_idx"] if tl else None
    sfx = [{"path": e[0], "t": float(e[1]), "vol": sfx_vol * (float(e[2]) if len(e) > 2 else 1.0), "beat": _beat_at(float(e[1]))}
           for e in evs]
    bgm = deco.get("bgm") or {}
    bg = ({"path": bgm["_abspath"], "vol": max(0.0, min(1.0, (bgm.get("volume", 15)) / 100.0))}      # = _burn_captions
          if bgm.get("_abspath") and os.path.exists(bgm["_abspath"]) else None)
    on, _sel, isec = mp._intro_choice(job.get("thumbnail"))
    intro = float(isec or 1.2) if on else 0.0
    meta = {"final": str(final), "final_name": final.name, "pack": (sfx_paths.get("_pack") or {}).get("name"),
            "bgm_cfg": {k: bgm.get(k) for k in ("file", "volume")} if bgm else None,
            "bgm_file_missing": bool(bgm.get("file") and not bg), "status": job.get("status"),
            "scene_style": bool((job.get("deco") or {}).get("scene_style"))}
    return {"final": str(final), "intro": intro, "beats": beats, "sfx": sfx, "bgm": bg, "meta": meta,
            "_by": len(by)}, ""


def line(jid, ctx, r, j, sec):
    m = ctx.get("meta") or {}
    lv = [x for x in r["rows"] if x.get("err_v") is not None and not x["stale"]]
    mx = max(lv, key=lambda x: abs(x["err_v"]), default=None)
    last = r["rows"][-1] if r["rows"] else {}
    b = r["bgm"] or {}
    if b.get("expect"):
        bg = "BGM 기대 %sdB 실측 %s(상관 %s)%s" % (b.get("exp_db"), b.get("rel_db"), b.get("r"), " ★이상" if b.get("bad") else "")
    else:
        bg = "BGM 없음(잔여 %sdB)%s" % (b.get("resid_db"), " ★파일 사라짐" if m.get("bgm_file_missing") else "")
    return ("%s 칸%d 인트로%.1f(실측%.1f) 길이%.2f(기대%.2f,%+.3f) | 마지막칸 음성-영상 %s 음성-자막 %s 영상-자막 %s (pts참고 %s, 수리전예측 %s) "
            "| 음성-영상 최대 %s | 음성-영상0.15+ %s | 음성-자막0.15+ %d칸 | 끝잘림 %s초(꼬리 %sdB) | 못찾음 %s | 렌더뒤음성바뀜 %s"
            " | 효과음 %d발(팩 %s) 누락 %d 타점0.10+ %d | %s | %.0fs") % (
        jid, j["n"], ctx["intro"], r.get("intro_used", ctx["intro"]), r["len"]["got"], r["len"]["exp"], r["len"]["diff"],
        last.get("err_v"), last.get("err"), last.get("vid_minus_cap"), last.get("err_pts"), last.get("pred_prefix"),
        "%s칸 %+.3f(%s)" % (mx["beat"], mx["err_v"], mx["ref_kind"]) if mx else "-",
        [(x["beat"], x["err_v"]) for x in j["narr_bad"]], len(j["cap_bad"]), r.get("tail_cut"), r.get("tail_db"),
        [(x["beat"], x["ncc"]) for x in j["narr_lost"]], [x["beat"] for x in j["stale"]],
        j["sfx_n"], m.get("pack") or "-", len(j["sfx_miss"]), len(j["sfx_off"]), bg, sec)


def main():
    args = sys.argv[1:]
    n = int(args[0]) if args and args[0].isdigit() else 10
    ids = [a for a in args if not a.isdigit()]
    db = "shopping_shorts/data/reference.db"
    store = ro_store(db)
    if not ids:
        con = sqlite3.connect("file:%s?mode=ro" % Path(db).resolve().as_posix(), uri=True)
        cand = [r for r in con.execute("select job_id, video_path from mix_jobs where status='done' and video_path is not null "
                                       "order by updated_at desc limit 200")]
        ids = [jid for jid, vp in cand if vp and Path(vp).exists()][:n]
    OUT.mkdir(parents=True, exist_ok=True)
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    smp = open(OUT / "samples.jsonl", "w", encoding="utf-8")
    print("판정: 나레이션 ±%.1fs(못 찾으면 ±%.1fs) NCC>=%.2f · 오차 %.2fs+ 보고 / 효과음 잔여 NCC>=%.2f · 타점 %.2fs+ / "
          "BGM 기대 dB(=20log10 볼륨) ±%.0fdB·상관>=%.2f / 길이 %.2fs+" % (WIN, WIDE, NARR_MIN, SHIFT_T, SFX_MIN, SFX_SHIFT_T,
                                                                    BGM_DB_T, BGM_MIN_R, LEN_T), file=rep, flush=True)
    tot = dict(n=0, nb=0, sm=0, bg=0, ln=0, lost=0, skip=0, stale=0, soff=0)
    for jid in ids:
        t0 = time.time()
        try:
            ctx, why = expected(store, jid)
            if not ctx:
                print(jid, "건너뜀", why, file=rep, flush=True); tot["skip"] += 1; continue
            r = audit(ctx)
        except Exception as e:      # noqa: BLE001
            print(jid, "건너뜀 %s: %s" % (type(e).__name__, str(e)[:160]), file=rep, flush=True); tot["skip"] += 1; continue
        j = judge(r)
        print(line(jid, ctx, r, j, time.time() - t0), file=rep, flush=True)
        smp.write(json.dumps({"job": jid, "meta": ctx.get("meta"), "intro": ctx["intro"], **r}, ensure_ascii=False) + "\n")
        tot["cb"] = tot.get("cb", 0) + len(j["cap_bad"])
        tot["n"] += j["n"]; tot["nb"] += len(j["narr_bad"]); tot["lost"] += len(j["narr_lost"]); tot["stale"] += len(j["stale"])
        tot["sm"] += len(j["sfx_miss"]); tot["soff"] += len(j["sfx_off"]); tot["bg"] += j["bgm_bad"]; tot["ln"] += j["len_bad"]
    print("== 칸 %d · 나레이션 %.2f초+ 오차 %d · 효과음 누락 %d · BGM 이상 %d · 음성-자막 %.2f초+ %d · 나레이션 못찾음 %d"
          " · 효과음 타점%.2f+ %d · 길이 이상 %d · 렌더뒤음성바뀜 %d · 건너뜀 %d   (나레이션 오차 = 음성 vs 영상 칸 첫 그림)" % (
              tot["n"], SHIFT_T, tot["nb"], tot["sm"], tot["bg"], SHIFT_T, tot.get("cb", 0), tot["lost"], SFX_SHIFT_T,
              tot["soff"], tot["ln"], tot["stale"], tot["skip"]), file=rep, flush=True)
    rep.close(); smp.close()
    print((OUT / "report.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
