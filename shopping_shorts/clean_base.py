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


def save_base(work, *, sig, path, plan, cuts):
    """청소 직후 호출. 컷 지도(final_clip_pairs 결과)와 그때의 재료 키를 비트별로 남긴다."""
    keys = {int(b["beat_idx"]): _key_list(beat_material_key(b))
            for b in (plan or {}).get("beats") or [] if b.get("beat_idx") is not None}
    base = {"sig": sig, "path": str(path), "cuts": [dict(c) for c in cuts or []],
            "beat_keys": {str(k): v for k, v in keys.items()}, "extras": {}}
    _write(work, base)
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


def add_extra(work, base, *, vid, path, beat_idx, material_key, seconds):
    """증분 청소 조각을 정본에 붙인다. 같은 재료 키로 다시 오면 covered."""
    base.setdefault("extras", {})[vid] = {"path": str(path), "beat_idx": int(beat_idx),
                                          "key": _key_list(material_key), "seconds": float(seconds)}
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


def coverage(plan, base):
    """{beat_idx: "covered" | "changed" | "new"} — 재료(장면)만 본다. 자막·확대·길이는 무관."""
    out = {}
    for b in (plan or {}).get("beats") or []:
        bi = int(b["beat_idx"])
        key = beat_material_key(b)
        saved = base.get("beat_keys", {}).get(str(bi))
        if saved is None:
            out[bi] = "covered" if _extra_for(base, bi, key)[0] else "new"
        elif saved == _key_list(key) and _cuts_of(base, bi):
            out[bi] = "covered"
        elif _extra_for(base, bi, key)[0]:
            out[bi] = "covered"
        else:
            out[bi] = "changed"
    return out


def remap_plan(plan, base, *, tts_durs=None):
    """편성표 → 청소본을 소스로 쓰는 **파생 사본**.

    covered 비트: scene_override = 청소본 컷 구간들("clean", fin, fin+dur) 또는 extras 조각.
    uncovered 비트: 재료를 그대로 둔다(호출부가 증분 청소 뒤 다시 remap 한다).
    extend: covered인데 새 길이가 청소본 컷 합보다 EXTEND_MIN 넘게 길면, 원본에서 더 잘라
            지울 구간을 요청한다({beat_idx, video_id, start, end, need}). 그 이하는
            plan_beat_clips_for 의 느리게(_MAX_SLOWMO)+정지가 채운다.
    """
    plan2 = copy.deepcopy(plan or {})
    plan2["clean_base"] = True
    cov = coverage(plan, base)
    uncovered, extend = [], []
    all_cuts = base.get("cuts") or []
    for b in plan2.get("beats") or []:
        bi = int(b["beat_idx"])
        if cov.get(bi) != "covered":
            uncovered.append(bi)
            continue
        key = beat_material_key(b)
        cuts = _cuts_of(base, bi)
        if base.get("beat_keys", {}).get(str(bi)) == _key_list(key) and cuts:
            b["scene_override"] = [
                {"video_id": CLEAN_VID, "seg_id": "%s-%d" % (CLEAN_VID, all_cuts.index(c)),
                 "start": float(c["fin"]), "end": float(c["fin"]) + float(c["dur"])} for c in cuts]
            have = sum(float(c["dur"]) for c in cuts)
            need = float((tts_durs or {}).get(bi) or b.get("target_seconds") or 0.0)
            # 이미 늘림 조각(cbx{bi})을 지워 두었으면 청소 컷 뒤에 **붙여 쓴다** — 지워놓고 안 쓰면 돈만 나간다
            xvid, xex = _extra_for(base, bi, key, prefix="cbx")
            if xvid:
                b["scene_override"].append({"video_id": xvid, "seg_id": xvid, "start": 0.0, "end": float(xex["seconds"])})
                have += float(xex["seconds"])
            if have > 0 and need > have * (1.0 + EXTEND_MIN):
                last = cuts[-1]
                s = float(last["src"]) + float(last["dur"]) + (float(xex["seconds"]) if xvid else 0.0)
                extend.append({"beat_idx": bi, "video_id": last["video_id"], "start": round(s, 3),
                               "end": round(s + (need - have) + EXTEND_PAD, 3), "need": round(need - have, 3)})
        else:
            vid, ex = _extra_for(base, bi, key)
            b["scene_override"] = [{"video_id": vid, "seg_id": vid, "start": 0.0, "end": float(ex["seconds"])}]
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
    t0 = float(cuts[0]["fin"])
    t1 = float(cuts[-1]["fin"]) + float(cuts[-1]["dur"])
    return t0 + (t1 - t0) * max(0.0, min(1.0, float(pos)))
