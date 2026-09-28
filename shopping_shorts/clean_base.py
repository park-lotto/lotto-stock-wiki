# -*- coding: utf-8 -*-
"""청소본 정본(clean base) — 자막제거는 job당 한 번 (2026-09-22 사장님 대전제).

4단계에서 지운 완성본(final_clean_{sig}.mp4)을 **정본**으로 두고, 그 시점의 컷 지도를
work/<job>/clean_base.json 에 남긴다. 최종렌더·미리보기·프레임·캡컷·ZIP은 편성표의
재료를 청소본 좌표("clean", t0, t1)로 바꾼 **파생 사본**(remap_plan)으로 조립한다 →
VMake를 다시 안 탄다. 재료(장면)가 바뀐 비트만 uncovered로 돌려주고, 그 비트는
mix_pipeline.incremental_clean 이 원본에서 잘라 1콜로 지워 extras 에 넣는다.

★판정은 여기 두 함수뿐이다(0순위-B): load_base(무엇이 청소본인가) · remap_plan(재료가 어디인가).
★파생 사본은 DB에 저장하지 않는다. 원본 edit_plan은 손대지 않는다.

왜(실측 2026-09-22): 7일 350 job이 평균 1.65회 과금, 37%가 최종렌더에서 재과금. 원인 173쌍 중
자막 줄 나누기 67·확대 25·등급 20·장면 교체 13 — 그림이 바뀌면 완성본을 통째로 다시 지우던 구조.
"""
import copy
import os
import json
from pathlib import Path

BASE_FILE = "clean_base.json"
CLEAN_VID = "clean"
STRETCH_MAX = 0.10      # 이만큼까진 느리게 재생으로 채운다(그 다음은 정지) — plan_beat_clips_for 가 한다
EXTEND_MIN = 0.30       # 부족분이 컷의 이 비율을 넘으면 원본에서 더 잘라 증분 청소
EXTEND_PAD = 0.2        # 증분 조각 뒤 여유(초)


def beat_material_key(beat):
    """비트의 재료를 (video_id, start, end) 튜플열로. mix_pipeline._beat_materials 규칙 그대로."""
    from shopping_shorts.mix_pipeline import _beat_materials
    out = []
    for m in _beat_materials(beat or {}):
        try:
            out.append((str(m.get("video_id")), round(float(m.get("start")), 3), round(float(m.get("end")), 3)))
        except (TypeError, ValueError):
            out.append((str(m.get("video_id")), None, None))
    return tuple(out)


_ROOT = Path(__file__).resolve().parent.parent     # 저장소 루트 — 정본 파일 상대경로의 기준


def _abs_path(p):
    """정본·조각 경로를 절대경로로. 상대경로는 **저장소 루트** 기준(서비스 cwd = 루트일 때 쓰인 것).
    ★왜(2026-09-27 실측): 정본 392개 중 200개가 'shopping_shorts/data/...' 상대경로라 cwd 가 루트가 아닌
      도구·스크립트에선 load_base 가 '정본 없음'으로 오독했다."""
    q = Path(str(p))
    return str(q if q.is_absolute() else (_ROOT / q))


def _norm_paths(base):
    if base.get("path"):
        base["path"] = _abs_path(base["path"])
    for ex in (base.get("extras") or {}).values():
        if isinstance(ex, dict) and ex.get("path"):
            ex["path"] = _abs_path(ex["path"])
    return base


def _write(work, base):
    _norm_paths(base)                  # 저장은 늘 절대경로
    Path(work).mkdir(parents=True, exist_ok=True)
    (Path(work) / BASE_FILE).write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")


def save_base(work, *, sig, path, plan, cuts, sel=None):
    """청소 직후 호출. 컷 지도(final_clip_pairs 결과)와 그때의 재료 키를 비트별로 남긴다.

    sel: 고른 장면만 지웠으면 그 컷 키 목록(None=전체). cuts의 "cleaned"가 컷마다 지웠나를 말한다.
    ★안 고른 비트(컷이 하나도 안 지워진 비트)는 skip_beats — remap_plan이 원본 재료 그대로 두고
      증분 청소도 안 한다(고객이 안 고른 장면에 돈이 나가면 안 된다).
    """
    keys = {int(b["beat_idx"]): _key_list(beat_material_key(b))
            for b in (plan or {}).get("beats") or [] if b.get("beat_idx") is not None}
    base = {"sig": sig, "path": str(path), "cuts": [dict(c) for c in cuts or []],
            "beat_keys": {str(k): v for k, v in keys.items()}, "extras": {}}
    # 칸 길이 누적 프레임 수정(2026-09-27 00:12 KST 배포) 뒤에 만든 청소본은 컷 지도와 파일이 맞는다 — 보정 불필요.
    #   그 전 파일(재사용 분기로 지금 정본이 되는 옛 파일 포함)은 calibrate가 컷마다 밀림을 잰다.
    try:
        if Path(path).stat().st_mtime >= FRAME_EXACT_SINCE:
            base["frame_exact"] = True
    except OSError:
        pass
    if sel:
        wanted = {int(c["beat_idx"]) for c in cuts or [] if c.get("cleaned") and c.get("beat_idx") is not None}
        base["partial"] = True
        base["sel"] = list(sel)
        base["skip_beats"] = sorted(k for k in keys if k not in wanted)
    _write(work, base)
    return base


FRAME_EXACT_SINCE = 1790435500      # 2026-09-27 00:11:40 KST — _render_mix 누적 프레임 경계 배포 시각


CAL_VERSION = 5     # 1 = 앞뒤 0.4초 고정 창 → 2 = 앞 컷 값 기준 + 넓혀 재탐색 + 이어받기(62ed6 9번 칸 +0.37초 잔여)
                    # → 3 = 도구와 같은 특징(frame_match)·원본을 완성본 구도로 자름·컷 앞/끝 세 지점씩(off·off_end)·
                    #       못 재면 앞 컷과의 경계(튀는 프레임)로 시작만 · 다음 컷 시작에서 자르기(_cut_geom)
                    # → 4 = 속도 불일치 컷(cal_speed_mismatch) 표시 — 그 컷은 덮지 않은 것으로(_speed_bad)
                    # → 5 = frame_exact 정본도 **잰다**(2026-09-27) — frame_exact 표식은 칸 경계 수리(00:12) 시각으로만 붙어,
                    #       칸 안 컷 경계 수리(cut_frame_list, 05:11) 전 청소본은 칸 안에서 컷마다 1프레임씩 밀려 있었다
                    #       (39e55470ebb0 02:06 청소본: 칸 안 +1→+3, 뒤 칸 −3프레임 — 보정을 건너뛰어 완성본이 화면보다 3프레임 앞섬).
                    #       단 이 정본은 EXACT_MIN 이상 어긋난 컷만 좌표를 고친다(맞는 파일을 잡음으로 흔들지 않게).
EXACT_MIN = 1.5 / 30.0          # frame_exact 정본: 이 이상(2프레임) 어긋난 컷만 off/off_end 를 남긴다
CAL_WIN = 18                    # 찾는 범위 ±18프레임(±0.6초) — 기대 밀림(prior) 중심
CAL_AGREE = 1                   # 세 지점 **모두** 최소(후보)가 확정 밀림의 ±1프레임 안에 있어야 한다(하나라도 딴 데면 못 잼)
CAL_SPREAD = 3                  # …그중 둘 이상은 '최소 후보' 폭이 3프레임 이하로 뾰족해야 한다(정지 화면은 어디든 닮아 못 박는다)
CAL_MIN = 0.2                   # 이보다 짧은 컷은 재지 않는다(이어받기)
CAL_END_MIN = 0.95              # 이 이상 긴 컷만 끝 밀림(off_end)도 잰다 — 앞·끝 지점이 겹치지 않게
_OLD_SLOWMO = 1.15              # 옛 조립: 원본을 이 배율까지 느리게 재생, 남는 시간은 마지막 프레임 정지
SPEED_MISPLACE = 4              # 속도 불일치: 좌표(_cut_geom)대로 읽으면 컷 끝(또는 시작)에서 장면이 이만큼(프레임, 0.13초) 이상 어긋난다
SPEED_EVID = 3                  # …그리고 실제로 3프레임 이상 어긋난 지점이 SPEED_EVID 개 이상(한 점 튐으로 판정하지 않는다)
SPEED_WIN = 12                  # 속도 검사: 좌표가 말하는 자리 ±12프레임에서 찾는다
SPEED_MIN_PTS = 4               # …뾰족한(정지 화면 아닌) 지점이 이만큼 이상, 원본 0.4초 이상에 걸쳐 있어야 판정한다
SPEED_DMAX = 0.33               # …닮음 거리 이 이하 지점만(같은 장면 최대 0.45 근처 = 겨우 닮은 점은 증거로 안 쓴다)
SPEED_RESID = 1.0               # …직선(일정한 속도 차)에서 벗어난 정도 가운데값이 이 프레임 이하일 때만(흩어짐 = 잡음)
# ★속도 불일치 컷을 **재청소(과금) 대상**으로 칠지 — 기본 꺼짐(표식·경보만). 14일 실측 108컷/69 job = +118.7초(≈362크레딧)가
#   고객에게 추가 과금되는 일이라 사장님 승인 뒤 켠다(`CLEAN_SPEED_RECLEAN=1`). 꺼져 있어도 표식(cal_speed_mismatch)은 남고
#   매일 영상 점검(daily_video_audit)이 그 컷의 어긋남을 잡는다. 판정은 `_speed_bad` 한 곳.
SPEED_RECLEAN = os.environ.get("CLEAN_SPEED_RECLEAN", "0").strip() == "1"


