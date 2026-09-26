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


def _write(work, base):
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
CAL_WIN = 0.4                       # 옛 청소본 밀림 탐색 범위(초, 앞뒤)


def _gray_frames(path, t0, dur, w=48, h=85):
    import subprocess
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, t0), "-i", str(path), "-t", "%.3f" % dur,
                        "-vf", "scale=%d:%d,format=gray,fps=30" % (w, h), "-f", "rawvideo", "-"],
                       capture_output=True, timeout=60)
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    n = buf.size // (w * h)
    return buf[: n * w * h].reshape(n, h, w).astype(np.int16) if n else None


def calibrate(work, base, src_paths):
    """옛 청소본(frame_exact 없음)의 컷마다 **실제 밀림(off)**을 한 번 재서 정본에 남긴다(2026-09-27).

    왜: 청소본은 조립본(mix_raw)을 지운 것인데, 옛 조립본은 칸마다 프레임 올림이 쌓여 뒤 칸일수록 장면이
      컷 지도(fin, 음성 길이 누적)보다 늦게 들어 있었다(실측 7bbb 3번 칸 +0.132초). 재생이 fin 으로 읽으면
      화면보다 그만큼 앞 장면이 나온다. 청소를 다시 하지 않고(돈 0) 원본 프레임과 청소본 프레임을 맞춰 잰다.
    ★실패·확신 없음은 0(종전과 같음). 한 번 재면 calibrated 로 표시해 다시 안 잰다."""
    if not base or base.get("frame_exact") or base.get("calibrated"):
        return base
    try:
        import numpy as np
        clean = base["path"]
        for c in base.get("cuts") or []:
            src = (src_paths or {}).get(c.get("video_id"))
            if not src:
                continue
            dur = float(c.get("dur") or 0)
            if dur < 0.2:
                continue
            take = min(0.4, dur * 0.4)
            ref = _gray_frames(src, float(c["src"]) + take, 0.05)
            seq_t0 = float(c["fin"]) + take - CAL_WIN
            seq = _gray_frames(clean, seq_t0, 2 * CAL_WIN + 0.05)
            if ref is None or seq is None or not len(ref):
                continue
            d = np.abs(seq - ref[0]).mean(axis=(1, 2))
            i = int(d.argmin())
            # 확신: 가장 닮은 프레임이 충분히 닮고(< 25), 나머지 평균보다 뚜렷이 낮을 때만
            if d[i] < 25 and d[i] < 0.7 * float(np.median(d)):
                off = max(-CAL_WIN, seq_t0 + max(0, i) / 30.0 - (float(c["fin"]) + take))
                if max(0.0, seq_t0) != seq_t0:          # 파일 앞에서 잘린 경우 시작 보정
                    off = i / 30.0 - (float(c["fin"]) + take)
                c["off"] = round(off, 3) if abs(off) >= 0.02 else 0.0
        base["calibrated"] = True
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
        base = json.loads(p.read_text(encoding="utf-8"))
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
    for i, c in enumerate(cuts):
        if str(c.get("video_id")) != vid:
            continue
        if cleaned_only and c.get("cleaned") is False:
            continue            # 고른 장면만 지운 정본 — 안 지운 컷을 '지운 조각'으로 빌려 쓰지 않는다
        cs, ce, fin, k = _cut_geom(c)
        lo, hi = max(s, cs), min(e, ce)
        if hi - lo >= MIN_PIECE:
            out.append((lo, {"video_id": CLEAN_VID, "seg_id": "%s-%d" % (CLEAN_VID, i),
                             "start": round(fin + (lo - cs) * k, 3), "end": round(fin + (hi - cs) * k, 3)}))
    out.sort(key=lambda x: x[0])
    return [x[1] for x in out]


def _cut_geom(c):
    """청소본 컷 하나 → (원본 시작, 원본 끝, 청소본 시작, 원본1초당 청소본 초).

    ★원본 끝은 sdur(원본에서 실제로 읽은 길이)로 잰다. dur는 완성본 길이라 느리게·정지로 늘어난 컷이면
      원본의 **안 지운 구간**까지 덮었다고 오판한다(2026-09-26). sdur 없는 옛 정본은 dur 그대로(종전)."""
    cs = float(c["src"]); dur = float(c["dur"])
    try:
        sd = float(c.get("sdur") or dur)
    except (TypeError, ValueError):
        sd = dur
    sd = sd if sd > 1e-6 else dur
    # off = 옛 청소본의 실제 밀림(calibrate가 잰다) — 파일 안 장면이 컷 지도(fin)보다 늦게 들어 있다
    try:
        off = float(c.get("off") or 0.0)
    except (TypeError, ValueError):
        off = 0.0
    return cs, cs + sd, float(c["fin"]) + off, (dur / sd if sd > 1e-6 else 1.0)


SPAN_TOL = 0.12         # 이만큼 이하 틈은 이어 붙인다(프레임 반올림) — 그보다 크면 못 덮은 것


def _regions(base):
    """지워진 원본 구간 전부: (조립 vid, seg_id, 원본 vid, 원본 시작, 원본 끝, 조립 시작, 원본1초당 조립 초).

    청소본 컷 + 원본 위치를 아는 증분 조각(src_vid 가 붙은 cb*·cbx*). 옛 증분 조각은 위치를 몰라 뺀다."""
    out = []
    for i, c in enumerate(base.get("cuts") or []):
        if c.get("cleaned") is False:
            continue            # 고른 장면만 지운 정본(장면 골라 지우기) — 안 지운 컷은 지운 조각이 아니다
        cs, ce, fin, k = _cut_geom(c)
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
    while e - pos > SPAN_TOL:
        best = None
        for r in regs:
            if r[3] <= pos + SPAN_TOL and r[4] > pos + SPAN_TOL and (best is None or r[4] > best[4]):
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
        elif saved == _key_list(key) and _cuts_of(base, bi):
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
        if base.get("beat_keys", {}).get(str(bi)) == _key_list(key) and cuts:
            b["scene_override"] = [
                {"video_id": CLEAN_VID, "seg_id": "%s-%d" % (CLEAN_VID, all_cuts.index(c)),
                 "start": _cut_geom(c)[2], "end": _cut_geom(c)[2] + float(c["dur"])} for c in cuts]
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
                s = _cut_geom(last)[1] + (float(xex["seconds"]) if xvid else 0.0)
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
    t0 = _cut_geom(cuts[0])[2]
    t1 = _cut_geom(cuts[-1])[2] + float(cuts[-1]["dur"])
    return t0 + (t1 - t0) * max(0.0, min(1.0, float(pos)))
