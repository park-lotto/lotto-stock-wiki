# -*- coding: utf-8 -*-
"""대본 → 실제 뽑힌 장면 보기 (2026-09-22 사장님 "렌더 말고 대본이랑 실제 장면 뽑힌 걸 몇 초짜리인지 눈으로").

서버에서 돈다(읽기 전용·저장 없음). 2단계 이야기 작가로 대본을 새로 뽑고 → 3단계 상속 편성 → 컷 리듬 조각 줄이기 →
렌더 규칙(plan_beat_clips_for)으로 줄마다 실제 구간을 계산 → 그 구간을 ffmpeg로 잘라 HTML에 대본 옆에 붙인다.
  PYTHONPATH=<코드경로> python3 tools/seed_analyzer/scene_view.py --job <job_id> --out /tmp/show [--preset short|full] [--repeat 1]
이 PC: scp로 받아 index.html을 연다. 렌더(5분) 대신 2분.
"""
import argparse, html, json, os, re, subprocess, sys

ROOT = os.environ.get("LSW_ROOT", "/home/ubuntu/lotto-stock-wiki")
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", default="/tmp/show")
    ap.add_argument("--preset", default="short")
    ap.add_argument("--seconds", type=int, default=25)
    ap.add_argument("--db", default="/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    ap.add_argument("--work", default="/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs")
    a = ap.parse_args()
    from shopping_shorts.store import Store
    from shopping_shorts import edit_plan as ep, mix_pipeline as mp, video_assemble as va, story_writer as sw
    from shopping_shorts.app import _enrich_job_extract
    os.makedirs(os.path.join(a.out, "clips"), exist_ok=True)
    store = Store(a.db); job = _enrich_job_extract(store.get_mix_job(a.job), store)
    extract = job.get("extract") or {}
    srcs = [{"video_id": vid, "segments": (ex or {}).get("segments") or []} for vid, ex in extract.items() if isinstance(ex, dict)]
    paths = {}
    for vid in extract:
        d = os.path.join(a.work, a.job, vid)
        if os.path.isdir(d):
            m = [f for f in os.listdir(d) if f.endswith(".mp4")]
            if m:
                paths[vid] = os.path.join(d, m[0])
    src_durs = {}
    for vid, p in paths.items():
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip()
        src_durs[vid] = float(o or 0)
    seg_map, _ = ep._build_inventory(srcs)
    tag = {}
    for vid, ex in extract.items():
        for s in (ex or {}).get("segments") or []:
            tag[s.get("seg_id")] = s
    def tag_at(vid, t):
        for s in (extract.get(vid) or {}).get("segments") or []:
            if float(s.get("start", 0)) <= t < float(s.get("end", 0)):
                return s
        return {}
    drafts, why = sw.make_drafts([], job, a.seconds, job_id=a.job, preset=a.preset)
    if not drafts:
        print("대본 실패:", why); return
    d = drafts[0]; lines = [b["text"] for b in d["beats"]]
    beat_sources = [{"role": b["role"], "seg": b.get("src_seg"), "segs": b.get("src_segs") or []} for b in d["beats"]]
    plan = ep.build_inherit_plan(srcs, "\n".join(lines), beat_sources, structure="template")
    mp._trim_for_cut_rhythm(plan)
    titles = {v: ((e.get("source_brief") or {}).get("product") or e.get("title") or v) for v, e in extract.items() if isinstance(e, dict)}
    H = ["<meta charset=utf-8><style>body{font-family:sans-serif;background:#111;color:#eee;max-width:1400px;margin:16px auto}"
         ".row{display:flex;gap:12px;align-items:flex-start;border-bottom:1px solid #333;padding:12px 0}.txt{width:400px;font-size:15px;line-height:1.5}"
         ".role{color:#9cf;font-size:12px}.hold{color:#fc6;font-size:12px}video{height:300px;border-radius:6px;background:#000}"
         ".cap{font-size:12px;color:#aaa;text-align:center;max-width:180px}.tag{font-size:11px;color:#8b8;max-width:180px}</style>",
         "<h2>대본 → 실제 뽑힌 장면 · job %s · %s</h2><p style='color:#aaa;font-size:12px'>재료: %s</p>" % (a.job, a.preset, html.escape(" / ".join("%s=%s" % (k, v[:14]) for k, v in titles.items())))]
    tot = 0; ncut = 0
    for b in plan["beats"]:
        t = ep.narr_secs(b["narration"]); tot += t
        clips = va.plan_beat_clips_for(b, t, src_durs); ncut += len(clips)
        H.append("<div class=row><div class=txt><div class=role>%d. %s %s · 대사 %.1f초</div>%s</div>" % (
            b["beat_idx"] + 1, b.get("role", ""), "<span class=hold>홀드</span>" if (b.get("cut_rhythm") or {}).get("hold") else "", t, html.escape(b["narration"])))
        for k, c in enumerate(clips):
            vid = c["video_id"]; p = paths.get(vid)
            if not p:
                H.append("<div class=cap>%s 파일 없음</div>" % vid); continue
            out = os.path.join(a.out, "clips", "b%d_%d.mp4" % (b["beat_idx"], k))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(c["start"]), "-t", str(max(0.3, c["src_dur"])), "-i", p,
                            "-vf", "scale=-2:300", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", out])
            s = tag_at(vid, c["start"] + 0.05)
            H.append("<div><video src=clips/%s muted autoplay loop playsinline></video><div class=cap>%s %.1f~%.1f초 · 화면 %.1f초</div><div class=tag>%s · %s</div></div>" % (
                os.path.basename(out), vid, c["start"], c["start"] + c["src_dur"], c["out_dur"], html.escape(str(s.get("shot_role") or "")), html.escape((s.get("scene_desc") or "")[:40])))
        H.append("</div>")
    H.append("<p>총 %d줄 · 대사 %.1f초(추정) · 컷 %d개</p>" % (len(lines), tot, ncut))
    open(os.path.join(a.out, "index.html"), "w", encoding="utf-8").write("\n".join(H))
    print("done 줄", len(lines), "컷", ncut, "초 %.1f" % tot)


if __name__ == "__main__":
    main()