def _ceil_frames(x):
    import math
    return math.ceil(float(x) * 30 - 1e-6) / 30.0


def old_frame_lag(cuts):
    """이론값(초): 옛 조립본에서 컷 시작이 컷 지도(fin)보다 늦은 양 — 컷 지도 fin 순서의 cuts 와 같은 길이 목록.

    옛 조립은 컷 조각·칸을 `-t 초`로 잘라 30fps 프레임 경계로 **올림**됐다(칸마다 ceil(tts*30)/30 - tts,
    칸 안 컷마다 ceil(dur*30)/30 - dur). 그게 뒤 칸일수록 쌓였다. 실측 우선 — 이건 탐색 시작점·이어받기 보정만."""
    lag, within, beat_sum, prev, out = 0.0, 0.0, 0.0, object(), []
    for c in cuts:
        bi = c.get("beat_idx")
        if bi != prev:
            if beat_sum > 0:
                lag += _ceil_frames(beat_sum) - beat_sum
            prev, within, beat_sum = bi, 0.0, 0.0
        out.append(lag + within)
        d = float(c.get("dur") or 0.0)
        within += _ceil_frames(d) - d
        beat_sum += d
    return out


def _src_vf(fm):
    """원본을 청소본과 같은 화면으로 — 옛 조립도 칸마다 꽉 채워 자르기(frame_vf, 기본 확대)를 걸었다.
    ★안 맞추면 가로 원본은 청소본(9:16로 잘린 것)과 가장 닮은 자리도 거리 0.3~0.45라 세 지점이 흩어진다(62ed6 실측)."""
    try:
        from shopping_shorts.video_assemble import frame_vf
        return frame_vf(None, fm.W, fm.H)
    except Exception:      # noqa: BLE001
        return "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (fm.W, fm.H, fm.W, fm.H)


def _group_shift(ff, rf, j0, kp, us, k0, why=None):
    """원본 컷 안 지점들(us, 초) 을 청소본 특징 ff 의 k0 ±CAL_WIN 프레임에서 찾아 **한 밀림**(프레임)으로 모이면 그 값, 아니면 None.

    뾰족한(최소 후보 폭 ≤ CAL_SPREAD — 정지 화면 아님) 지점이 둘 이상이고, 그 가운데값 밀림에서 **모든 지점**의
    최소(후보)가 ±CAL_AGREE 안에 있어야 한다. 한 지점이라도 다른 장면·다른 밀림이면 못 잰 것.
    why(list)를 주면 못 잰 사유를 하나 붙인다: "nomatch"(같은 장면 없음) · "static"(정지 화면) ·
      "speed"(지점 전부 뾰족한데 **뒤 지점일수록 밀림이 한쪽으로 커진다** — 옛 파일이 다른 배속으로 구워짐) · "disagree"."""
    import math
    import numpy as np
    from shopping_shorts import frame_match as fm
    ks = np.arange(k0 - CAL_WIN, k0 + CAL_WIN + 1)
    pts = []
    for u in us:
        i = int(round(u * fm.FPS))
        if not 0 <= i < len(rf):
            continue
        # 느리게(setpts) 30fps 출력: 청소본 j 프레임 = 원본 floor(j/kp) → 원본 i 가 처음 보이는 j = ceil(i*kp)
        d = fm.dist(ff, j0 + int(math.ceil(i * kp - 1e-6)) + ks, rf[i])
        m = np.isfinite(d)
        if not m.any():
            return _why(why, "nomatch")
        kb_p, dmin_p, ok_p = fm.pick(ks[m], d[m], k0)
        if dmin_p >= fm.SCENE_T:
            return _why(why, "nomatch")     # 이 지점과 같은 장면이 근처에 없다
        pts.append((kb_p, ok_p))
    if len(pts) < 2:
        return _why(why, "nomatch")
    sharp = [kb_p for kb_p, ok_p in pts if ok_p.max() - ok_p.min() <= CAL_SPREAD]
    if len(sharp) < 2:
        return _why(why, "static")          # 정지 화면이라 어디든 닮았다 — 밀림을 못 박는다
    kb = int(round(float(np.median(sharp))))
    for _kb_p, ok_p in pts:
        if np.abs(ok_p - kb).min() > CAL_AGREE:
            # 이 지점은 그 밀림에서 최소가 아니다(다른 밀림). 지점 전부 뾰족하고 밀림이 원본 시간 순으로 한쪽으로만
            # 커지면(2프레임 이상) 흩어진 게 아니라 **속도가 다른 것**이다.
            kbs = [p[0] for p in pts]
            dif = np.diff(kbs)
            mono = len(pts) == len(us) >= 3 and len(sharp) == len(pts) and (np.all(dif > 0) or np.all(dif < 0))
            return _why(why, "speed" if mono and abs(kbs[-1] - kbs[0]) >= 2 else "disagree")
    return kb


def _why(why, reason):
    if why is not None:
        why.append(reason)
    return None


def _cut_src(c, src_paths):
    """원본 컷 구간 특징 → (rf, kp, sd) 또는 None. kp = 옛 조립 재생 배율(1.15배까지 느리게, 그 뒤 정지)."""
    from shopping_shorts import frame_match as fm
    src = (src_paths or {}).get(c.get("video_id"))
    dur = float(c.get("dur") or 0.0)
    sd = _f(c.get("sdur") or dur, dur)
    sd = sd if sd > 1e-6 else dur
    if not src or dur < CAL_MIN or sd < CAL_MIN:
        return None
    kp = dur / sd if dur <= sd * _OLD_SLOWMO + 1e-6 else _OLD_SLOWMO
    s0 = float(c["src"])
    rf = fm.feats(fm.frames(src, s0, sd + 0.1, timeout=60, pre_vf=_src_vf(fm)))
    if len(rf) < int(round(sd * fm.FPS)) - 1:
        # 원본이 컷 끝보다 짧다 — 옛 조립은 시작을 원본 안으로 당겨 읽었다(start = min(start, 원본길이 - sdur))
        fd = fm.duration(src)
        if fd > 0 and s0 + sd > fd:
            rf = fm.feats(fm.frames(src, max(0.0, fd - sd), sd + 0.1, timeout=60, pre_vf=_src_vf(fm)))
    return (rf, kp, sd) if len(rf) else None


