# -*- coding: utf-8 -*-
"""편집 화면 미리보기 영상 vs '완성본 만들기' 영상 — 칸마다 장면·시각을 **영상 프레임으로** 비교한다(2026-09-27).

왜: 계산끼리 비교하면 같은 함수라 늘 같다(2026-09-26에 그걸로 '됐다'고 세 번 틀렸다). 고객이 보는 건 영상이다.
  ① 편집 화면 미리보기 = app._pvproxy_build(편집 화면 컷, 원본 소스) — 화면이 서버에 요청해 굽는 그 함수
  ② 완성본 만들기    = render_inputs_for(allow_clean=False) + assemble(preview_preset) — run_preview와 같은 조립
  칸마다 25/50/75% 지점을 ①에서 찍고 ②의 같은 칸 같은 비율 지점 ±0.3초에서 가장 닮은 프레임을 찾는다.
  차이(0~255 평균) > 18 이면 다른 장면으로 본다(자막 유무 차이는 대개 3~14). 밀림 = 가장 닮은 시각 - 기대 시각.

서버: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
      python3 tools/editor_vs_final_video.py [N최근작업=30] [job_id ...]
결과: /tmp/evf/report.txt (작업별·칸별), 임시 영상은 /tmp/evf/<job>/ (고객 파일 불변)
"""
import json, subprocess, sys, sqlite3, hashlib, shutil
from pathlib import Path
sys.path.insert(0, ".")
from PIL import Image, ImageChops, ImageStat

import os, importlib.util
if os.getenv("PATCH_DIR"):          # 배포 전 대조: 고친 모듈을 먼저 얹는다
    import shopping_shorts
    for _n in ("screen_clips", "video_assemble", "clean_base", "mix_pipeline"):
        _f = Path(os.getenv("PATCH_DIR")) / ("%s.py" % _n)
        if _f.exists():
            _sp = importlib.util.spec_from_file_location("shopping_shorts." + _n, str(_f))
            _m = importlib.util.module_from_spec(_sp); sys.modules["shopping_shorts." + _n] = _m
            _sp.loader.exec_module(_m); setattr(shopping_shorts, _n, _m)
    _fa = Path(os.getenv("PATCH_DIR")) / "app.py"
    if _fa.exists():                 # app 은 통째로 못 얹는다(정적 파일 경로) — 미리보기 굽기 함수만 바꿔 끼운다
        from shopping_shorts import app as _app
        _src = _fa.read_text(encoding="utf-8")
        _i = _src.index("def _pvproxy_build("); _j = _src.index(chr(10) + "@app.", _i)
        exec(compile(_src[_i:_j], str(_fa), "exec"), _app.__dict__)
OUT = Path("/tmp/evf"); OUT.mkdir(exist_ok=True)
THRESH = 18.0


def _dur(p):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "csv=p=0", str(p)]).strip())
    except Exception:
        return 0.0


def _grab(f, t, o):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % max(0.0, t), "-i", str(f), "-frames:v", "1",
                    "-vf", "scale=90:160", str(o)])
    try:
        return Image.open(o).convert("L")
    except Exception:
        return None


