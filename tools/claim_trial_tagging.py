# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] 태깅 지침서를 바꾸면 라이브 기본 2단계(backbone_assemble)의 장면 매칭이 달라지는가 (카드 051, 2026-10-01).

세 벌을 같은 재료(job의 extract)로 만든다:
  live : job에 실제로 저장된 대본·장면 짝(script_structure.beat_sources) — 사장님 화면의 그것
  old  : 옛 태그 그대로 → ba.assemble_clean  (하네스가 라이브를 재현하는지 보는 기준)
  new  : 지침서(--guide)로 5소스를 다시 태깅 → 같은 ba.assemble_clean

DB에 아무것도 안 쓴다. 산출물은 --out 폴더(result.json + 줄별 컷 프레임 jpg).
    set -a && . /etc/shopping-shorts.env && set +a && cd /home/ubuntu/lotto-stock-wiki
    python3 /tmp/claim_trial_tagging.py 29109deff2a9 --mode live --out /tmp/tagtrial_29109deff2a9_live
    python3 /tmp/claim_trial_tagging.py 29109deff2a9 --mode old  --out /tmp/tagtrial_29109deff2a9_old
    python3 /tmp/claim_trial_tagging.py 29109deff2a9 --mode new  --guide /tmp/guide_new.txt --out /tmp/tagtrial_29109deff2a9_new
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path[:] = [os.getcwd()] + [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]
MIX = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
EXTRA_KEYS = ("appeal_kind", "hook_type", "hook_why", "is_outro", "outro_why", "moments", "tempo", "speed_hint")   # 새 지침서가 더 내는 칸(정규화가 버리므로 따로 붙인다)


def _grab(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", video, "-frames:v", "1",
                    "-vf", "scale=-2:300", out], check=False)
    return out if os.path.exists(out) else None


def _video_of(jid, vid):
    v = sorted(glob.glob(os.path.join(MIX, jid, str(vid), "*.mp4")))
    return v[0] if v else None