def _measure_cut(c, cs_, ff, prior, why=None):
    """컷 하나의 (시작 밀림 off, 끝 밀림 off_end|None) 초 — 시작을 확신 못 하면 None. cs_ = _cut_src 결과.

    시작: 원본 컷 앞쪽 세 지점(긴 컷 0.2·0.3·0.4초 / 짧은 컷 sdur의 15·35·55%)을 prior ±0.6초에서 찾는다.
    끝:   원본 컷 끝-0.4·-0.3·-0.2초 세 지점(sdur ≥ CAL_END_MIN 일 때만)을 시작 밀림 ±0.6초에서 찾는다.
    off_end = 원본 컷 끝이 청소본에서 보일 자리 - (fin + dur). _cut_geom 이 구간 길이 = dur + off_end - off 로 읽는다.
    옛 조립 컷 안 시간 = 원본 u초 → 청소본 fin + off + u*kp (정지 몫은 구간 밖)."""
    from shopping_shorts import frame_match as fm
    if not cs_:
        return None
    rf, kp, sd = cs_
    fin, dur = float(c["fin"]), float(c["dur"])
    j0 = int(round(fin * fm.FPS))
    long_ = sd >= CAL_END_MIN
    us = (0.2, 0.3, 0.4) if long_ else tuple(q * sd for q in (0.15, 0.35, 0.55))
    kb = _group_shift(ff, rf, j0, kp, us, int(round(prior * fm.FPS)), why=why)
    if kb is None:
        return None
    off = (j0 + kb) / fm.FPS - fin
    off_end = None
    if long_:
        ke = _group_shift(ff, rf, j0, kp, (sd - 0.4, sd - 0.3, sd - 0.2), kb)
        if ke is not None:
            off_end = (j0 + ke) / fm.FPS + sd * kp - fin - dur
    return off, off_end


CUT_T = 0.40            # 청소본 이웃 프레임 특징 거리가 이 이상 = 눈에 보이는 컷 경계(영상 비교 도구와 같은 값)
CAL_BWIN = 6            # 경계로 잴 땐 기대 시작 ±6프레임만 — 같은 원본이 이어지는 컷은 앞 컷 안에도 닮은 경계가 있다
                        #   (±0.6초로 찾다 62ed6 23번 컷이 -0.09초(이웃 0.47초)로 잡힌 실측)


def _boundary_start(ff, mot, j_lo, j_exp, cs_):
    """앞 컷 시작(j_lo) 뒤, 기대 시작(j_exp) ±CAL_BWIN 프레임 안의 **컷 경계**(특징이 튀는 프레임) 중 원본 컷 첫머리와 닮은 것 →
    이 컷의 청소본 시작 프레임. 정지 화면 컷도 앞 컷과의 경계는 보인다(세 지점으로 못 재는 컷을 여기서 잰다)."""
    import math
    import numpy as np
    from shopping_shorts import frame_match as fm
    if not cs_:
        return None
    rf, kp, _sd = cs_
    i0 = min(2, len(rf) - 1)            # 경계 첫 프레임은 섞일 수 있어 2프레임 안쪽을 본다
    di = int(math.ceil(i0 * kp - 1e-6))
    lo, hi = max(j_lo + 3, j_exp - CAL_BWIN, 1), min(len(ff) - 1 - di, j_exp + CAL_BWIN)
    js = [j for j in range(lo, hi + 1) if mot[j] >= CUT_T]
    if not js:
        return None
    sc = sorted((float(np.abs(ff[j + di] - rf[i0]).mean()), abs(j - j_exp), j) for j in js)
    if sc[0][0] >= fm.SCENE_T:
        return None
    if len(sc) > 1 and sc[1][0] < sc[0][0] + 0.1 and abs(sc[1][2] - sc[0][2]) > 1:
        return None                     # 비슷하게 닮은 경계가 둘 — 못 고른다
    return sc[0][2]


def _speed_drift(c, cs_, ff, nxt):
    """좌표(_cut_geom)대로 읽으면 컷 안에서 장면이 **가장 크게 어긋나는 양**(프레임, ≥0) — 속도 차가 증거로 보일 때만.
    어긋남이 증거로 안 보이면 0.0, 잴 지점이 모자라면 None.

    원본 컷을 0.1초마다 한 장씩, 좌표가 말하는 청소본 자리 ±SPEED_WIN 에서 가장 닮은 프레임을 찾는다.
    뾰족하고(정지 화면 아님) 잘 닮은(≤SPEED_DMAX) 지점이 SPEED_MIN_PTS 이상 원본 0.4초 넘게 모이면
    한 직선(일정한 속도 차 — 기울기는 쌍별 기울기 가운데값, 한 점 튐에 안 끌린다)으로 맞춰 컷 양 끝 어긋남을 본다.
    ★직선에서 흩어지면(가운데 잔차 > SPEED_RESID) 속도 차가 아니다 → 0.0.
    ★실제로 SPEED_EVID(3)프레임 이상 어긋난 지점이 SPEED_EVID 개 미만이면 0.0 — 컷 안 한 번 튐(프레임 몇 장 빠짐)이
      직선에 1~2프레임씩 나눠 보이는 것까지 돈 내고 다시 지우지 않는다(실측 018382 3번 컷: 앞 +1·뒤 −2).
    ★렌더가 읽을 좌표 그대로(다음 컷 시작에서 자른 구간 안만) 잰다 — 판정 대상이 곧 렌더가 쓰는 것."""
    import numpy as np
    from shopping_shorts import frame_match as fm
    if not cs_:
        return None
    rf, _kp, _sd = cs_
    cs, ce, t0, k = _cut_geom(c, nxt)
    n = min(len(rf), int((ce - cs) * fm.FPS))
    ks = np.arange(-SPEED_WIN, SPEED_WIN + 1)
    pts = []
    for i in range(0, n, 3):
        jp = int(round((t0 + i / fm.FPS * k) * fm.FPS))
        d = fm.dist(ff, jp + ks, rf[i])
        m = np.isfinite(d)
        if not m.any():
            continue
        kb, dmin, ok = fm.pick(ks[m], d[m], 0)
        if dmin > SPEED_DMAX or ok.max() - ok.min() > CAL_SPREAD:
            continue
        pts.append((i / fm.FPS, kb))
    if len(pts) < SPEED_MIN_PTS or pts[-1][0] - pts[0][0] < 0.4 - 1e-6:
        return None
    u = np.array([p[0] for p in pts]); v = np.array([p[1] for p in pts], float)
    iu, ju = np.triu_indices(len(u), 1)
    du = u[ju] - u[iu]
    b = float(np.median((v[ju] - v[iu])[du > 1e-9] / du[du > 1e-9]))
    a = float(np.median(v - b * u))
    if float(np.median(np.abs(v - (a + b * u)))) > SPEED_RESID:
        return 0.0                      # 직선이 아니다 — 속도 차가 아니라 잡음·딴 장면
    if int(np.sum(np.abs(v) >= SPEED_EVID)) < SPEED_EVID:
        return 0.0
    return float(max(abs(a + b * u[0]), abs(a + b * u[-1])))


def _geom_resid(c, cs_, ff, nxt):
    """좌표(_cut_geom)대로 읽을 때 컷 **전 구간**에서 장면이 2프레임 이상 어긋난 지점 수 → (어긋난 수, 잰 지점 수) 또는 None.
    원본 0.1초마다 한 장을 좌표가 말하는 청소본 자리 ±10프레임에서 찾는다(뾰족하고 잘 닮은 지점만 — _speed_drift 와 같은 기준).
    frame_exact 정본에서 새로 잰 좌표가 **실제로 더 맞을 때만** 쓰는 판정(v5) — 세 지점 측정이 빗나가 멀쩡한 컷을 흔들지 않게."""
    import numpy as np
    from shopping_shorts import frame_match as fm
    if not cs_:
        return None
    rf = cs_[0]
    cs, ce, t0, k = _cut_geom(c, nxt)
    n = min(len(rf), int((ce - cs) * fm.FPS))
    ks = np.arange(-10, 11)
    bad = tot = 0
    for i in range(0, n, 3):
        jp = int(round((t0 + i / fm.FPS * k) * fm.FPS))
        d = fm.dist(ff, jp + ks, rf[i])
        m = np.isfinite(d)
        if not m.any():
            continue
        kb, dmin, ok = fm.pick(ks[m], d[m], 0)
        if dmin > SPEED_DMAX or ok.max() - ok.min() > CAL_SPREAD:
            continue
        tot += 1
        bad += abs(int(kb)) >= 2
    return (bad, tot) if tot else None


def _speed_bad(c):
    """속도 불일치로 **청소본 좌표를 못 믿는** 지운 컷 — 지워진 조각으로 치지 않는다(렌더가 그 칸만 증분 청소).
    ★안 지운 컷(cleaned:false — 부분 청소 정본에서 원래 안 지우는 컷)은 표식만 남기고 과금 대상이 아니다."""
    return SPEED_RECLEAN and bool(c.get("cal_speed_mismatch")) and c.get("cleaned") is not False


