# -*- coding: utf-8 -*-
"""청소본 정본 LAB — 실제 job 사본으로 "자막제거 1회 · 그림 일치 · 캡컷 경계"를 잰다 (2026-09-22).

VMake는 절대 안 부른다: _vmake_clean 을 'drawbox로 아래 1/4을 검게 칠한 사본'으로 바꾼다.
그러면 결과 영상에서 "지워진 곳"이 눈과 phash로 보인다.

실행(트랙 폴더):
  py shopping_shorts/scripts/clean_base_lab.py --job <job_id> --db shopping_shorts/data/lab.db \
     --edit lines --edit zoom --edit swap
  --edit lines : 첫 비트 자막을 3줄로   --edit zoom : 둘째 비트 확대 1.2   --edit swap : 셋째 비트를 다른 소스로
  --edit voice : 첫 비트 음성을 1.5배 길게(늘림 정책: 느리게/정지, 30% 넘으면 증분)
  --pick 0,3,4 : 장면 골라 지우기(2026-09-26) — 그 컷 번호만 지운다. 보고서가 컷마다
                 "골랐나 ↔ 띠가 있나"를 대조하고, 청소본·완성본 프레임 수가 조립본과 같은지 잰다.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")

from shopping_shorts import mix_pipeline as mp                      # noqa: E402
from shopping_shorts import clean_base as cb                        # noqa: E402
from shopping_shorts.store import Store                             # noqa: E402

CALLS = []


def _fake_vmake(src, keys, out, tier=None):
    CALLS.append((Path(src).name, tier))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-vf", "drawbox=x=0:y=ih*3/4:w=iw:h=ih/4:color=black@1:t=fill",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", str(out)], check=True)
    return str(out)


def _phash(path, t):
    """t초 프레임의 8x8 평균 해시(외부 라이브러리 없이)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                          "-vf", "scale=8:8,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    px = list(raw[:64]); avg = sum(px) / max(1, len(px))
    return sum(1 << i for i, v in enumerate(px) if v > avg)


def _ham(a, b):
    return bin(a ^ b).count("1")