def retag_source(jid, vid, ex, guide_text, work):
    """소스 하나를 새 지침서로 다시 태깅 — 구간(start/end/text)은 기존 것을 그대로 쓰고 프레임 띠만 새로 만든다.
    라이브 frame_script 본문과 같은 순서(frame_times→make_strip→_gemini_tag_frames)."""
    from shopping_shorts import frame_script as fs, script_extract
    video = _video_of(jid, vid)
    segs = [dict(s) for s in (ex.get("segments") or []) if isinstance(s, dict)]
    if not video or not segs:
        return ex, "영상 또는 구간 없음"
    fdir = os.path.join(work, "frames_%s" % vid)
    os.makedirs(fdir, exist_ok=True)
    groups = []
    for i, s in enumerate(segs):
        shots = []
        for j, t in enumerate(fs.frame_times(float(s["start"]), float(s["end"]),
                                             fs.frames_for_span(float(s["end"]) - float(s["start"])))):
            p = _grab(video, t, os.path.join(fdir, "seg%03d_%d.jpg" % (i, j)))
            if p:
                shots.append(p)
        strip = (fs.make_strip(shots, os.path.join(fdir, "seg%03d_strip.jpg" % i), label="#%d %.1fs" % (i + 1, float(s["start"])))
                 if len(shots) > 1 else None)
        groups.append([strip] if strip else ([shots[len(shots) // 2]] if shots else []))
    # ★지침서 교체 + 정규화가 버리는 새 칸을 살린다(이 프로세스 안에서만 — DB·라이브 무관)
    script_extract._SEG_FIELD_GUIDE = guide_text
    _orig_norm = fs.normalize_tags
    extras = {}

    def _norm_keep(tags, n):
        out = _orig_norm(tags, n)
        seq = 0
        for t in (tags or []):
            if not isinstance(t, dict):
                continue
            no = t.get("seg_no", t.get("image_no"))
            try:
                idx = int(no) - 1 if no is not None and not isinstance(no, bool) else seq
            except (TypeError, ValueError):
                idx = seq
            seq = idx + 1
            if 0 <= idx < n and out[idx]:
                # ★정규화된 dict 안에 바로 심는다 — _gemini_tag_frames 가 out[b0:b1]=got 으로 그대로 돌려주므로 살아남는다
                #   (첫 실행 10-01: extras 를 따로 모아 놓고 안 썼다 → 새 칸 0/88. 묶음별 지역 번호라 전역 짝도 못 맞췄다)
                #   패치본 패키지(normalize_tags 가 이미 새 키를 정규화)면 덮어쓰지 않는다 — 4차에서 speed_hint 가 문자열 '1.0'으로 덮였다.
                out[idx].update({k: t.get(k) for k in EXTRA_KEYS if t.get(k) not in (None, "") and k not in out[idx]})
        return out
    fs.normalize_tags = _norm_keep
    try:
        tags = fs._gemini_tag_frames(groups, ex.get("caption") or "", segs, brief=ex.get("source_brief") or {}) or []
    finally:
        fs.normalize_tags = _orig_norm
    if not tags:
        return ex, "태깅 실패(빈 응답)"
    # 묶음(배치)별 extras 인덱스는 묶음 안 번호라 전역으로 못 쓴다 → 태그 순서대로 다시 붙인다
    new_segs = []
    for i, (s, t) in enumerate(zip(segs, tags)):
        m = dict(s)
        for k in ("scene_desc", "shot_role", "is_key", "has_effect", "product_benefits", "label", "use_point", "action", "change"):
            if k in (t or {}):
                m[k] = (t or {}).get(k)
        for k in EXTRA_KEYS:
            if (t or {}).get(k) not in (None, ""):
                m[k] = t[k]
        new_segs.append(m)
    out = dict(ex, segments=new_segs)
    return out, "ok(%d구간, 묘사 빈 곳 %d)" % (len(new_segs), sum(1 for s in new_segs if not (s.get("scene_desc") or "").strip()))


def patch_source_block(ba):
    """새 칸(소구점 종류·훅·속도)을 작가 재료 줄에 싣는다 — 라이브 _source_block과 같은 형식 뒤에 덧붙임."""
    _orig = ba._source_block

    def _blk(s, is_backbone):
        txt = _orig(s, is_backbone)
        lines = txt.split("\n")
        segs = [x for x in (s.get("segments") or []) if isinstance(x, dict)]
        k = 0
        for li, ln in enumerate(lines):
            if ln.startswith("  [") and k < len(segs):
                x = segs[k]
                k += 1
                add = []
                if x.get("appeal_kind"):
                    add.append("소구:%s" % x["appeal_kind"])
                if x.get("hook_type"):
                    add.append("훅:%s(%s)" % (x["hook_type"], (x.get("hook_why") or "")[:12]))
                if x.get("is_outro") in (True, "true", "True"):
                    add.append("뒷컷")
                if x.get("tempo"):
                    add.append("속도:%s/%s배" % (x["tempo"], x.get("speed_hint") or "1.0"))
                if add:
                    lines[li] = ln + " | " + " ".join(add)
        return "\n".join(lines)
    ba._source_block = _blk


def run_assemble(job, jid, store, note):
    """app._backbone_drafts 의 자동 안(씨앗 그대로) 경로를 그대로 — 호출부 형태 그대로(메모리 규칙)."""
    from shopping_shorts import backbone_assemble as ba
    ext = job.get("extract") or {}
    srcs = ba.sources_from_extract(ext)
    bb = None
    bm = job.get("backbone_main")
    if bm is not None and isinstance(ext.get("s%d" % int(bm)), dict):
        want = ba.sources_from_extract({"s%d" % int(bm): ext["s%d" % int(bm)]})
        bb = next((s for s in srcs if want and s.get("video_id") == want[0].get("video_id")), None)
    if bb is None:
        def _ko(t):
            return sum(1 for c in t if "가" <= c <= "힣") / max(1, sum(1 for c in t if c.isalpha()))
        kor = [s for s in srcs if _ko(s.get("full_text") or "") > 0.7]
        bb = max(kor or srcs, key=lambda s: len((s.get("full_text") or "").strip()))
    typ = ""
    try:
        typ = ba.seed_type(srcs, job.get("backbone_main"), note=note)
    except Exception as e:      # noqa: BLE001
        note["seed_type_err"] = repr(e)[:100]
    note["seed_type"] = typ
    auto_c = ba.origin_spines(store, typ) if typ else []
    seed_src = ba.seed_source(srcs, job.get("backbone_main"))
    auto_c = [dict(sp, _use_seed_origin=True) for sp in auto_c]
    if not auto_c and seed_src:
        auto_c = [{"id": None, "name": "씨앗 그대로", "_use_seed_origin": True}]
    got = ba.assemble_clean(srcs, bb.get("video_id"), store, auto_c, target_seconds=int(job.get("target_seconds") or 25),
                            seed=jid, want=1, note=note, seed_src=seed_src)
    if not got:
        return None
    g = got[0]
    return {"given": g["given"], "beat_sources": g["beat_sources"], "spine": g.get("spine"),
            "report": (g.get("meta") or {}).get("report"), "groups": (g.get("meta") or {}).get("groups"),
            "note": (g.get("meta") or {}).get("note")}


def frames_for_lines(jid, given, beat_sources, seg_index, work):
    """줄마다 고른 컷의 프레임(컷당 2장)을 뽑아 시트 재료로."""
    rows = []
    lines = [l for l in (given or "").split("\n")]
    for i, bs in enumerate(beat_sources or []):
        text = lines[i] if i < len(lines) else ""
        segs = list((bs or {}).get("segs") or [])
        paths, descs = [], []
        for sid in segs[:4]:
            v = seg_index.get(sid) or {}
            vid = v.get("vid")
            video = _video_of(jid, vid) if vid else None
            st, en = v.get("start"), v.get("end")
            if video and st is not None and en is not None:
                for q in range(2):
                    p = _grab(video, float(st) + (float(en) - float(st)) * (q + 0.5) / 2,
                              os.path.join(work, "line%02d_%s_%d.jpg" % (i, sid.replace("/", "_"), q)))
                    if p:
                        paths.append(p)
            descs.append("%s(%.1fs) %s" % (sid, v.get("secs") or 0, (v.get("desc") or "")[:40]))
        rows.append({"i": i, "text": text, "role": (bs or {}).get("role"), "segs": segs, "frames": paths, "descs": descs})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--mode", choices=("live", "old", "new", "story"), required=True)
    ap.add_argument("--guide", default="")
    ap.add_argument("--extract", default="", help="new 모드: 전에 저장한 extract_new.json 을 다시 써서 재태깅을 건너뛴다")
    ap.add_argument("--out", required=True)
    ap.add_argument("--writer", choices=("backbone", "story_writer"), default="backbone", help="2단계 경로(사장님 계정은 story_writer 가 켜져 있다)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    from shopping_shorts import app as A, backbone_assemble as ba
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)
    job = A._enrich_job_extract(store.get_mix_job(a.job), store)
    if not (job or {}).get("extract"):
        sys.exit("extract 없음")
    note = {"mode": a.mode}
    if a.mode == "new":
        if a.extract:
            ext2 = json.load(open(a.extract, encoding="utf-8"))
            note["retag"] = "reused:%s" % a.extract
            print("재태깅 생략 — 저장본 재사용", a.extract, flush=True)
        else:
            # 지침서 정본은 script_extract._SEG_FIELD_GUIDE 한 곳(0순위-B). --guide 는 실험용 대체본일 때만.
            from shopping_shorts import script_extract as _se
            guide = open(a.guide, encoding="utf-8").read() if a.guide else _se._SEG_FIELD_GUIDE
            ext2 = {}
            for vid, ex in sorted((job.get("extract") or {}).items()):
                if not isinstance(ex, dict):
                    continue
                ex2, why = retag_source(a.job, vid, ex, guide, a.out)
                print("재태깅", vid, why, flush=True)
                note.setdefault("retag", {})[vid] = why
                ext2[vid] = ex2
        with open(os.path.join(a.out, "extract_new.json"), "w", encoding="utf-8") as f:
            json.dump(ext2, f, ensure_ascii=False)
        job = dict(job, extract=ext2)
        # ★패치본 패키지(/tmp/patch)로 돌리면 _source_block 이 이미 훅·속도·뒷컷을 싣는다 — 그땐 덧붙이지 않는다
        if "훅:" not in ba._source_block.__code__.co_consts.__repr__():
            patch_source_block(ba)
    if a.mode == "story":
        # 2026-10-01: 소스마다 1단계 스토리(story_tag.make_story)를 붙인 뒤 백본 2단계(groups_from_stories)를 돈다 — 라이브 코드 그대로
        from shopping_shorts import story_tag as _st
        ext2 = {}
        for vid, ex in sorted((job.get("extract") or {}).items()):
            if not isinstance(ex, dict):
                continue
            if not ex.get("story"):
                n = {}
                ex = dict(ex, story=_st.make_story(((ex.get("source_brief") or {}) or {}).get("product") or "", ex.get("segments") or [], note=n))
                print("스토리", vid, len(ex["story"]), "줄", n.get("story_reason") or "", flush=True)
                for L in ex["story"]:
                    print("    [%s] %s  (컷 %s)" % (L.get("kind"), L.get("text"), ",".join(c[-6:] for c in L.get("cuts") or [])), flush=True)
            ext2[vid] = ex
        job = dict(job, extract=ext2)
        with open(os.path.join(a.out, "extract_story.json"), "w", encoding="utf-8") as f:
            json.dump(ext2, f, ensure_ascii=False)
    # 작가에게 들어간 재료 블록도 남긴다(무엇이 달라졌나를 눈으로 보려고)
    srcs = ba.sources_from_extract(job.get("extract") or {})
    seg_index = ba._seg_index(srcs)
    # seg_index에 start/end를 보탠다(프레임 뽑기용)
    for s in srcs:
        for x in (s.get("segments") or []):
            if x.get("seg_id") in seg_index:
                seg_index[x["seg_id"]].update(start=x.get("start"), end=x.get("end"))
    with open(os.path.join(a.out, "writer_materials.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(ba._source_block(s, False) for s in srcs))
    if a.mode == "live":
        ss = job.get("script_structure") or {}
        res = {"given": job.get("given_script") or "", "beat_sources": ss.get("beat_sources") or [], "spine": None,
               "report": None, "groups": None, "note": note}
    elif a.writer == "story_writer":
        from shopping_shorts import story_writer as _sw
        drafts, why = _sw.make_drafts([], job, int(job.get("target_seconds") or 25), job_id=a.job, preset="short",
                                      seed_text="", seed_product=srcs[0].get("source_brief", {}).get("product", "") if srcs else "")
        note["story_writer_why"] = why
        if not drafts:
            sys.exit("이야기작가 실패: %s" % why)
        d = drafts[0]
        res = {"given": d.get("script") or "\n".join(b.get("text") or "" for b in d.get("beats") or []),
               "beat_sources": [{"role": b.get("role"), "seg": (b.get("src_segs") or [b.get("src_seg")] or [""])[0] or "", "segs": [str(x) for x in (b.get("src_segs") or ([b.get("src_seg")] if b.get("src_seg") else []))]} for b in d.get("beats") or []],
               "spine": {"name": d.get("style_name")}, "report": None, "groups": None, "note": dict(note, writer_note=d.get("writer_note"))}
    else:
        res = run_assemble(job, a.job, store, note)
        if not res:
            sys.exit("assemble 실패: %s" % json.dumps(note, ensure_ascii=False)[:300])
    res["rows"] = frames_for_lines(a.job, res["given"], res["beat_sources"], seg_index, a.out)
    res["mode"], res["job"], res["secs"] = a.mode, a.job, round(time.time() - t0, 1)
    res["tags"] = {k: [{kk: s.get(kk) for kk in ("seg_id", "start", "end", "label", "use_point", "change", "product_benefits",
                                                   "is_key", "shot_role") + EXTRA_KEYS if s.get(kk) not in (None, "", [])}
                       for s in (v.get("segments") or []) if isinstance(s, dict)]
                   for k, v in sorted((job.get("extract") or {}).items()) if isinstance(v, dict)}
    with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("완료", a.mode, "줄", len(res["beat_sources"] or []), "%.0fs" % (time.time() - t0),
          "| 줄별 컷 수", [len((b or {}).get("segs") or []) for b in (res["beat_sources"] or [])])


if __name__ == "__main__":
    main()