def calibrate(work, base, src_paths):
    """옛 청소본(frame_exact 없음)의 컷마다 **실제 밀림(off)**을 한 번 재서 정본에 남긴다(2026-09-27).

    왜: 청소본은 조립본(mix_raw)을 지운 것인데, 옛 조립본은 칸마다 프레임 올림이 쌓여 뒤 칸일수록 장면이
      컷 지도(fin, 음성 길이 누적)보다 늦게 들어 있었다(실측 7bbb 3번 칸 +0.132초, 62ed6 뒤 칸 +0.43초+).
      재생이 fin 으로 읽으면 화면보다 앞 장면이 나온다. 청소를 다시 하지 않고(돈 0) 원본↔청소본 프레임을 맞춰 잰다.
    v3(2026-09-27): v2(회색 절대차·프레임 1장)는 62ed6 9번 칸에서 -0.33초를 남겼다 → 영상 비교 도구와 **같은 특징**
      (frame_match — 가운데 띠·5x5·z정규화)으로 청소본을 통째 한 번 풀고, 컷 안 세 지점이 같은 밀림에서 최소일 때만 확정.
    ★컷마다 시작(off)과 끝(off_end) 둘 다 잰다 — 옛 조각은 끝도 밀리고 길이도 지도와 달랐다(a90253dd235b). 끝을 못 재면
      off_end 없음(구간 길이 = dur) — 그래도 _cut_geom 이 다음 컷 시작에서 잘라 다음 조각을 읽지 않는다.
    ★탐색 중심·이어받기 = 앞 컷 실측 + 이론 증가분(old_frame_lag). 못 잰 컷은 cal_unsure=True(정본의 cal_unsure = 개수).
    ★부분 청소 정본의 안 지운 컷(cleaned:false)도 같은 조립본에서 왔다 — 똑같이 잰다.
    ★v4: 속도 불일치 컷 = 컷 안에서 내용이 좌표보다 점점 빠르거나 느리게 흐르는 컷(옛 조립이 다른 배속으로 구움 —
      _speed_drift ≥ SPEED_MISPLACE 프레임 = cal_speed_by "drift", 또는 시작 세 지점이 "speed" 사유로 못 모였는데
      드리프트를 잴 지점이 모자람 = "start").
      cal_speed_mismatch=True — _regions·piece_map·coverage 가 그 컷을 **덮지 않은 것**으로 본다(맞는 장면 우선:
      딴 속도로 내보내느니 그 칸만 돈 내고 지운다). 정본의 cal_speed = 그런 컷 수.
    ★한 번 재면 calibrated=CAL_VERSION. 옛 버전 표시는 다시 잰다."""
    if not base or base.get("calibrated") == CAL_VERSION:
        return base
    exact = bool(base.get("frame_exact"))       # v5: frame_exact 도 잰다 — 2프레임 이상 어긋난 컷만 고친다
    try:
        from shopping_shorts import frame_match as fm
        ff = fm.feats(fm.frames(base["path"]))
        if not len(ff):
            raise RuntimeError("청소본 프레임 0장")
        import numpy as np
        mot = np.zeros(len(ff), np.float32)
        mot[1:] = np.abs(ff[1:] - ff[:-1]).mean(axis=(1, 2))
        cuts = sorted(base.get("cuts") or [], key=lambda x: float(x.get("fin") or 0))
        theo = old_frame_lag(cuts)
        last, unsure, j_prev = None, 0, -10 ** 6
        srcs, whys = [], []
        for c, th in zip(cuts, theo):
            for k in ("off", "off_end", "cal_unsure", "cal_by", "cal_speed_mismatch", "cal_speed_by"):
                c.pop(k, None)
            prior = th if last is None else last[0] + (th - last[1])
            fin = float(c["fin"])
            cs_, why = None, []
            try:
                cs_ = _cut_src(c, src_paths)
                got = _measure_cut(c, cs_, ff, prior, why=why)
                if got is None:         # 세 지점으로 못 쟀다 → 앞 컷과의 경계로 시작만 잰다
                    jb = _boundary_start(ff, mot, j_prev, int(round((fin + prior) * fm.FPS)), cs_)
                    if jb is not None:
                        got = (jb / fm.FPS - fin, None)
                        c["cal_by"] = "cut"
            except Exception:      # noqa: BLE001 — 원본 하나가 깨져도 나머지 컷은 잰다
                got = None
            if got is None:
                off = prior
                c["cal_unsure"] = True
                unsure += 1
            else:
                off, off_end = got
                last = (off, th)
                if off_end is not None:
                    c["off_end"] = round(off_end, 3)
            if exact and got is not None:
                # 맞게 만든 파일(frame_exact)은 잡음(±1프레임)으로 흔들지 않는다 — 2프레임 이상만 고친다
                if c.get("off_end") is not None and abs(float(c["off_end"])) < EXACT_MIN and abs(off) < EXACT_MIN:
                    c.pop("off_end", None)
                if abs(off) < EXACT_MIN and "off_end" not in c:
                    off = 0.0
            elif exact:
                off = 0.0                       # 못 잰 컷 — 맞게 만든 파일이니 지도 그대로(이어받기 추정으로 옮기지 않는다)
                c.pop("cal_unsure", None); unsure -= 1
            j_prev = int(round((fin + off) * fm.FPS))
            if abs(off) >= 0.5 / fm.FPS or "off_end" in c:
                c["off"] = round(off, 3)
            srcs.append(cs_); whys.append(why)
        if exact:
            # frame_exact 정본: 새 좌표가 **전 구간 대조에서 실제로 더 맞는** 컷만 남긴다(v5). 세 지점 측정이 빗나가면
            #   멀쩡한 컷을 오히려 흔든다(68b48b12c7f5 실측: 고치지 않으면 어긋난 지점 소수 → 세 지점 값 그대로 쓰면 38).
            nx0 = _next_starts({"cuts": cuts})
            for c, cs_, nxt in zip(cuts, srcs, nx0):
                if c.get("off") is None and c.get("off_end") is None:
                    continue
                plain = {k_: v_ for k_, v_ in c.items() if k_ not in ("off", "off_end")}
                try:
                    after, before = _geom_resid(c, cs_, ff, nxt), _geom_resid(plain, cs_, ff, nxt)
                except Exception:      # noqa: BLE001
                    after = before = None
                if after is None or before is None or after[0] >= before[0]:
                    c.pop("off", None); c.pop("off_end", None)
                    c.pop("cal_by", None)
                else:
                    c["cal_by"] = (c.get("cal_by") or "points") + "+verified"
        # 속도 검사 — 모든 컷 밀림이 정해진 뒤(다음 컷 시작에서 자른 좌표 = 렌더가 읽는 좌표로 잰다)
        nx = _next_starts({"cuts": cuts})
        n_speed = 0
        for c, cs_, why, nxt in zip(cuts, srcs, whys, nx):
            try:
                dr = _speed_drift(c, cs_, ff, nxt)
            except Exception:      # noqa: BLE001
                dr = None
            by = "drift" if (dr is not None and dr >= SPEED_MISPLACE) else (
                "start" if (dr is None and "speed" in why) else None)
            if by:
                c["cal_speed_mismatch"] = True
                c["cal_speed_by"] = by
                n_speed += 1
        base["calibrated"] = CAL_VERSION
        base["cal_unsure"] = unsure
        base["cal_speed"] = n_speed
        _write(work, base)
    except Exception as e:      # noqa: BLE001 — 보정 실패는 종전과 같다(0)
        import sys
        print("[clean-base] 밀림 보정 실패(무시): %s" % e, file=sys.stderr)
    return base


def load_base(work):
    """정본이 있고 파일이 살아 있으면 dict, 아니면 None(호출부는 종전 경로로)."""
    p = Path(work) / BASE_FILE
    if not p.exists():
        return None
    try:
        base = _norm_paths(json.loads(p.read_text(encoding="utf-8")))
        f = Path(base["path"])
        if not (f.exists() and f.stat().st_size > 1024):
            return None
        base.setdefault("extras", {})
        base.setdefault("beat_keys", {})
        return base
    except Exception:      # noqa: BLE001 — 깨진 정본은 없는 것으로(종전 경로 폴백)
        return None