def _bottom_black_ratio(path, t):
    """t초 프레임 아래 1/4이 검은 비율(0~1) — '지워진 띠'가 있는가."""
    # ★t=None = 정지 그림(jpg). 그림에 -ss 0을 주면 프레임이 **0장** 나와 '띠 없음'으로 읽힌다(2026-09-26 실측).
    seek = [] if t is None else ["-ss", f"{t:.3f}"]
    raw = subprocess.run(["ffmpeg", "-v", "error"] + seek + ["-i", str(path), "-frames:v", "1",
                          "-vf", "crop=iw:ih/4:0:ih*3/4,scale=16:4,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    if not raw:
        raise RuntimeError("프레임을 못 뽑았다(판정 불가): %s" % path)
    px = list(raw[:64])
    return sum(1 for v in px if v < 24) / max(1, len(px))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True); ap.add_argument("--db", required=True)
    ap.add_argument("--edit", action="append", default=[])
    ap.add_argument("--pick", default="", help="지울 컷 번호(쉼표). 비우면 전체")
    ap.add_argument("--work-root", default=str(ROOT / "shopping_shorts" / "data" / "mix_jobs"))
    ap.add_argument("--report-only", action="store_true", help="청소·렌더 없이 3)·4) 검사만(현재 파일 기준)")
    a = ap.parse_args()
    store = Store(a.db)
    store.set_setting("clean_base_enabled", "1")
    # ★clean_base_for·app 쪽 판정은 config.DB_PATH의 설정을 읽는다 — LAB DB를 가리키지 않으면
    #   렌더(정본 켬)와 꾸미기 프레임(정본 끔)이 서로 다른 길을 타서 가짜 불일치가 난다(2026-09-26 실측).
    from shopping_shorts import config as _cfg
    _cfg.DB_PATH = a.db
    work_root = Path(a.work_root)
    work = work_root / a.job
    assert work.exists(), f"job 폴더 없음: {work}"
    mp._vmake_clean = _fake_vmake
    mp._vmake_keys = lambda s, c=0: ["lab-key"]
    mp._charge_clean = lambda s, c, n: 0
    # 장면 골라 지우기 검사용 — 되붙이기 전 조립본을 남겨 partial_clean_frames_check.py가 프레임 대조한다
    _orig_partial = mp._clean_partial

    def _keep_raw(mix_raw, *x, **k):
        import shutil
        shutil.copyfile(mix_raw, work / "lab_mix_raw.mp4")
        return _orig_partial(mix_raw, *x, **k)
    mp._clean_partial = _keep_raw
    if a.report_only:
        job = store.get_mix_job(a.job)
        _report(store, a, work, work_root, job)
        return
    for f in list(work.glob("final_clean_*")) + [work / cb.BASE_FILE] + list(work.glob("cb*.mp4")):
        if f.exists():
            f.unlink()

    job = store.get_mix_job(a.job)
    assert job and job.get("edit_plan"), "편성표 없음"
    # ★서버 사본의 tts_path는 서버 절대경로다 — 로컬 tts/ 폴더로 바꿔야 skip_existing이 먹는다.
    #   안 바꾸면 로컬 TTS(무음 목)가 같은 이름으로 덮어써 컷이 0.4초짜리가 된다(실측 2026-09-22).
    _plan = job["edit_plan"]; _n = 0
    for _b in _plan.get("beats") or []:
        _tp = _b.get("tts_path")
        if _tp and not Path(_tp).exists():
            _loc = work / "tts" / Path(_tp).name
            if _loc.exists():
                _b["tts_path"] = str(_loc); _n += 1
            else:
                raise SystemExit(f"로컬에 TTS 없음: {_loc} — 서버 tts/ 폴더를 먼저 받아라")
    store.update_mix_job(a.job, edit_plan=_plan)
    print(f"   tts_path 로컬로 바꿈 {_n}개")
    store.update_mix_job(a.job, subtitle_removal=1, clean_status=None, clean_sources=None, clean_cuts=None)
    if a.pick:
        _cuts = mp.clean_pick_cuts(store.get_mix_job(a.job), work)
        _idx = [int(x) for x in a.pick.split(",") if x.strip()]
        _keys = [_cuts[i]["key"] for i in _idx]
        store.update_mix_job(a.job, clean_cuts=_keys)
        print("   고른 컷:", _idx, "/ 전체", len(_cuts), "→", _keys)

    print("== 1) 4단계 청소"); mp.run_clean_sources(a.job, a.db, str(work_root))
    base = cb.load_base(work); assert base, "정본이 안 생겼다(clean_status=%s err=%s)" % (
        store.get_mix_job(a.job).get("clean_status"), store.get_mix_job(a.job).get("clean_error"))
    print("   정본:", Path(base["path"]).name, "컷", len(base["cuts"]), "VMake 콜", len(CALLS),
          "| 보낸 파일:", [c[0] for c in CALLS], "| skip_beats:", base.get("skip_beats"))
    _mr = work / "mix_raw.mp4"
    if _mr.exists():
        print("   프레임 수: 조립본", mp._probe_fps_frames(_mr)[2], "청소본", mp._probe_fps_frames(base["path"])[2])
    for _f in CALLS:
        _pp = work / _f[0]
        if _pp.exists():
            print("   업체로 보낸 길이: %.2f초 (%s)" % (mp._probe_seconds(_pp) or 0, _f[0]))

    job = store.get_mix_job(a.job); plan = job["edit_plan"]; beats = plan["beats"]
    if "lines" in a.edit:
        words = (beats[0].get("narration") or "가 나 다").split(" ")
        k = max(1, len(words) // 3)
        beats[0]["caption_lines"] = [" ".join(words[:k]), " ".join(words[k:2 * k]), " ".join(words[2 * k:])]
        beats[0]["caption_lines"] = [x for x in beats[0]["caption_lines"] if x] or ["가", "나", "다"]
    if "zoom" in a.edit and len(beats) > 1:
        beats[1]["scene_zoom"] = 1.2
    if "swap" in a.edit and len(beats) > 2:
        srcs = mp._resolve_sources(job, work)
        cur = {m.get("video_id") for m in mp._beat_materials(beats[2])}
        other = [v for v in srcs if v not in cur]
        if other:
            beats[2]["scene_override"] = [{"video_id": other[0], "seg_id": other[0] + "-lab", "start": 0.0, "end": 2.0}]
    if "voice" in a.edit:
        # 실제 TTS 파일을 1.5배 길게(atempo 0.667) 만들어 가리킨다 — 렌더는 파일 길이를 보므로 target만 바꾸면 헛것
        # ★같은 파일명에 덮어쓴다 — skip_existing은 tts_path==해시파일명 일 때만 재합성을 건너뛴다.
        #   이름을 바꾸면 로컬 TTS(무음 목)가 다시 구워져 0.4초짜리가 된다(실측 2026-09-22).
        src = Path(beats[0]["tts_path"]); tmp = src.with_name(src.stem + "_tmp15.mp3")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter:a", "atempo=0.6667", str(tmp)], check=True)
        tmp.replace(src)
        for sc in (".align.json", ".cuts.json"):        # 옛 정렬 사이드카는 길이가 달라 못 쓴다
            sp = src.with_name(src.name + sc)
            if sp.exists():
                sp.unlink()
        beats[0]["target_seconds"] = round(float(beats[0].get("target_seconds") or 2.0) * 1.5, 3)
    store.update_mix_job(a.job, edit_plan=plan)

    n0 = len(CALLS)
    print("== 2) 최종렌더"); mp.run_render(a.job, a.db, str(work_root))
    job = store.get_mix_job(a.job)
    print("   상태:", job.get("status"), job.get("error") or "")
    print("   VMake 콜(렌더 중):", len(CALLS) - n0, "→ 기대: swap/voice 없으면 0, 있으면 1(증분)")
    _report(store, a, work, work_root, job)
    print("== 끝. VMake 총 콜:", len(CALLS), CALLS)


def _report(store, a, work, work_root, job):
    final = Path(job["video_path"])
    print("== 3) 그림 일치(컷별 phash, 청소본 vs 완성본) + 아래 검은 띠")
    plan2, paths, base = mp.render_inputs_for(store, job, a.job, work, [], 0, allow_clean=False)
    tts = {b["beat_idx"]: b["tts_path"] for b in plan2["beats"] if b.get("tts_path")}
    durs = {v: mp._probe_duration(p) for v, p in paths.items()}
    cuts = mp.final_clip_pairs(plan2, tts, durs)
    bad = 0; noband = 0; wrong = 0; _rend = []
    bcuts = (base or {}).get("cuts") or []
    for c in cuts:
        t_fin = c["fin"] + c["dur"] / 2
        band = _bottom_black_ratio(final, t_fin)
        if band < 0.9:
            noband += 1
        # 기대: 청소본 컷이면 정본의 cleaned 표식, 원본 재료(s*)면 안 지움, 증분 조각(cb*)이면 지움
        if c["video_id"] == "clean":
            _i = int(str(c.get("seg_id") or "clean--1").split("-")[-1]) if c.get("seg_id") else None
            _bc = None
            for _k, _x in enumerate(bcuts):
                cs = float(_x["fin"]); ce = cs + float(_x["dur"])
                if cs - 0.01 <= float(c["src"]) + float(c["dur"]) / 2 <= ce + 0.01:
                    _bc = _x
                    break
            want = bool(_bc.get("cleaned", True)) if _bc else True
        else:
            want = str(c["video_id"]).startswith("cb")
        ok = (band >= 0.9) == want
        _kk = sum(1 for _x in _rend if _x[0] == c["beat_idx"])
        _rend.append((c["beat_idx"], _kk, band))
        if not ok:
            wrong += 1
        print(f"     기대 {'지움' if want else '원본'} / 실제 띠 {band:.2f} {'OK' if ok else '★틀림'}")
        if c["video_id"] == "clean":
            d = _ham(_phash(paths["clean"], c["src"] + c["dur"] / 2), _phash(final, t_fin))
            flag = "" if d <= 12 else "  ★불일치"
            if d > 12:
                bad += 1
            print(f"   beat{c['beat_idx']} clean@{c['src']:.2f} vs final@{t_fin:.2f} 거리 {d} 띠 {band:.2f}{flag}")
        else:
            print(f"   beat{c['beat_idx']} [{c['video_id']}] final@{t_fin:.2f} 띠 {band:.2f}")
    print("   골랐나↔띠 대조 틀린 컷:", wrong)
    print("   컷", len(cuts), "불일치 컷:", bad, "(확대 비트는 거리가 커도 정상 — 눈으로 확인) | 띠 없는 컷:", noband)

    print("== 4) 캡컷 경계")
    from shopping_shorts import app as A
    A._MIX_WORK_DIR = work_root
    A.DB_PATH = a.db
    r = A.api_mix_capcut(a.job, base=str(work / "capcut_lab"))
    ok = getattr(r, "status_code", 200) == 200
    print("   응답:", type(r).__name__, "status", getattr(r, "status_code", 200))
    dc = sorted((work / "capcut").rglob("draft_content.json"), key=os.path.getmtime)
    if ok and dc:
        d = json.loads(dc[-1].read_text(encoding="utf-8"))
        segs = [s for t in d.get("tracks", []) if t.get("type") == "video" for s in t.get("segments", [])]
        # 캡컷은 **비트 단위**로 조각을 낸다(split_final_into_beat_clips) — 비트 경계와 대조한다.
        beats = {}
        for c in cuts:
            b = beats.setdefault(c["beat_idx"], [c["fin"], 0.0]); b[1] += c["dur"]
        blist = [beats[k] for k in sorted(beats)]
        # 세그먼트 수가 컷 수와 같으면(일반 경로) 컷 단위로, 비트 수와 같으면(완성본 자르기 경로) 비트 단위로 대조
        if len(segs) == len(cuts) and len(cuts) != len(blist):
            blist = [[c["fin"], c["dur"]] for c in cuts]
        print("   캡컷 비디오 세그먼트:", len(segs), "| 렌더 비트:", len(beats), "| 렌더 컷:", len(cuts), "| 대조 단위:", "컷" if len(blist) == len(cuts) else "비트")
        mism = 0
        for s, (bst, bdu) in zip(segs, blist):
            tr = s.get("target_timerange", {}); st = tr.get("start", 0) / 1e6; du = tr.get("duration", 0) / 1e6
            dv = abs(st - bst) + abs(du - bdu)
            if dv > 0.068:
                mism += 1
            print(f"     캡컷 {st:.3f}+{du:.3f}  렌더비트 {bst:.3f}+{bdu:.3f}  {'★어긋남' if dv > 0.068 else ''}")
        print("   경계 어긋남(>2프레임):", mism)
        # 캡컷 조각 파일이 청소본에서 나왔나 — 각 조각 가운데 프레임의 아래 띠
        mats = {m.get("id"): m.get("path") for m in (d.get("materials") or {}).get("videos") or []}
        nob = 0; shown = 0
        for s in segs:
            pth = mats.get(s.get("material_id"))
            # 초안 JSON의 경로는 캡컷 쪽 절대경로(base)다 — 실제 파일은 최신 draft 폴더에 같은 이름으로 있다
            f = Path(dc[-1]).parent / Path(pth or "").name
            if not pth or not f.exists():
                continue
            sr = s.get("source_timerange", {}); t = (sr.get("start", 0) + sr.get("duration", 0) / 2) / 1e6
            band = _bottom_black_ratio(f, t); shown += 1
            if band < 0.9:
                nob += 1
            print(f"     조각 {f.name} @{t:.2f} 띠 {band:.2f}")
        print("   캡컷 조각 중 띠 없는 것:", nob, "/", shown)
    print("== 5) 꾸미기 장면 프레임(_beatframe_file) ↔ 완성본 같은 컷의 띠")
    import shutil
    shutil.rmtree(work / "beatframes", ignore_errors=True)
    mism = 0
    for bi, k, rband in _rend:
        f = A._beatframe_file(store.get_mix_job(a.job), a.job, bi, cut=k)
        if not f:
            print(f"     beat{bi} 컷{k} 프레임 없음 ★"); mism += 1
            continue
        fb = _bottom_black_ratio(f, None)
        ok = (fb >= 0.5) == (rband >= 0.5)
        if not ok:
            mism += 1
        print(f"     beat{bi} 컷{k} 꾸미기 띠 {fb:.2f} / 완성본 띠 {rband:.2f} {'OK' if ok else '★다름'}  ({Path(f).name})")
    print("   꾸미기↔완성본 다른 컷:", mism)


if __name__ == "__main__":
    main()