def check(jid):
    from shopping_shorts import app, mix_pipeline as mp, video_assemble as va, screen_clips as sc
    from shopping_shorts.store import Store
    st = Store("shopping_shorts/data/reference.db"); job = st.get_mix_job(jid)
    w = Path("shopping_shorts/data/mix_jobs") / jid
    plan = (job or {}).get("edit_plan") or {}
    beats = [b for b in plan.get("beats") or [] if b.get("tts_path") and Path(b["tts_path"]).exists()]
    if not beats:
        return None, "음성 없음"
    wd = OUT / jid
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    # ① 편집 화면 미리보기 — 화면과 같은 컷(screen_clips 러너) → 화면이 부르는 굽기 함수
    if sc.warm(job) <= 0:
        return None, "화면 계산 실패"
    cuts, blens = [], []
    for b in plan["beats"]:
        r = sc._CACHE.get(sc.beat_key(b)) or {}
        cl = [{"video_id": c["v"], "start": round(float(c["s"]), 3), "dur": round(float(c["d"]), 3),
               "src_dur": round(float(c["sd"] if c["sd"] is not None else c["d"]), 3), **({"fit": 1} if c.get("fit") else {})}
              for c in (r.get("c") or [])]
        cuts += cl; blens.append(len(cl))
    sig = "evf" + hashlib.sha1(json.dumps([cuts, blens]).encode()).hexdigest()[:12]
    srcs = {k: v for k, v in (mp._resolve_sources(job, w) or {}).items() if v and Path(v).exists()}
    tts = {int(b["beat_idx"]): b["tts_path"] for b in plan["beats"] if b.get("tts_path") and Path(b["tts_path"]).exists()}
    app._pvproxy_build(jid, sig, cuts, srcs, blens, tts)
    E = app._pvproxy_dir(jid) / ("%s.mp4" % sig)
    meta = json.loads((app._pvproxy_dir(jid) / ("%s.json" % sig)).read_text(encoding="utf-8"))
    if not E.exists():
        return None, "화면 미리보기 굽기 실패"
    # ② 완성본 만들기(임시 파일)
    F = wd / "final_preview.mp4"
    plan_used, paths, _b = mp.render_inputs_for(st, job, jid, w, [], job.get("customer_id") or 0, allow_clean=False)
    with mp.preview_preset():
        mp.assemble(plan_used, tts, paths, str(F), clean_fn=None, deco={})
    if not F.exists():
        return None, "완성본 렌더 실패"
    # 칸 경계: ① = 굽기 기록(offs), ② = 음성 길이 누적(자막과 같은 자 — _beat_timeline)
    offs = meta.get("offs") or []
    e_end = offs[1:] + [meta.get("dur") or _dur(E)]
    f_t, rows = 0.0, []
    for k, b in enumerate(plan["beats"]):
        if int(b["beat_idx"]) not in tts or k >= len(offs):
            continue
        td = float(va._beat_effective_dur(b, tts[int(b["beat_idx"])]))
        e0, e1 = offs[k], e_end[k]
        worst, shifts = 0.0, []
        for q in (0.25, 0.5, 0.75):
            ref = _grab(E, e0 + (e1 - e0) * q, wd / "e.jpg")
            if ref is None:
                continue
            tq = f_t + td * q
            best = min(((ImageStat.Stat(ImageChops.difference(ref, im)).mean[0], s) for s in [x * 0.05 for x in range(-6, 7)]
                        for im in [_grab(F, tq + s, wd / "f.jpg")] if im is not None), default=(255.0, 0.0))
            worst = max(worst, best[0]); shifts.append(best[1])
        rows.append((int(b["beat_idx"]), round(worst, 1), max(shifts, key=abs) if shifts else 0.0,
                     round((e1 - e0) - td, 3)))
        f_t += td
    # 눈 확인용 사진: 위 = 편집 화면 미리보기 칸 가운데, 아래 = 완성본 같은 칸 가운데(자막·확대 차이는 사람이 걸러 본다)
    try:
        ft2, tiles = 0.0, []
        for k, b in enumerate(plan["beats"]):
            if int(b["beat_idx"]) not in tts or k >= len(offs):
                continue
            td = float(va._beat_effective_dur(b, tts[int(b["beat_idx"])]))
            a = _grab(E, (offs[k] + e_end[k]) / 2, wd / ("sE%d.jpg" % k)); c = _grab(F, ft2 + td / 2, wd / ("sF%d.jpg" % k))
            ft2 += td
            tiles.append((wd / ("sE%d.jpg" % k), wd / ("sF%d.jpg" % k)))
        im = Image.new("RGB", (90 * len(tiles), 320))
        for i, (a, c) in enumerate(tiles):
            im.paste(Image.open(a).convert("RGB"), (i * 90, 0)); im.paste(Image.open(c).convert("RGB"), (i * 90, 160))
        im.save(OUT / ("eye_%s.jpg" % jid))
    except Exception:      # noqa: BLE001
        pass
    return {"job": jid, "rows": rows, "E": _dur(E), "F": _dur(F), "tts": round(f_t, 3)}, ""


def main():
    args = sys.argv[1:]
    n = int(args[0]) if args and args[0].isdigit() else 30
    ids = [a for a in args if not a.isdigit()]
    if not ids:
        con = sqlite3.connect("shopping_shorts/data/reference.db")
        ids = [r[0] for r in con.execute("select job_id from mix_jobs where preview_status='ready' order by updated_at desc limit ?", (n,))]
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    bad_scene = bad_shift = tot = 0
    for jid in ids:
        try:
            r, why = check(jid)
        except Exception as e:      # noqa: BLE001
            r, why = None, "%s: %s" % (type(e).__name__, str(e)[:120])
        if not r:
            print(jid, "건너뜀", why, file=rep, flush=True); continue
        bs = [x for x in r["rows"] if x[1] > THRESH]
        sh = [x for x in r["rows"] if abs(x[2]) >= 0.15]
        tot += len(r["rows"]); bad_scene += len(bs); bad_shift += len(sh)
        print("%s 칸%d 화면%.2fs 완성본%.2fs 음성%.2fs | 다른장면 %s | 밀림0.15+ %s" % (
            jid, len(r["rows"]), r["E"], r["F"], r["tts"], [(x[0], x[1]) for x in bs], [(x[0], x[2]) for x in sh]), file=rep, flush=True)
    print("== 칸 %d · 다른 장면 %d · 0.15초 이상 밀림 %d" % (tot, bad_scene, bad_shift), file=rep, flush=True)


if __name__ == "__main__":
    main()