def add_extra(work, base, *, vid, path, beat_idx, material_key, seconds, src_vid=None, src_start=None):
    """증분 청소 조각을 정본에 붙인다. 같은 재료 키로 다시 오면 covered.
    src_vid·src_start: 원본 어디를 지웠나 — 있으면 렌더 컷 재생(span_map)이 이 조각도 쓴다."""
    ex = {"path": str(path), "beat_idx": int(beat_idx),
          "key": _key_list(material_key), "seconds": float(seconds)}
    if src_vid is not None and src_start is not None:
        ex["src_vid"], ex["src_start"] = str(src_vid), float(src_start)
    base.setdefault("extras", {})[vid] = ex
    _write(work, base)
    return base


def _key_list(k):
    return [list(x) for x in k]


def _extra_for(base, beat_idx, key, prefix="cb"):
    """이 비트·재료 키의 증분 조각. prefix="cb"=바뀐 장면 조각(cb{bi}_{k}) · "cbx"=늘림 조각(cbx{bi})."""
    for vid, ex in (base.get("extras") or {}).items():
        is_x = vid.startswith("cbx")
        if (prefix == "cbx") != is_x:
            continue
        if int(ex.get("beat_idx", -1)) == int(beat_idx) and ex.get("key") == _key_list(key):
            if Path(ex.get("path", "")).exists():
                return vid, ex
    return None, None


def _cuts_of(base, beat_idx):
    return [c for c in base.get("cuts") or [] if int(c.get("beat_idx", -1)) == int(beat_idx)]


MIN_PIECE = 0.25        # 청소본 컷과 이만큼 이상 겹쳐야 그 조각을 쓴다(초)


def piece_map(base, material, cleaned_only=False):
    """재료 조각 (video_id, start, end) 이 청소본 **어디에든** 있으면 그 자리를 청소본 좌표로 돌려준다.
    반환 [{"video_id":"clean","seg_id":"clean-<i>","start":t0,"end":t1}, ...] (겹치는 컷마다 하나, 원본 시간순) — 없으면 [].

    ★왜(2026-09-22 사장님 job 956a6843cdd5): 장면편집으로 조각을 빼거나 다른 칸으로 옮기면 칸 단위 재료 키가
      달라져 '바뀐 장면'이 됐다(9칸 중 6칸, 25.4초 재청소 안내). 그런데 쓰는 조각은 전부 이미 청소돼 있었다.
      조각이 청소본에 있으면 그걸 쓴다 — 칸이 바뀐 게 아니라 조각이 옮겨간 것이다."""
    try:
        vid = str(material.get("video_id")); s = float(material.get("start")); e = float(material.get("end"))
    except (TypeError, ValueError):
        return []
    out = []
    cuts = base.get("cuts") or []
    nx = _next_starts(base)
    for i, c in enumerate(cuts):
        if str(c.get("video_id")) != vid:
            continue
        if cleaned_only and c.get("cleaned") is False:
            continue            # 고른 장면만 지운 정본 — 안 지운 컷을 '지운 조각'으로 빌려 쓰지 않는다
        if _speed_bad(c):
            continue            # 속도 불일치 컷 — 좌표를 못 믿는다(_regions 와 같은 판단)
        cs, ce, fin, k = _cut_geom(c, nx[i])
        lo, hi = max(s, cs), min(e, ce)
        if hi - lo >= MIN_PIECE:
            out.append((lo, {"video_id": CLEAN_VID, "seg_id": "%s-%d" % (CLEAN_VID, i),
                             "start": round(fin + (lo - cs) * k, 3), "end": round(fin + (hi - cs) * k, 3)}))
    out.sort(key=lambda x: x[0])
    return [x[1] for x in out]


def _f(v, dflt=0.0):
    try:
        return float(v) if v is not None else dflt
    except (TypeError, ValueError):
        return dflt


def _cut_geom(c, nxt=None):
    """청소본 컷 하나 → (원본 시작, 원본 끝, 청소본 시작, 원본1초당 청소본 초). **청소본 컷 좌표의 유일한 자리.**

    ★원본 끝은 sdur(원본에서 실제로 읽은 길이)로 잰다. dur는 완성본 길이라 느리게·정지로 늘어난 컷이면
      원본의 **안 지운 구간**까지 덮었다고 오판한다(2026-09-26). sdur 없는 옛 정본은 dur 그대로(종전).
    ★옛 청소본(calibrate 가 잰 것): 청소본 시작 = fin + off, 청소본 구간 길이 = dur + off_end - off
      (off_end 없으면 dur — 종전). 옛 조립본은 조각 **끝**도 밀리고 길이도 지도와 달랐다(2026-09-27 a90253dd235b).
    ★nxt = fin 순서상 다음 컷의 청소본 시작. 이 컷 구간이 거기를 넘으면 **거기서 자른다**(원본 끝도 그만큼 당긴다) —
      무엇을 못 재도 다음 조각 장면을 읽지 않는다(3→4칸 경계에서 다음 칸 장면이 6프레임 먼저 나온 사고)."""
    cs = float(c["src"]); dur = float(c["dur"])
    sd = _f(c.get("sdur") or dur, dur)
    sd = sd if sd > 1e-6 else dur
    off = _f(c.get("off"))                 # 옛 청소본 밀림(calibrate) — 파일 안 장면이 컷 지도(fin)보다 늦게 들어 있다
    span = dur
    if c.get("off_end") is not None:
        span = dur + _f(c.get("off_end")) - off
        if span <= 1e-3:
            span = dur
    k = span / sd if sd > 1e-6 else 1.0
    t0 = float(c["fin"]) + off
    ce = cs + sd
    if nxt is not None and t0 + span > nxt + 1e-4:
        ce = cs + max(0.0, nxt - t0) / k
    return cs, ce, t0, k


def _next_starts(base):
    """컷 번호 → fin 순서상 다음 컷의 청소본 시작(fin+off). 마지막 컷은 None."""
    cuts = base.get("cuts") or []
    order = sorted(range(len(cuts)), key=lambda i: _f(cuts[i].get("fin")))
    out = [None] * len(cuts)
    for a, b in zip(order, order[1:]):
        if _f(cuts[b].get("fin")) > _f(cuts[a].get("fin")) + 1e-6:
            out[a] = _f(cuts[b].get("fin")) + _f(cuts[b].get("off"))
    return out


def _geom_in(base, c):
    """base 안 컷 c 의 좌표(다음 컷 시작에서 자르기 포함)."""
    cuts = base.get("cuts") or []
    nx = _next_starts(base)
    for i, x in enumerate(cuts):
        if x is c:
            return _cut_geom(c, nx[i])
    return _cut_geom(c)


def _clean_span(base, c):
    """base 안 컷 c 가 청소본에서 차지하는 (시작, 끝) 초."""
    cs, ce, t0, k = _geom_in(base, c)
    return t0, t0 + (ce - cs) * k


def cut_span_in_clean(base, i):
    """정본 컷 i 가 청소본에서 차지하는 (시작, 끝) 초 — **화면(전/후 비교)도 이걸로 좌표를 잡는다**.

    ★왜(2026-09-27 사장님 화면): 옛 청소본은 칸마다 프레임 올림이 누적돼 지도(fin)보다 최대 0.33초 늦게 들어 있다.
      렌더는 calibrate 가 잰 off 로 맞추는데(_cut_geom), 비교 화면은 fin 을 그대로 써서 샷 전환에 걸린 컷이
      '다른 장면'으로 보였다(8c63b0691924 컷2: +0.13초). 판단은 여기 한 곳 — 화면은 계산하지 않고 부른다.
    없는 번호면 None."""
    cuts = base.get("cuts") or []
    if not (0 <= int(i) < len(cuts)):
        return None
    return _clean_span(base, cuts[int(i)])


SPAN_TOL = 0.12         # 이만큼 이하 틈은 이어 붙인다(프레임 반올림) — 그보다 크면 못 덮은 것


def _regions(base):
    """지워진 원본 구간 전부: (조립 vid, seg_id, 원본 vid, 원본 시작, 원본 끝, 조립 시작, 원본1초당 조립 초).

    청소본 컷 + 원본 위치를 아는 증분 조각(src_vid 가 붙은 cb*·cbx*). 옛 증분 조각은 위치를 몰라 뺀다."""
    out = []
    nx = _next_starts(base)
    for i, c in enumerate(base.get("cuts") or []):
        if c.get("cleaned") is False:
            continue            # 고른 장면만 지운 정본(장면 골라 지우기) — 안 지운 컷은 지운 조각이 아니다
        if _speed_bad(c):
            continue            # 속도 불일치 — 좌표를 못 믿는다(그 구간은 증분 청소 대상이 된다)
        cs, ce, fin, k = _cut_geom(c, nx[i])     # ★다음 컷 시작에서 자른다 — 다음 조각으로 못 넘어간다
        out.append((CLEAN_VID, "%s-%d" % (CLEAN_VID, i), str(c.get("video_id")), cs, ce, fin, k))
    for vid, ex in (base.get("extras") or {}).items():
        if ex.get("src_vid") is None or not Path(ex.get("path", "")).exists():
            continue
        try:
            s0, sec = float(ex["src_start"]), float(ex["seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append((vid, vid, str(ex["src_vid"]), s0, s0 + sec, 0.0, 1.0))
    return out


def _kept_iv(base, vid):
    """고객이 안 지우기로 고른 컷(cleaned:false)의 원본 구간 [(시작, 끝)] — 이 영상(vid)만, 시작순."""
    return sorted((_f(c.get("src")), _f(c.get("src")) + (_f(c.get("sdur")) or _f(c.get("dur"))))
                  for c in base.get("cuts") or []
                  if c.get("cleaned") is False and str(c.get("video_id")) == str(vid))


def left_by_choice(base, material):
    """재료 구간 중 청소본에 없는 부분이 **전부 고객이 안 지우기로 고른 컷**(cleaned:false) 자리인가 — 장면 골라 지우기 정본 전용.

    ★왜(2026-09-28 job 52a1ef1723a8): 고객이 한 칸 안에서 컷 일부만 골라 지웠다(32컷 중 14컷 안 고름, 모든 칸에 고른 컷이
      하나 이상 → skip_beats 없음). 렌더 컷 재생은 칸 단위 skip 만 알아 안 고른 컷을 '못 덮은 구간'으로 쳐 10칸 중 7칸이
      uncovered → 렌더가 고객이 **안 지우기로 고른** 장면을 증분 청소(과금) 대상으로 안내했다.
    판단: 청소본에 없는 틈(uncleaned_gaps)이 안 고른 컷의 원본 구간(src ~ src+sdur) 합집합 안에 다 들어가면 True.
      편성을 바꿔 새로 읽게 된 원본(어느 컷에도 없던 구간)은 False — 종전대로 '바뀐 장면'(증분 청소·동의창)."""
    if not base.get("partial"):
        return False
    try:
        vid = str(material.get("video_id"))
    except AttributeError:
        return False
    gaps = uncleaned_gaps(base, material)
    if not gaps:
        return False
    kept = _kept_iv(base, vid)
    for gs, ge in gaps:
        pos = gs
        for a, b in kept:
            if a <= pos + SPAN_TOL and b > pos:
                pos = max(pos, b)
        if ge - pos > SPAN_TOL:
            return False
    return True


TAIL_MAX = 0.30         # 컷 **끝**이 이만큼 이하로 안 지워졌으면 재청소(과금) 대신 조금 느리게 읽어 메운다
TAIL_FRAC = 0.15        # …단 그 컷 길이의 이 비율 이하일 때만(느려지는 게 눈에 띄지 않게)


def span_map(base, material, allow_tail=0.0):
    """재료 구간 하나를 지워진 조각으로 **빈틈없이 이어** 덮는다(원본 시간순·겹침 없이). 못 덮으면 None.
    반환 [{"video_id","seg_id","start","end","_src": 원본 길이}, ...].

    ★piece_map과 다른 점: piece_map은 겹치는 컷을 **전부** 돌려준다. 두 칸이 같은 원본을 쓰면 청소본에
      그 원본이 두 번 있어 조각이 두 번 재생되고, 일부만 덮여도 "있다"고 본다. 컷 하나를 그대로
      옮겨야 하는 자리(렌더 컷 재생·손으로 정한 컷)는 이걸 쓴다."""
    try:
        vid = str(material.get("video_id")); s = float(material.get("start")); e = float(material.get("end"))
    except (TypeError, ValueError):
        return None
    regs = [r for r in _regions(base) if r[2] == vid]
    out, pos = [], s
    # ★이음 허용치는 컷 길이의 절반까지만(2026-09-28 cecc7b884bb0 7번 칸): 0.1초짜리 컷은 SPAN_TOL(0.12)보다 짧아
    #   루프가 한 번도 안 돌아 None — 틈 계산(uncleaned_gaps)은 "빈 곳 없음"인데 재생은 "못 덮음"이라 그 칸이 증분 청소로 갔다.
    #   SPAN_TOL보다 긴 컷은 종전 그대로(허용치 SPAN_TOL), 그보다 짧은 컷만 절반 허용치로 한 조각을 찾는다.
    tol = SPAN_TOL if e - s > SPAN_TOL else max(e - s, 0.0) / 2
    while e - pos > SPAN_TOL or (not out and e - pos > 1e-3):
        best = None
        for r in regs:
            if r[3] <= pos + tol and r[4] > pos + tol and (best is None or r[4] > best[4]):
                best = r
        if best is None:
            if out and e - pos <= allow_tail:
                break                      # 끝 자투리만 모자람 — 호출부가 느리게 읽어 메운다
            return None
        rv, sid, _v, cs, ce, fin, k = best
        lo, hi = max(pos, cs), min(e, ce)
        out.append({"video_id": rv, "seg_id": sid, "start": round(fin + (lo - cs) * k, 3),
                    "end": round(fin + (hi - cs) * k, 3), "_src": round(hi - lo, 3)})
        pos = hi
    return out or None


def _pieces_for_beat(base, beat):
    """비트의 재료 전부가 청소본 조각으로 대체되면 그 목록, 하나라도 없으면 None."""
    from shopping_shorts.mix_pipeline import _beat_materials
    segs = []
    for m in _beat_materials(beat or {}):
        got = piece_map(base, m, cleaned_only=bool(base.get("partial")))
        if not got:
            return None
        segs.extend(got)
    return segs or None


def _extras_all(base, beat_idx, key, n):
    """이 비트·재료 키의 바뀐 장면 조각 cb{bi}_{k} **전부**(k 순). n개가 다 살아 있어야 준다.

    ★예전엔 첫 조각 하나만 찾아(_extra_for) 재료가 둘 이상인 칸은 증분 청소한 나머지 조각을 버렸다 —
      돈 내고 지운 장면이 완성본에서 빠지고 첫 조각이 늘어나 채웠다(2026-09-26 점검에서 발견)."""
    got = {}
    for vid, ex in (base.get("extras") or {}).items():
        if vid.startswith("cbx") or not vid.startswith("cb"):
            continue
        if int(ex.get("beat_idx", -1)) != int(beat_idx) or ex.get("key") != _key_list(key):
            continue
        if not Path(ex.get("path", "")).exists():
            continue
        try:
            got[int(vid.rsplit("_", 1)[1])] = (vid, ex)
        except (IndexError, ValueError):
            continue
    if n and all(k in got for k in range(n)):
        return [got[k] for k in range(n)]
    return None


def _manual_pieces(base, beat):
    """손으로 정한 컷이 있는 칸 → 컷마다 청소본 조각 목록 [[{…, "_src": 원본 길이}], …]. 하나라도 못 덮으면 None.

    ★컷을 그대로 옮긴다 — 청소본을 만들던 때의 컷 배치(_cuts_of)를 쓰면 그 뒤 고친 컷이 사라진다
      (2026-09-26 강규봉님 job 7bbb1329aff0: 1번 칸 한 컷 5.17초가 옛 두 컷 2.44+2.72초로 나감).
    ★coverage 와 remap_plan 이 **둘 다 이 함수 하나**로 정한다(0순위-B)."""
    from shopping_shorts.mix_pipeline import _beat_materials
    mats = _beat_materials(beat)
    exs = _extras_all(base, int(beat["beat_idx"]), beat_material_key(beat), len(mats))
    if exs:
        return [[{"video_id": vid, "seg_id": vid, "start": 0.0, "end": float(ex["seconds"]),
                  "_src": float(ex["seconds"])}] for vid, ex in exs]
    out = []
    for m in mats:
        got = span_map(base, m)
        if not got:
            return None
        out.append(got)
    return out


def _is_manual(beat):
    from shopping_shorts.video_assemble import manual_cut_spans
    return bool(manual_cut_spans(beat))


def coverage(plan, base):
    """{beat_idx: "covered" | "changed" | "new" | "skip"} — 재료(장면)만 본다. 자막·확대·길이는 무관.

    "skip" = 고른 장면만 지운 정본에서 **고객이 안 고른 비트**(또는 청소 뒤 새로 생긴 비트).
      원본 재료 그대로 쓰고 증분 청소도 하지 않는다 — 안 고른 장면에 돈이 나가지 않게.
    """
    from shopping_shorts.mix_pipeline import _beat_materials
    out = {}
    partial = bool(base.get("partial"))
    skip = {int(x) for x in base.get("skip_beats") or []}
    for b in (plan or {}).get("beats") or []:
        bi = int(b["beat_idx"])
        key = beat_material_key(b)
        saved = base.get("beat_keys", {}).get(str(bi))
        if partial and (bi in skip or saved is None):
            out[bi] = "skip"
            continue
        if _is_manual(b):
            out[bi] = "covered" if _manual_pieces(base, b) else ("new" if saved is None else "changed")
            continue
        has_ex = bool(_extras_all(base, bi, key, len(_beat_materials(b))))
        if saved is None:
            out[bi] = "covered" if (has_ex or _pieces_for_beat(base, b)) else "new"
        elif saved == _key_list(key) and _cuts_of(base, bi) and not any(_speed_bad(c) for c in _cuts_of(base, bi)):
            out[bi] = "covered"
        elif has_ex:
            out[bi] = "covered"
        elif _pieces_for_beat(base, b):
            out[bi] = "covered"            # 조각이 청소본 어디엔가 있다(옮기기·빼기·잘라쓰기)
        else:
            out[bi] = "changed"
    return out


_REPLAY_DROP = ("slow", "sync_speed", "stretch_fill", "fixed_lens", "clip_anchor", "cut_rhythm")


def uncleaned_gaps(base, material):
    """재료 구간 중 **안 지워진 부분만** [(시작, 끝), …] — 증분 청소는 이것만 보낸다(초당 과금).
    ★컷 하나가 일부만 비었다고 컷 전체를 다시 지우면 이미 지운 부분에 또 돈이 나간다(2026-09-26 사장님)."""
    try:
        vid = str(material.get("video_id")); s = float(material.get("start")); e = float(material.get("end"))
    except (TypeError, ValueError):
        return []
    iv = sorted((max(s, r[3]), min(e, r[4])) for r in _regions(base)
                if r[2] == vid and min(e, r[4]) > max(s, r[3]))
    gaps, cur = [], s
    for a, b in iv:
        if a - cur > SPAN_TOL:
            gaps.append((cur, a))
        cur = max(cur, b)
    if e - cur > SPAN_TOL:
        gaps.append((cur, e))
    return gaps


def _span_with_kept(base, material, seg_id=None):
    """left_by_choice 가 참인 재료 구간 → 지운 부분은 청소본 조각(span_map), 안 고른 컷 자리는 **원본 조각**으로 이어 붙인 목록.
    원본 조각 = {"video_id": 원본 vid, "seg_id", "start", "end", "_src"}(원본 좌표, 1배속). 못 이으면 None."""
    vid = str(material.get("video_id")); s = float(material.get("start")); e = float(material.get("end"))
    # ★컷 대부분이 안 고른 컷 자리면 **통째로 원본** — 청소본(조립본)에서도 그 자리는 원본 프레임이었다. 옆 컷의 지운 끝이
    #   살짝 걸쳤다고(52a1 칸4 0.19초) 쪼개면 자막이 잠깐 사라졌다 나타나고 컷 수가 편집 화면과 달라진다.
    kept_len = sum(max(0.0, min(e, b) - max(s, a)) for a, b in _kept_iv(base, vid))
    if e - s > 1e-3 and kept_len >= 0.5 * (e - s):
        return [{"video_id": vid, "seg_id": seg_id or "", "start": round(s, 4), "end": round(e, 4),
                 "_src": round(e - s, 4)}]
    segs, pos = [], s                      # [("clean"|"orig", 시작, 끝)] 원본 좌표
    for gs, ge in uncleaned_gaps(base, material) + [(e, e)]:
        if gs - pos > 1e-3:
            segs.append(["clean", pos, gs])
        if ge - gs > 1e-3:
            segs.append(["orig", gs, ge])
        pos = max(pos, ge)
    # SPAN_TOL 이하 지운 자투리(프레임 반올림으로 옆 컷 끝이 걸친 것 — 52a1 칸2 0.007초)는 옆 원본 조각에 붙인다:
    #   따로 두면 0.03초짜리 컷이 끼어 컷 수가 편집 화면과 달라진다
    merged = []
    for k, a, b in segs:
        if k == "clean" and b - a <= SPAN_TOL and len(segs) > 1:
            k = "orig"
        if merged and merged[-1][0] == k == "orig":
            merged[-1][2] = b
        else:
            merged.append([k, a, b])
    out = []
    for k, a, b in merged:
        if k == "clean":
            sub = span_map(base, {"video_id": vid, "start": a, "end": b})
            if not sub:
                return None
            out.extend(sub)
        else:
            out.append({"video_id": vid, "seg_id": seg_id or "", "start": round(a, 4), "end": round(b, 4),
                        "_src": round(b - a, 4)})
    return out or None


def replay_clips(base, clips):
    """렌더 컷 계획(원본 좌표, plan_beat_clips_for 결과) → 지워진 조각 좌표의 수동 컷.

    반환 (cuts, miss). cuts 원소 {video_id, seg_id, start, dur(화면 길이), sdur(읽는 길이)[, pspeed]}.
    miss = 지워진 조각으로 못 덮은 원본 구간들(증분 청소 대상) — 하나라도 있으면 그 칸은 못 옮긴 것이다."""
    cuts, miss = [], []
    for c in clips or []:
        try:
            s = float(c["start"]); out = float(c["out_dur"]); sd = float(c.get("src_dur") or out)
        except (KeyError, TypeError, ValueError):
            continue
        if sd <= 1e-3 or out <= 1e-3:
            continue
        m = {"video_id": c.get("video_id"), "start": s, "end": s + sd}
        got = span_map(base, m)
        short = False
        if not got and left_by_choice(base, m):
            # 고객이 안 지우기로 고른 컷 자리 — 그 부분은 원본 그대로 튼다(과금 0), 지운 부분은 청소본 조각.
            #   렌더는 원본 소스를 같이 받는다(render_inputs_for _left — 칸 재료에 원본 vid 가 남으므로)
            got = _span_with_kept(base, m, c.get("seg_id"))
        if not got:
            # 끝 자투리(≤0.3초·≤15%)만 안 지워졌으면 재청소 대신 지운 데까지만 읽고 살짝 느리게 채운다
            got = span_map(base, m, allow_tail=min(TAIL_MAX, TAIL_FRAC * sd))
            short = bool(got)
        if not got:
            for gs, ge in uncleaned_gaps(base, m) or [(s, s + sd)]:
                miss.append({"video_id": c.get("video_id"), "start": round(gs, 3), "end": round(ge, 3)})
            continue
        tot = sum(p["_src"] for p in got) or 1.0
        for p in got:
            cut = {"video_id": p["video_id"], "seg_id": p["seg_id"], "start": p["start"],
                   "dur": round(out * p["_src"] / tot, 4), "sdur": round(p["end"] - p["start"], 4)}
            if c.get("playback_speed") or short:
                cut["pspeed"] = True      # 읽는 길이 전부를 화면 길이에 담는다(정지 대신 부드럽게 느리게)
            cuts.append(cut)
    return cuts, miss


def remap_plan(plan, base, *, tts_durs=None, src_durs=None):
    """편성표 → 청소본을 소스로 쓰는 **파생 사본**.

    ★src_durs(원본 소스 길이)를 주면 **렌더 컷 재생**(2026-09-26): 칸마다 원본으로 그렸을 컷 계획
      (video_assemble.plan_beat_clips_for — 편집 화면·렌더·캡컷이 쓰는 그 함수)을 그대로 지워진 조각
      좌표로 옮겨 수동 컷으로 박는다. 컷 리듬·구절 맞춤·손 컷·배속이 이미 반영된 결과라 청소본에서
      **다시 계산하지 않는다**. 다시 계산하면 조각이 청소본 컷으로 쪼개진 채 리듬을 새로 타서
      같은 장면이 반복되고 딴 장면이 끼었다(실측 7일 349 job 중 293 job·780칸 불일치).
      못 옮긴 칸은 uncovered, 못 덮은 원본 구간은 plan2["_clean_need"][str(bi)] 로 준다(증분 청소가 그 구간만 지운다).
      호출부(render_inputs_for·재청소 안내)는 전부 이 모드로 부른다.

    covered 비트: scene_override = 청소본 컷 구간들("clean", fin, fin+dur) 또는 extras 조각.
      손으로 정한 컷이 있는 칸은 manual_cuts 도 청소본 좌표로 옮긴다(렌더가 그 컷만 그린다).
    uncovered 비트: 재료를 그대로 둔다(호출부가 증분 청소 뒤 다시 remap 한다).
    extend: covered인데 새 길이가 청소본 컷 합보다 EXTEND_MIN 넘게 길면, 원본에서 더 잘라
            지울 구간을 요청한다({beat_idx, video_id, start, end, need}). 그 이하는
            plan_beat_clips_for 의 느리게(_MAX_SLOWMO)+정지가 채운다.
    """
    if src_durs is not None:
        return _remap_replay(plan, base, tts_durs or {}, src_durs)
    return _remap_legacy(plan, base, tts_durs)


def _remap_replay(plan, base, tts_durs, src_durs):
    from shopping_shorts import video_assemble as _va
    from shopping_shorts.mix_pipeline import _beat_materials
    plan2 = copy.deepcopy(plan or {})
    plan2["clean_base"] = True
    orig = {int(b["beat_idx"]): b for b in (plan or {}).get("beats") or []}
    live = [bi for bi, d in (tts_durs or {}).items() if (d or 0) > 0]
    runout_idx = max(live) if live else None
    uncovered, need = [], {}
    _leg = {}

    def _legacy_beat(bi):
        """종전(재료 단위) 판정 결과 한 칸 — 옛 증분 조각 재사용·원본 길이를 못 잰 칸의 안전판."""
        if not _leg:
            p2, unc2, _ = _remap_legacy(plan, base, tts_durs)
            _leg.update({int(x["beat_idx"]): x for x in p2["beats"]})
            _leg["_unc"] = set(unc2)
        return _leg[bi], bi in _leg["_unc"]

    partial = bool(base.get("partial"))
    skip = {int(x) for x in base.get("skip_beats") or []}
    for b in plan2.get("beats") or []:
        bi = int(b["beat_idx"])
        td = float((tts_durs or {}).get(bi) or 0.0)
        if td <= 0:
            continue                      # 렌더도 음성 없는 칸은 건너뛴다
        if partial and (bi in skip or str(bi) not in (base.get("beat_keys") or {})):
            continue                      # 고객이 안 고른 칸(장면 골라 지우기) — 원본 그대로, 청소 안 함(과금 0)
        runout = _va._LAST_RUNOUT if bi == runout_idx else 0.0
        try:
            clips = _va.plan_beat_clips_for(orig[bi], td, src_durs, runout=runout)
        except Exception:      # noqa: BLE001 — 계획 실패는 종전 판정으로
            clips = []
        if not clips:
            # 원본 길이를 못 재 계획을 못 세웠다(소스 파일 없음·깨짐). 원본을 가리킨 채 두면 청소본만 넘어가
            # 렌더가 소스를 못 찾는다 → 종전 판정으로 떨어진다.
            lb, lunc = _legacy_beat(bi)
            b.clear(); b.update(lb)
            if lunc:
                uncovered.append(bi)
            continue
        cuts, miss = replay_clips(base, clips)
        if miss:
            # 이미 돈 내고 지운 옛 증분 조각(원본 위치 기록 없음)이 이 칸 재료를 통째로 덮으면 그걸 쓴다 — 재과금 금지
            if _extras_all(base, bi, beat_material_key(orig[bi]), len(_beat_materials(orig[bi]))):
                lb, _lunc = _legacy_beat(bi)
                b.clear(); b.update(lb)
                continue
            uncovered.append(bi)
            need[str(bi)] = miss
            continue
        for k in _REPLAY_DROP:
            b.pop(k, None)                # 이미 계획에 녹아 있다 — 남기면 두 번 먹는다
        b["phrase_sync"] = False
        b["clean_replay"] = True
        b["manual_cuts"] = cuts
        b["scene_override"] = [{"video_id": c["video_id"], "seg_id": c["seg_id"], "start": c["start"],
                                "end": round(c["start"] + c["sdur"], 4)} for c in cuts]
    plan2["_clean_need"] = need
    return plan2, uncovered, []


def _remap_legacy(plan, base, tts_durs=None):
    """종전 재배치(재료 단위) — src_durs 없이 부르는 곳(옛 테스트·도구)용."""
    from shopping_shorts.mix_pipeline import _beat_materials
    plan2 = copy.deepcopy(plan or {})
    plan2["clean_base"] = True
    cov = coverage(plan, base)
    uncovered, extend = [], []
    all_cuts = base.get("cuts") or []
    for b in plan2.get("beats") or []:
        bi = int(b["beat_idx"])
        if cov.get(bi) == "skip":
            continue            # 안 고른 장면 — 원본 재료 그대로(호출부가 원본 소스도 함께 넘긴다)
        if cov.get(bi) != "covered":
            uncovered.append(bi)
            continue
        key = beat_material_key(b)
        if _is_manual(b):
            per = _manual_pieces(base, b) or []
            flat = [p for grp in per for p in grp]
            b["manual_cuts"] = [{"video_id": p["video_id"], "seg_id": p["seg_id"], "start": p["start"],
                                 "dur": p["_src"], "sdur": round(p["end"] - p["start"], 3)} for p in flat]
            b["scene_override"] = [{k: v for k, v in p.items() if k != "_src"} for p in flat]
            continue
        cuts = _cuts_of(base, bi)
        exs = _extras_all(base, bi, key, len(_beat_materials(b)))
        if (base.get("beat_keys", {}).get(str(bi)) == _key_list(key) and cuts
                and not any(_speed_bad(c) for c in cuts)):
            b["scene_override"] = [
                {"video_id": CLEAN_VID, "seg_id": "%s-%d" % (CLEAN_VID, all_cuts.index(c)),
                 "start": _clean_span(base, c)[0], "end": _clean_span(base, c)[1]} for c in cuts]
            have = sum(float(c["dur"]) for c in cuts)
            need = float((tts_durs or {}).get(bi) or b.get("target_seconds") or 0.0)
            # 이미 늘림 조각(cbx{bi})을 지워 두었으면 청소 컷 뒤에 **붙여 쓴다** — 지워놓고 안 쓰면 돈만 나간다
            xvid, xex = _extra_for(base, bi, key, prefix="cbx")
            if xvid:
                b["scene_override"].append({"video_id": xvid, "seg_id": xvid, "start": 0.0, "end": float(xex["seconds"])})
                have += float(xex["seconds"])
            if have > 0 and need > have * (1.0 + EXTEND_MIN):
                last = cuts[-1]
                # 원본 끝 = src + sdur(원본에서 읽은 길이). dur(완성본 길이)로 재면 느리게 구운 컷일 때 뒤로 밀린다
                s = _geom_in(base, last)[1] + (float(xex["seconds"]) if xvid else 0.0)
                extend.append({"beat_idx": bi, "video_id": last["video_id"], "start": round(s, 3),
                               "end": round(s + (need - have) + EXTEND_PAD, 3), "need": round(need - have, 3)})
        elif exs:
            b["scene_override"] = [{"video_id": vid, "seg_id": vid, "start": 0.0, "end": float(ex["seconds"])}
                                   for vid, ex in exs]
        else:
            b["scene_override"] = _pieces_for_beat(base, b) or []   # coverage가 covered로 판정한 조각들
    return plan2, uncovered, extend


def source_paths(base):
    """조립에 넘길 소스 맵: 청소본 + 증분 조각들."""
    out = {CLEAN_VID: base["path"]}
    for vid, ex in (base.get("extras") or {}).items():
        out[vid] = ex["path"]
    return out


def time_in_clean(base, beat_idx, pos=0.5):
    """그 비트가 청소본 어디에 있나(초). pos=0.0 첫 컷 시작 … 1.0 마지막 컷 끝. 없으면 None."""
    cuts = _cuts_of(base, beat_idx)
    if not cuts:
        return None
    t0 = _clean_span(base, cuts[0])[0]
    t1 = _clean_span(base, cuts[-1])[1]
    return t0 + (t1 - t0) * max(0.0, min(1.0, float(pos)))
