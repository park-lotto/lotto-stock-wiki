"""벤치 자막팩 3벌 점검(관제 235) — 하이브리드 자막표 그대로 실제 렌더해서 벤치 수치와 대조한다.

  py tools/caption_pack/check_bench_packs.py [<출력폴더>] [팩,...] [--no-compose]
     기본 출력 = out/check_bench_packs · 팩 = kitchit,kkultemnote,starpick

팩마다 칼카피 트랙의 하이브리드 자막표(channel/<채널>/하이브리드_성시경/자막표.json)를 비트(timeline)로 옮겨
렌더(scene_style.render_layers → compose)하고:
  ① 넘침 튀어나옴: 등장 30fps 크기 곡선(잉크 폭 ÷ 끝 폭) = 보강안 수치(계약 파일 키프레임) ±5%p · 반투명 등장 첫 프레임 투명도
     + 줄 첫 덩어리만 등장, 같은 줄 다음 덩어리는 바로(자막표의 enter 열과 장면별 등장 유무 대조)
  ② 말 맞춘 타이핑: 글자가 나온 프레임 = 비트에 실은 글자 시각 ±1프레임 · 새 글자 첫 프레임 번쩍 색
  ③ 핵심 단어 색: 정지 그림에 기대 색(±10)이 칠해졌나 · 강조 없는 줄엔 안 칠했나
  ④ 화자별 글꼴: 같은 글을 나레/원음으로 찍으면 그림이 다르다
  ⑤ 캡컷 그림(overlay_spans)·썸네일(render_layer_one)이 다 나온 자막 + 강조로 찍혔나(정지 그림과 대조)
그리고 벤치 프레임과 나란히 시트(<팩>_비교.jpg)와 하이브리드 미리보기 영상(<팩>_hybrid.mp4, 자막 입힌 완성본)을 남긴다.

★자막표 → 비트 옮기기(rows_to_timeline)는 하이브리드 쪽이 그대로 쓰면 되는 견본이다 — 장면 자료 꼴의 주인은
  shopping_shorts/scene_style.py scene_marks·_attach_scene_chars(비트의 speaker·variant·emph·caption_marks·chars).
"""
import json, math, pathlib, re, shutil, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageChops, ImageDraw, ImageFont
from shopping_shorts import scene_style, video_assemble as va

CONTRACT = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
MOTIONS = json.loads(CONTRACT.split("/*JSON*/")[1])
PACKS = json.loads(CONTRACT.split("/*PACKS*/")[1])
CHANNEL = {"kitchit": "kitchit", "kkultemnote": "kkultemnote", "starpick": "starpickroom"}
BENCH = pathlib.Path("C:/숏템_칼카피")


def tables_dir():
    for c in (ROOT.parent / "칼카피숏템엔진/channel", ROOT / ".tracks/칼카피숏템엔진/channel", ROOT / "channel"):
        if (c / "kitchit/하이브리드_성시경/자막표.json").exists():
            return c
    raise SystemExit("자막표를 못 찾았다 — 칼카피숏템엔진 트랙 channel/ 이 필요하다")


# ── 자막표(채널마다 열 이름이 다르다) → 공통 줄 ─────────────────────────────────────
def norm_rows(pack, table):
    out = []
    for r in table["rows"]:
        if pack == "kitchit":
            row = {"line": r["line"], "t0": r["t0"], "t1": r["t1"], "text": r["text"], "speaker": "narr" if r["kind"] == "나레" else "orig",
                   "emph": [{"word": r["emph"]}] if r.get("emph") else [],     # ★색은 안 싣는다 — 팩의 5색 돌림이 자막표와 같은 색을 내는지 잰다
                   "want_hex": [r["emph_hex"]] if r.get("emph_hex") else [], "variant": "typing" if r.get("typing") else "",
                   "sticker": r.get("sticker") if r.get("sticker") == "heart" else "", "enter_pop": r.get("enter") == "pop", "typing": bool(r.get("typing")),
                   "stickers": [{"kind": r["sticker"], "word": r.get("emph") or ""}] if r.get("sticker") in ("gem", "spark_lines") else []}
            if row["typing"]:   # 원음 타이핑 = 0.1초마다 한 글자(벤치 BRa 8.0~8.9 실측), 줄이 짧으면 줄 안에 들어오게
                n = len(row["text"].replace(" ", "")); step = min(.1, (r["t1"] - r["t0"]) * .8 / max(1, n))
                row["chars"] = [round(r["t0"] + k * step, 3) for k in range(n)]
        elif pack == "kkultemnote":
            v = r.get("style") or ""
            row = {"line": r["line"], "t0": r["t0"], "t1": r["t1"], "text": r["text"], "speaker": "narr" if r["who"] == "나레" else "orig",
                   "emph": [{"word": w} for w in r.get("emph") or []], "want_hex": ["#F51814" if v == "orig_red" else "#FDF60E"] if r.get("emph") else [],
                   "variant": v if v in ("orig_pop", "orig_red") else "", "sticker": "", "typing": False}
        else:   # starpick
            narr = str(r.get("speaker", "")).startswith("나레")
            row = {"line": f'{r["line"]}', "t0": r["t0"], "t1": r["t1"], "text": r["text"], "speaker": "narr" if narr else "orig",
                   "emph": [{"word": e["word"], "color": e["hex"], **({"grow": e["grow"]} if e.get("grow") else {})} for e in r.get("emph") or []],
                   "want_hex": [e["hex"] for e in r.get("emph") or []], "variant": "", "sticker": "", "typing": bool(r.get("typing"))}
            if row["typing"] and r.get("type_cps"):
                n = len(row["text"].replace(" ", "")); row["chars"] = [round(r["t0"] + k / float(r["type_cps"]), 3) for k in range(n)]
        out.append(row)
    return out


def rows_to_timeline(rows, tts, total=None):
    """공통 줄 → 비트(줄 하나 = 비트 하나, 덩어리 = caption_lines). 장면 창 = 자막표 시각 그대로(cap_durs = 다음 덩어리 시작까지).
    ★비트는 빈틈 없이 잇는다(다음 줄 시작까지, 마지막 줄은 영상 끝 total 까지) — compose 는 장면들을 이어 붙여 영상을 만들므로
      줄 사이 틈을 비워 두면 그만큼 영상이 잘린다(실측: 키치잇 28.47→28.26초). 첫 줄이 0초가 아니면 첫 비트를 0초부터 시작한다.
    하이브리드 쪽 견본: 화자·줄 변형·핵심 단어·스티커는 caption_marks(덩어리별), 글자 시각은 chars(비트 t0 부터 영상 초)."""
    lines = []
    for r in rows:
        if lines and lines[-1][0]["line"] == r["line"]:
            lines[-1].append(r)
        else:
            lines.append([r])
    beats = []
    for i, ln in enumerate(lines):
        t0 = 0.0 if i == 0 else ln[0]["t0"]
        t1 = lines[i + 1][0]["t0"] if i + 1 < len(lines) else max(ln[-1]["t1"], total or 0)
        lead = ln[0]["t0"] - t0
        durs = [(ln[k + 1]["t0"] if k + 1 < len(ln) else t1) - r["t0"] for k, r in enumerate(ln)]
        chars = []
        for r in ln:
            for ch, t in zip(r["text"].replace(" ", ""), r.get("chars") or []):
                chars.append({"char": ch, "start": round(t - t0, 3)})
        beats.append({"beat_idx": i, "t0": t0, "dur": round(t1 - t0, 3), "narration": " ".join(r["text"] for r in ln),
                      "caption_lines": [r["text"] for r in ln], "cap_durs": durs, "cap_lead": round(lead, 3), "tts_path": str(tts),
                      "target_seconds": round(t1 - t0, 3), "role": "body", "primary": {"video_id": "s0", "start": t0, "end": t1},
                      "caption_marks": [{k: v for k, v in (("speaker", r["speaker"]), ("variant", r["variant"]), ("sticker", r["sticker"]), ("emph", r["emph"]), ("stickers", r.get("stickers"))) if v}
                                        for r in ln],
                      **({"chars": chars} if chars else {})})
    return beats


def snapshot(pack):
    return scene_style.validate_snapshot({"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "body",
                                          "frameRule": "body_all", "text": {"channel": "", "hook1": "", "hook2": "", "bodyTitle": ""},
                                          "captionPack": pack, "motionPack": "off", "wordFx": {"style": "mark", "color": "", "grow": ""}})


# ── 그림 재기 ──────────────────────────────────────────────────────────────────
def img(p):
    return Image.open(p).convert("RGBA")


def ink_box(im, a=40):
    return im.split()[3].point(lambda v: 255 if v > a else 0).getbbox()


def alpha_sum(im):
    return sum(im.split()[3].get_flattened_data())


def color_count(im, hexes, tol=10):
    want = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in hexes]
    n = 0
    for px in im.get_flattened_data():
        if px[3] > 200 and any(all(abs(px[c] - w[c]) <= tol for c in range(3)) for w in want):
            n += 1
    return n


def hard_diff(x, y):
    from PIL import ImageFilter
    xa, ya = x.split()[3], y.split()[3]
    hi, lo = ya.filter(ImageFilter.MaxFilter(3)), ya.filter(ImageFilter.MinFilter(3))
    over = ImageChops.subtract(xa, hi); under = ImageChops.subtract(lo, xa)
    return sum(1 for v in ImageChops.lighter(over, under).get_flattened_data() if v > 128)


def curve(motion, t_ms):
    """계약 파일 키프레임의 scale 을 t 에서 선형 보간(easing linear 효과만)."""
    m = MOTIONS[motion]; fr = m["frames"]; n = len(fr)
    offs = [f.get("offset", k / (n - 1)) for k, f in enumerate(fr)]
    sc = [float(str(f.get("scale", 1)).split()[0]) for f in fr]
    p = max(0.0, min(1.0, t_ms / m["ms"]))
    for k in range(n - 1):
        if offs[k] <= p <= offs[k + 1]:
            return sc[k] + (sc[k + 1] - sc[k]) * (p - offs[k]) / max(1e-9, offs[k + 1] - offs[k])
    return sc[-1]


def run(pack, out, compose, fails):
    def need(ok, msg):
        print(("  통과  " if ok else "★ 실패  ") + f"[{pack}] " + msg)
        if not ok: fails.append(f"[{pack}] {msg}")
    table = json.loads((tables_dir() / CHANNEL[pack] / "하이브리드_성시경/자막표.json").read_text(encoding="utf-8"))
    rows = norm_rows(pack, table)
    d = out / pack; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True, exist_ok=True)
    tts = out / "v.wav"
    if not tts.exists():
        va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
    base_video = pathlib.Path(table["video"])
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(base_video)],
                                 capture_output=True, text=True).stdout.strip() or 0) if base_video.exists() else None
    timeline = rows_to_timeline(rows, tts, total); snap = snapshot(pack)
    ctx = scene_style.context_for(timeline, {"text": "x"}, snap, None)
    scenes = [s for s in ctx["scenes"] if s["caption"]]
    need(len(scenes) == len(rows) and all(s["caption"] == r["text"] for s, r in zip(scenes, rows)),
         f"자막표 {len(rows)}줄 = 장면 {len(scenes)}개(글·순서 같음)")
    idx = [i for i, s in enumerate(ctx["scenes"]) if s["caption"]]   # 줄 k → 장면 번호
    layers = scene_style.render_layers(timeline, snap, d / "layers", {"text": "x"}, "bench")
    L = d / "layers"
    still = lambda k: img(L / layers[idx[k]]["file"])
    report = {"pack": pack, "rows": []}

    # ① 등장: 줄 첫 덩어리만(키치잇) / 화자·변형별 등장 길이
    for k, r in enumerate(rows):
        e = layers[idx[k]].get("enterMs") or 0
        report["rows"].append({"text": r["text"], "enterMs": e})
    pk = PACKS[pack]
    if pack == "kitchit":
        want = [r["enter_pop"] or r["typing"] for r in rows]; got = [bool(layers[i].get("enterMs")) for i in idx]
        need(want == got, f"① 등장 있는 줄 = 자막표 pop·타이핑 줄 ({sum(got)}/{len(rows)}, 어긋남 {[rows[k]['text'] for k in range(len(rows)) if want[k] != got[k]]})")
    def measure_curve(k, motion):
        lay = layers[idx[k]]; a = lay.get("animation")
        if not a:
            need(False, f"① '{rows[k]['text']}' 등장 프레임 없음"); return None
        last = ink_box(still(k)); W = last[2] - last[0]
        n = min(a["count"], math.ceil(MOTIONS[motion]["ms"] / 1000 * 30) + 1)
        got, exp = [], []
        for f in range(n):
            b = ink_box(img(L / a["pattern"].replace("%04d", str(f).zfill(4))))
            got.append(round((b[2] - b[0]) / W, 3) if b else 0.0); exp.append(round(curve(motion, f / 30 * 1000), 3))
        bad = [(f, got[f], exp[f]) for f in range(n) if exp[f] >= .1 and abs(got[f] - exp[f]) > .05]
        need(not bad, f"① '{rows[k]['text']}' {motion} 30fps 크기 곡선 {got} vs 보강안 {exp} (±5%p 밖 {bad})")
        return got
    if pack == "kitchit":
        report["curve"] = measure_curve(0, "overPop")
        bench = [61, 115, 163, 205, 241, 268, 289, 299, 300, 289, 281, 277, 275]   # 스타일분석 §1 Cs-Ka 0~0.433초 '1년 내내' 잉크 폭(px)
        report["bench_curve"] = [round(v / 275, 3) for v in bench]
    if pack == "kkultemnote":
        k = next(k for k, r in enumerate(rows) if r["variant"] == "orig_pop"); report["curve"] = measure_curve(k, "overPopBig")
        k = next(k for k, r in enumerate(rows) if r["speaker"] == "narr")
        a = layers[idx[k]].get("animation")
        if a:
            f0 = alpha_sum(img(L / a["pattern"].replace("%04d", "0000"))) / max(1, alpha_sum(still(k)))
            need(abs(f0 - .45) <= .06, f"① 나레 '{rows[k]['text']}' 반투명 등장 첫 프레임 투명도 {f0:.2f} (보강안 0.45) · 등장 {layers[idx[k]].get('enterMs')}ms")
        else:
            need(False, f"① 나레 '{rows[k]['text']}' 반투명 등장 프레임 없음")
        origs = [k for k, r in enumerate(rows) if r["speaker"] == "orig" and not r["variant"]]
        need(all(not layers[idx[k]].get("enterMs") for k in origs), f"① 원음 줄 {len(origs)}개 = 컷인(등장 없음)")

    # ② 타이핑: 글자 나온 프레임
    typing_rows = [k for k, r in enumerate(rows) if r.get("chars")]
    for k in typing_rows[:6]:
        lay = layers[idx[k]]; a = lay.get("animation"); sc = ctx["scenes"][idx[k]]
        if not a:
            need(False, f"② '{rows[k]['text']}' 타이핑 프레임 없음"); continue
        frames = [img(L / a["pattern"].replace("%04d", str(f).zfill(4))) for f in range(a["count"])]
        ink = [alpha_sum(f.crop((0, 0, 1080, 1920))) for f in frames]
        full = alpha_sum(still(k)); n = len(rows[k]["chars"])
        steps = [f for f in range(1, len(ink)) if ink[f] - ink[f - 1] > full / n * .25]
        if ink and ink[0] > full / n * .25: steps = [0] + steps
        want = sorted({math.floor((t - sc["start"]) * 30 + 1e-6) + (0 if abs((t - sc["start"]) * 30 - round((t - sc["start"]) * 30)) < 1e-6 else 1) for t in sc.get("chars") or []})
        miss = [w for w in want if not any(abs(w - s) <= 1 for s in steps)]
        need(sc.get("chars") and not miss, f"② '{rows[k]['text']}' 글자 나온 프레임 {steps} = 글자 시각 {want} ±1 (빗나감 {miss})")
        flash = MOTIONS.get(pk.get("variants", {}).get(rows[k]["variant"], {}).get("enter") or pk.get("speakers", {}).get(rows[k]["speaker"], {}).get("enter") or "", {}).get("flash")
        if flash and flash["color"].upper() in [h.upper() for h in rows[k]["want_hex"]]:
            print(f"  (건너뜀) '{rows[k]['text']}' 강조 색이 번쩍 색과 같아 번쩍을 따로 못 잰다")
        elif flash and steps:
            f = steps[min(1, len(steps) - 1)]
            c_new, c_after = color_count(frames[f], [flash["color"]], 12), color_count(frames[min(len(frames) - 1, f + 2)], [flash["color"]], 12)
            need(c_new > 30 and c_after < c_new * .5, f"② '{rows[k]['text']}' 새 글자 첫 프레임 번쩍 {flash['color']} {c_new}점 → 두 프레임 뒤 {c_after}점")

    # ③ 핵심 단어 색
    for k, r in enumerate(rows):
        im = still(k)
        if r["want_hex"]:
            c = color_count(im, r["want_hex"])
            need(c > 150, f"③ '{r['text']}' 강조 {r['want_hex']} 칠한 점 {c}")
        elif pack == "kitchit":
            c = color_count(im, pk["mark"]["colors"])
            need(c < 30, f"③ '{r['text']}' 강조 없는 줄은 안 칠함(돌림 색 점 {c})")

    # ④ 화자별 글꼴(같은 글 · 나레/원음)
    if any(v.get("font") for v in (pk.get("speakers") or {}).values()):   # 화자마다 글꼴이 다른 팩(꿀템노트)
        same = "같은 글자 화자 비교"
        tl2 = rows_to_timeline([{"line": "A", "t0": 0, "t1": 1, "text": "앞 장면", "speaker": "orig", "variant": "", "sticker": "", "emph": []},
                                {"line": "B", "t0": 1, "t1": 2, "text": same, "speaker": "narr", "variant": "", "sticker": "", "emph": []},
                                {"line": "C", "t0": 2, "t1": 3, "text": same, "speaker": "orig", "variant": "", "sticker": "", "emph": []}], tts)
        lay2 = scene_style.render_layers(tl2, snap, d / "speakers", {"text": "x"}, "bench")
        a_, b_ = img(d / "speakers" / lay2[1]["file"]), img(d / "speakers" / lay2[2]["file"])
        ba, bb = ink_box(a_), ink_box(b_); h = hard_diff(a_, b_)
        need(h > 2000 and ba != bb, f"④ 같은 글 나레/원음 그림이 다르다(진한 차이 {h}점, 잉크 상자 {ba} / {bb})")
        report["speaker_box"] = {"narr": ba, "orig": bb}

    # ⑧ 자리: 정지 그림 자막 잉크 가운데 y = 팩 자리(place.y, 줄 변형이 있으면 그 자리) ±20px
    off = []
    for k, r in enumerate(rows):
        pl = (pk.get("variants", {}).get(r["variant"], {}).get("place") or pk.get("place") or {}).get("y")
        b = ink_box(still(k))
        if pl is None or not b: continue
        cy = (b[1] + b[3]) / 2; want = pl / 100 * 1920
        if abs(cy - want) > 20: off.append((r["text"], round(cy), round(want)))
    need(not off, f"⑧ 자막 자리 = 벤치 자리(팩 place) ±20px (어긋남 {off[:4]})")

    # ⑤ 캡컷(overlay_spans)·썸네일(render_layer_one) = 다 나온 자막 + 강조
    spans = scene_style.overlay_spans(ctx["scenes"], layers, L)
    by_scene = {}
    for sp in spans:
        for j, sc in enumerate(ctx["scenes"]):
            if sc["start"] - 1e-6 <= sp["start"] < sc["end"] - 1e-6:
                by_scene.setdefault(j, []).append(sp); break
    bad = []
    for k, r in enumerate(rows):
        sp = by_scene.get(idx[k]) or []
        if not sp:
            bad.append((r["text"], "그림 없음")); continue
        cap = img(sp[-1]["path"]); a = layers[idx[k]].get("animation")
        st = img(L / a["pattern"].replace("%04d", str(a["count"] - 1).zfill(4))) if a else still(k)   # 기준 = 장면 끝 그림(등장·톡 커짐이 다 끝난 상태)
        ratio = alpha_sum(cap) / max(1, alpha_sum(st))
        hexok = (color_count(cap, r["want_hex"]) > 150) if r["want_hex"] else True
        if ratio < .97 or not hexok:
            bad.append((r["text"], round(ratio, 3), hexok))
    need(not bad, f"⑤ 캡컷 그림 {len(rows)}줄 모두 다 나온 자막+강조 (어긋남 {bad})")
    picks = [k for k, r in enumerate(rows) if r.get("chars") or r["want_hex"]][:2] or [0]
    for k in picks:
        p = scene_style.render_layer_one(timeline, snap, d / f"thumb_{k}", idx[k], {"text": "x"}, "bench")
        th = img(p); st = still(k); h = hard_diff(th, st) + hard_diff(st, th)
        need(h == 0, f"⑤ 썸네일 '{rows[k]['text']}' = 정지 그림(진한 차이 {h}점)")

    # ⑥ 편집기: 팩 카드를 누르면 장면마다 계획대로 움직인다(돌고 있는 애니메이션 > 0 / 컷인 장면은 0) · 오류 0
    editor_check(pack, ctx, need)

    # 완성본(하이브리드 미리보기) + 벤치 나란히 시트
    final = None
    base = pathlib.Path(table["video"])
    if compose and base.exists():
        final = out / f"{pack}_hybrid.mp4"
        scene_style.compose(str(base), timeline, snap, str(final), d / "cw", {"text": "x"})
        need(final.exists() and final.stat().st_size > 100_000, f"완성본 {final.name} {final.stat().st_size if final.exists() else 0}바이트")
        vdur = lambda p: float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)
        need(abs(vdur(final) - vdur(base_video)) <= 1 / 30 + .01, f"완성본 화면 길이 {vdur(final):.3f}초 = 바탕 영상 화면 {vdur(base_video):.3f}초(±1프레임)")
        report["final"] = str(loud(final, out / f"{pack}_final.mp4", need))
    sheet(pack, rows, ctx, idx, layers, L, final, out, report)
    (out / f"{pack}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


def loud(src, dst, need, target=-14.0):
    """음량 −14 LUFS(사장님 결정, 2단 loudnorm) · 영상은 그대로 복사 · 길이 그대로(-t)."""
    import json as _j
    D = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    j = _j.loads(m[m.rindex("{"):m.rindex("}") + 1])
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000")
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(src), "-t", D, "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", str(dst)])
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(dst), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    got = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
    need(abs(got - target) <= .5, f"음량 {dst.name} {got} LUFS (목표 {target})")
    return dst


RUNNING = """()=>{const t=document.querySelector('.precision-text[data-edit-bind="caption"]');if(!t)return -1;
  return [t,...t.querySelectorAll('.cap-u')].reduce((n,e)=>n+e.getAnimations().filter(a=>a.playState==='running').length,0)}"""


STK = {"gem": ["#29B6F6", "#0288D1", "#81D4FA"], "gem_edge": ["#0D47A1"], "red": ["#FF1E1E"], "green": ["#2ED15A"]}


def cbox(im, hexes, tol=18):
    """그 색(±tol) 점들의 상자와 개수(2px 간격 표본)."""
    px = im.load(); want = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in hexes]
    xs, ys = [], []
    for y in range(0, im.size[1], 2):
        for x in range(0, im.size[0], 2):
            c = px[x, y]
            if c[3] > 200 and any(all(abs(c[j] - w[j]) <= tol for j in range(3)) for w in want):
                xs.append(x); ys.append(y)
    return ((min(xs), min(ys), max(xs) + 2, max(ys) + 2) if xs else None), len(xs)


def sticker_check(out, need, tts):
    """⑦ 2단계 스티커 — 키치잇 팩 장면에 스티커 6종을 실어 렌더하고 자리·크기·움직임·이어짐·캡컷·썸네일을 잰다(수치 = 세 보강안)."""
    d = out / "_stickers"; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True, exist_ok=True)
    src = d / "obj.png"   # 누끼 견본(하이브리드는 실제 누끼 PNG 를 src 로 준다)
    im = Image.new("RGBA", (300, 360), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((70, 60, 230, 350), 40, fill=(170, 110, 40, 255), outline=(90, 50, 10, 255), width=8); dr.rectangle((110, 10, 190, 70), fill=(40, 120, 40, 255))
    im.save(src)
    R = lambda line, t0, t1, text, **kw: {"line": line, "t0": t0, "t1": t1, "text": text, "speaker": "narr", "variant": "", "sticker": "", "emph": [], **kw}
    rows = [R("A", 0, 1.5, "고급 그 자체", stickers=[{"kind": "gem", "word": "고급"}]),
            R("B", 1.5, 3.0, "진짜 중국집 요리", stickers=[{"kind": "spark_lines", "word": "중국집"}]),
            R("C", 3.0, 4.5, "이 가방 하나로 끝", stickers=[{"kind": "circle_arrow", "x": 50, "y": 45, "r": 20}]),
            R("D", 4.5, 6.0, "오 마이 갓", stickers=[{"kind": "kk_doodle"}]),
            R("E", 6.0, 7.5, "댓글 반응이 난리", stickers=[{"kind": "comment_card", "text": "표고에 어묵에 바지락살 들어간 순간 이미 다른 요리임", "likes": 286, "hold": 2.2}]),
            R("E", 7.5, 9.0, "다음 줄도 카드 그대로"),
            R("F", 9.0, 10.5, "땅콩버터 한 스푼", stickers=[{"kind": "object_pop", "src": str(src), "hold": "beat"}]),
            R("F", 10.5, 12.0, "바나나도 넣어요", stickers=[{"kind": "object_pop", "src": str(src), "hold": "beat"}]),
            R("G", 12.0, 13.5, "끝 장면")]
    tl = rows_to_timeline(rows, tts, 13.5); snap = snapshot("kitchit")
    ctx = scene_style.context_for(tl, {"text": "x"}, snap, None); idx = [i for i, s in enumerate(ctx["scenes"]) if s["caption"]]
    lay = scene_style.render_layers(tl, snap, d / "L", {"text": "x"}, "bench"); L = d / "L"
    still = lambda k: img(L / lay[idx[k]]["file"])
    def frame(k, f):
        a = lay[idx[k]]["animation"]
        return img(L / a["pattern"].replace("%04d", str(min(f, a["count"] - 1)).zfill(4)))
    cap_box = lambda k: ink_box(still(k).crop((0, 1300, 1080, 1405)))   # 자막 줄(키치잇 자리 y1351 ±50)만 — 스티커는 빼고
    def cap_abs(k):
        b = cap_box(k); return (b[0], b[1] + 1300, b[2], b[3] + 1300)
    # 💎 다이아: 글자 1.5배 · 낱말 옆 · 팝 곡선 · 반짝 띠가 0.4초마다
    b, n = cbox(still(0), STK["gem_edge"], 30); cb, _ = cbox(still(0), ["#FFFFFF"], 8)   # 자막 = 흰 글자 점(다이아는 흰색이 아니다)   # 다이아 테두리 색(반짝 띠가 덮어도 늘 보인다)
    fs = 93.6 * PACKS["kitchit"]["size"] / 100   # 자막 글자 크기(plain 본문 93.6px × 팩 크기)
    h_ratio = (b[3] - b[1]) / fs if b else 0
    need(bool(b) and 1.25 <= h_ratio <= 1.65 and (b[0] >= cb[2] - 10 or b[2] <= cb[0] + 10) and abs((b[1] + b[3]) / 2 - (cb[1] + cb[3]) / 2) < 30,
         f"⑦ 💎 다이아: 상자 {b} · 높이/자막 줄 잉크 {h_ratio:.2f}· 글자 {fs:.0f}px 의 {h_ratio:.2f}배(보강안 1.5) · 자막 {cb} 바깥 끝(옆 글자 안 덮음)·세로 가운데")
    hs = []
    for f in range(10):
        bb, _ = cbox(frame(0, f), STK["gem_edge"], 30); hs.append(round(((bb[3] - bb[1]) / (b[3] - b[1])) if bb else 0, 3))
    exp = [round(curve("overPop", f / 30 * 1000 * 433 / 300), 3) for f in range(10)]
    bad = [(f, hs[f], exp[f]) for f in range(10) if exp[f] > .15 and abs(hs[f] - exp[f]) > .07]
    need(not bad, f"⑦ 💎 등장 팝 0.3초 크기 {hs} vs 곡선 {exp} (어긋남 {bad})")
    def shine(f):
        im = frame(0, f).crop(b); px = im.load()
        xs = [x for y in range(im.size[1]) for x in range(im.size[0]) if px[x, y][3] > 200 and min(px[x, y][:3]) > 245]
        return round(sum(xs) / len(xs)) if len(xs) > 20 else None
    sh = [shine(f) for f in (15, 17, 19, 27)]
    need(None not in sh[:3] and len(set(sh[:3])) == 3 and sh[3] is not None and abs(sh[0] - sh[3]) <= 3,
         f"⑦ 💎 흰 반짝 띠가 움직이고 0.4초(12프레임)마다 같은 자리(프레임 15·17·19·27 띠 가운데 x {sh})")
    # 강조선: 낱말 오른쪽 위 · 2프레임 번쩍
    cb = cap_abs(1); top = lambda im: im.crop((cb[0], cb[1] - 110, cb[2], cb[1] - 20))   # '중국집' 뒤에 글자가 있어 선은 자막 줄 위로(오른쪽 위 45°) — 자막 줄 위 띠만 잰다
    bb = ink_box(top(still(1))); a0, a2 = alpha_sum(top(frame(1, 0))), alpha_sum(top(frame(1, 2)))
    need(bool(bb) and a0 < a2 * .2, f"⑦ 강조선: 낱말 오른쪽에 그려짐 {bb} · 첫 프레임 잉크 {a0} → 2프레임 {a2}")
    # 빨간 원 + 화살표: 원 자리·반지름(x50% y45% r20%) · 0.2초 그려짐
    b, n = cbox(still(2), STK["red"])
    reds = [cbox(frame(2, f), STK["red"])[1] for f in range(8)]
    need(bool(b) and abs(b[2] - 756) <= 14 and abs(b[3] - 1080) <= 14 and reds[1] < reds[3] < reds[6],
         f"⑦ 빨간 원: 오른쪽·아래 끝 ({b and b[2]},{b and b[3]}) = 원 (760,1084) ±14 · 빨간 점 프레임별 {reds}")
    # ㅋㅋㅋ: 자막 왼쪽 위 초록 선 · 번쩍
    cb = cap_abs(3); b, n = cbox(still(3), STK["green"]); g0 = cbox(frame(3, 0), STK["green"])[1]
    need(bool(b) and b[2] <= cb[0] + 80 and b[3] <= cb[1] + 30 and g0 < max(1, n) * .3, f"⑦ ㅋㅋㅋ: 초록 선 {b} · 자막 {cb} 왼쪽 위 · 첫 프레임 {g0}/{n}")
    # 댓글 카드: 아래변 1505 · 높이 142 · 가운데 · 다음 장면도 · 2.2초 뒤엔 없음
    def card(im):   # 아래 여백 줄(y1500)에서 가로 끝을 찾고, 왼쪽 여백 세로줄로 위끝을 잰다(글자에 안 걸리게)
        px = im.load(); W = lambda x, y: px[x, y][3] > 250 and min(px[x, y][:3]) > 245
        xs = [x for x in range(1080) if W(x, 1500)]
        if not xs: return None
        x0, x1 = min(xs), max(xs); y1 = 1500
        while y1 + 1 < 1920 and W(x0 + 6, y1 + 1): y1 += 1
        y0 = 1500
        while y0 - 1 > 0 and W(x0 + 6, y0 - 1): y0 -= 1
        return (x0, y0, x1, y1)
    c4, c5, c6 = card(still(4)), card(still(5)), card(still(6))
    need(bool(c4) and abs(c4[3] - 1505) <= 6 and abs((c4[3] - c4[1] + 1) - 142) <= 8 and abs((c4[0] + c4[2]) / 2 - 540) <= 6 and bool(c5) and all(abs(a - b_) <= 3 for a, b_ in zip(c4, c5)) and not c6,
         f"⑦ 댓글 카드: {c4} 아래변 1505·높이 142·가운데 · 다음 장면 {c5} · 2.2초 뒤 없음 {not c6}")
    # 3D 재료: x≈180 · 폭 280 · 팝 .4→1.08→1 · 같은 줄 다음 장면에 이어지고 둘째는 옆으로
    zone = lambda im: im.crop((0, 1150, 1080, 1919))
    def obj(im):   # 갈색 병 그림(자막 글자 빼고)
        bb, _ = cbox(im, ["#AA6E28"], 20); return bb
    o6, o7 = obj(still(6)), obj(still(7))
    ws = []
    for f in range(11):
        bb = obj(frame(6, f)); ws.append(round((bb[2] - bb[0]) / (o6[2] - o6[0]), 3) if bb and o6 else 0)
    need(bool(o6) and abs(o6[0] - (180 + 70 * 280 / 300)) <= 30 and o6[1] >= cap_abs(6)[3] and abs((o6[2] - o6[0]) - 160 * 280 / 300) <= 20 and max(ws) >= 1.04 and ws[1] < .8,
         f"⑦ 3D 재료: 병 상자 {o6}(그림 x180·폭280 안 병 x≈245·폭≈150) · 팝 폭 비율 {ws}")
    need(bool(o7) and (o7[2] - o7[0]) >= (o6[2] - o6[0]) + 120, f"⑦ 3D 재료: 같은 줄 다음 장면에 이어지고 둘째가 옆에 쌓임(병 폭 {o6 and o6[2] - o6[0]} → {o7 and o7[2] - o7[0]})")
    # 캡컷·썸네일
    spans = scene_style.overlay_spans(ctx["scenes"], lay, L); bad = []
    for k in range(8):
        sc = ctx["scenes"][idx[k]]; sp = [s for s in spans if sc["start"] - 1e-6 <= s["start"] < sc["end"] - 1e-6]
        a = lay[idx[k]].get("animation"); ref = frame(k, a["count"] - 1) if a else still(k)
        if not sp or alpha_sum(img(sp[-1]["path"])) < alpha_sum(ref) * .97: bad.append(k)
    need(not bad, f"⑦ 캡컷 그림에 스티커까지 다 나옴(어긋남 장면 {bad})")
    for k in (0, 2, 4, 6):
        p = scene_style.render_layer_one(tl, snap, d / f"t{k}", idx[k], {"text": "x"}, "bench"); th = img(p); st = still(k)
        h = hard_diff(th, st) + hard_diff(st, th); need(h == 0, f"⑦ 썸네일 장면 {k}({rows[k]['stickers'][0]['kind']}) = 정지 그림(진한 차이 {h})")
    # 시트: 정지 8장 + 다이아·원·3D 등장 프레임
    bench = []
    for rel, t in (("kitchit/src/BRa5Iv4A3Y8.mp4", 16.3), ("kitchit/src/Cs-Ka_S8nDM.mp4", 10.2), ("kitchit/src/Cs-Ka_S8nDM.mp4", 0.5), ("kitchit/src/_Wa4IehA6yE.mp4", 12.5),
                   ("kkultemnote/src/m0Ex0y1DN5s.mp4", 3.0), ("starpickroom/src/VbpdNba182M.mp4", 19.5)):
        if (BENCH / rel).exists():
            va._run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", str(BENCH / rel), "-frames:v", "1", str(d / "_b.png")])
            bench.append(Image.open(d / "_b.png").convert("RGBA").resize((1080, 1920)))
    shots = [("벤치: 💎 BRa 16.3 · 강조선 Cs-Ka 10.2 · 빨간 원 Cs-Ka 0.5 · ㅋㅋㅋ _Wa 12.5(이 프레임엔 안 보임) · 댓글 카드 m0E 3.0 · 3D 재료 VbpdN 19.5", bench),
             ("우리 정지: 💎 · 강조선 · 빨간 원 · ㅋㅋㅋ · 댓글 카드 · (이어짐) · 3D 재료 · (쌓임)", [still(k) for k in range(8)]), ("💎 0·2·4·8·12·14프레임", [frame(0, f) for f in (0, 2, 4, 8, 12, 14)]),
             ("빨간 원 0·2·4·6 / 3D 0·3·7·10", [frame(2, f) for f in (0, 2, 4, 6)] + [frame(6, f) for f in (0, 3, 7, 10)])]
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    W = 270 * 8; sheet = Image.new("RGB", (W, (480 + 30) * len(shots)), (16, 18, 22)); dr = ImageDraw.Draw(sheet); y = 0
    for title, ims in shots:
        dr.text((8, y + 3), title, fill=(240, 240, 240), font=font); y += 30
        for j, im in enumerate(ims):
            bg = Image.new("RGBA", (1080, 1920), (70, 90, 110, 255)); bg.alpha_composite(im); sheet.paste(bg.convert("RGB").resize((270, 480)), (j * 270, y))
        y += 480
    sheet.save(out / "stickers_시트.jpg", quality=88); print(f"  시트 {out / 'stickers_시트.jpg'}")


def editor_check(pack, ctx, need):
    from playwright.sync_api import sync_playwright
    snap = {**snapshot(pack)}; snap.pop("captionPack"); snap["wordFx"] = {"style": "", "color": "", "grow": ""}
    caps = [i for i, s in enumerate(ctx["scenes"]) if s["caption"]][:12]
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1500, "height": 1100}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "out/scene-style-ui-showcase.html").as_uri()); pg.wait_for_timeout(1200)
        pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(1500)
        pg.evaluate("([c,s])=>window.sceneStyle.load(c,s)", [ctx, snap]); pg.wait_for_timeout(300)
        pg.evaluate("()=>window.sceneStyle.show(1)"); pg.wait_for_timeout(300)
        pg.evaluate(f"()=>document.querySelector('[data-caption-pack=\"{pack}\"]').click()"); pg.wait_for_timeout(500)
        saved = pg.evaluate("()=>window.sceneStyle.snapshot()")
        plan = pg.evaluate("()=>window.sceneStyle.motionPlan()"); bad = []; moved = 0
        for i in caps:
            run = pg.evaluate("""i=>new Promise(res=>{const f=%s;window.sceneStyle.show(i);let m=0;const t0=performance.now();
              const tick=()=>{m=Math.max(m,f());performance.now()-t0<400?requestAnimationFrame(tick):res(m)};requestAnimationFrame(tick)})""" % RUNNING, i)
            moved += run > 0   # 400ms 동안 프레임마다 재서 최댓값(반투명 툭 66ms 처럼 짧은 등장도 잡는다)
            if (run > 0) != bool(plan[i]): bad.append((i, ctx["scenes"][i]["caption"], plan[i], run))
            pg.wait_for_timeout(250)
        need(saved.get("captionPack") == pack and saved.get("wordFx", {}).get("style") == "mark",
             f"⑥ 편집기 카드 누름 → 저장 captionPack={saved.get('captionPack')} · 단어 강조 {saved.get('wordFx', {}).get('style')}")
        need(not bad and moved > 0, f"⑥ 편집기 {len(caps)}장면 넘기며 계획대로 움직임(움직인 장면 {moved}, 계획 {[plan[i] for i in caps]}, 어긋남 {bad[:3]})")
        need(not errs, f"⑥ 편집기 페이지 오류 {len(errs)}건 {errs[:2]}")
        b.close()


# 벤치 프레임(편·초·자막 줄 세로 가운데) — 스타일분석.md·보강안 근거 그대로
BENCH_SHOTS = {
    "kitchit": [("등장 팝", "kitchit/src/Cs-Ka_S8nDM.mp4", [0.0, 1 / 30, 3 / 30, 5 / 30, 8 / 30, 13 / 30], 1351),
                ("원음 타이핑", "kitchit/src/BRa5Iv4A3Y8.mp4", [8.0, 8.1, 8.2, 8.3, 8.4, 8.9], 1300)],
    "kkultemnote": [("나레 반투명·노랑", "kkultemnote/src/BpUOIUwkoG4.mp4", [1.70, 1.733, 3.0, 5.0], 1286),
                    ("원음 톡·빨강", "kkultemnote/src/BpUOIUwkoG4.mp4", [5.83, 5.90, 6.0, 6.2, 9.1, 0.3], 1286)],
    "starpick": [("나레 타이핑 번짐", "starpickroom/src/VbpdNba182M.mp4", [6.7, 7.0, 7.3, 7.6, 8.5, 9.8], 1140),
                 ("원음 즉시·사물 색", "starpickroom/src/VbpdNba182M.mp4", [18.3, 18.6, 20.6, 21.1], 1140)],
}


def bench_frame(rel, t, cy, w=540, h=170):
    src = BENCH / rel; tmp = OUT / "_bench.png"
    va._run_ffmpeg(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", str(tmp)])
    im = Image.open(tmp).convert("RGB")
    return im.crop((0, cy - 170, 1080, cy + 170)).resize((w, h))


def our_frame(path, w=540, h=170, base=(30, 30, 30)):
    im = img(path); b = ink_box(im) or (0, 800, 1080, 1100)
    cy = (b[1] + b[3]) // 2
    bg = Image.new("RGBA", im.size, base + (255,)); bg.alpha_composite(im)
    return bg.convert("RGB").crop((0, cy - 170, 1080, cy + 170)).resize((w, h))


def sheet(pack, rows, ctx, idx, layers, L, final, out, report):
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    tiles = []   # (제목, [그림…])
    for title, rel, times, cy in BENCH_SHOTS[pack]:
        if (BENCH / rel).exists():
            tiles.append((f"벤치 {title} · {pathlib.Path(rel).stem} {times[0]:.2f}~{times[-1]:.2f}초", [bench_frame(rel, t, cy) for t in times]))
    # 우리 쪽: 같은 성격의 장면 — 등장 프레임 / 타이핑 프레임 / 정지(강조)
    def frames_of(k, picks):
        a = layers[idx[k]].get("animation")
        if not a: return [our_frame(L / layers[idx[k]]["file"])]
        return [our_frame(L / a["pattern"].replace("%04d", str(min(a["count"] - 1, f)).zfill(4))) for f in picks]
    if pack == "kitchit":
        tiles.append(("우리 키치잇 등장(같은 프레임 0·1·3·5·8·13)", frames_of(0, [0, 1, 3, 5, 8, 13])))
        k = next(k for k, r in enumerate(rows) if r.get("chars"))
        tiles.append((f"우리 원음 타이핑 '{rows[k]['text']}'(3프레임 간격)", frames_of(k, [0, 3, 6, 9, 12, 15])))
        tiles.append(("우리 정지 — 핵심 단어 5색 돌림", [our_frame(L / layers[idx[k]]["file"]) for k in range(6)]))
    elif pack == "kkultemnote":
        kn = next(k for k, r in enumerate(rows) if r["speaker"] == "narr")
        kp = next(k for k, r in enumerate(rows) if r["variant"] == "orig_pop")
        kr = next(k for k, r in enumerate(rows) if r["variant"] == "orig_red")
        ko = next(k for k, r in enumerate(rows) if r["speaker"] == "orig" and not r["variant"])
        tiles.append(("우리 나레 반투명 등장 0·1프레임 + 노랑 강조 / 원음", frames_of(kn, [0, 1]) + [our_frame(L / layers[idx[kn]]["file"]), our_frame(L / layers[idx[ko]]["file"])]))
        tiles.append(("우리 원음 톡(0·2·4·6·11프레임) + 빨강 줄", frames_of(kp, [0, 2, 4, 6, 11]) + [our_frame(L / layers[idx[kr]]["file"])]))
    else:
        kn = next(k for k, r in enumerate(rows) if r.get("chars"))
        tiles.append((f"우리 나레 타이핑 번짐 '{rows[kn]['text']}'", frames_of(kn, [0, 3, 6, 9, 12, 20])))
        ks = [k for k, r in enumerate(rows) if r["want_hex"]][:4]
        tiles.append(("우리 원음 즉시 · 사물 색 강조", [our_frame(L / layers[idx[k]]["file"]) for k in ks]))
    if final:
        grab = OUT / "_final.png"; shots = []
        for k in [0, len(rows) // 3, 2 * len(rows) // 3, len(rows) - 1]:
            t = (rows[k]["t0"] + rows[k]["t1"]) / 2
            va._run_ffmpeg(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(final), "-frames:v", "1", str(grab)])
            shots.append(Image.open(grab).convert("RGB").resize((270, 480)))
        tiles.append(("우리 완성본(하이브리드 영상 위) 4장면", shots))
        # 자리 대조: 벤치 원본 한 장면 vs 우리 완성본, 같은 빨간 선 = 팩 자리(place.y)
        y = PACKS[pack].get("place", {}).get("y")
        if y is not None:
            pair = []
            rel, t = BENCH_SHOTS[pack][0][1], BENCH_SHOTS[pack][0][2][-1]
            va._run_ffmpeg(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(BENCH / rel), "-frames:v", "1", str(grab)])
            frames_full = [Image.open(grab).convert("RGB")]
            k = 0; tt = (rows[k]["t0"] + rows[k]["t1"]) / 2
            va._run_ffmpeg(["ffmpeg", "-y", "-ss", f"{tt:.3f}", "-i", str(final), "-frames:v", "1", str(grab)])
            frames_full.append(Image.open(grab).convert("RGB"))
            for im in frames_full:
                d_ = ImageDraw.Draw(im); yy = int(y / 100 * 1920); d_.line([(0, yy), (1080, yy)], fill=(255, 0, 0), width=4)
                pair.append(im.resize((270, 480)))
            tiles.append((f"자리 대조 — 왼쪽 벤치 · 오른쪽 우리 · 빨간 선 y{int(y / 100 * 1920)}", pair))
    W = 540 * 6; y = 0; H = sum((30 + max(t.height for t in ims)) for _, ims in tiles)
    sh = Image.new("RGB", (W, H), (16, 18, 22)); dr = ImageDraw.Draw(sh)
    for title, ims in tiles:
        dr.text((8, y + 3), title, fill=(240, 240, 240), font=font); y += 30
        x = 0
        for t in ims:
            sh.paste(t, (x, y)); x += t.width + 4
        y += max(t.height for t in ims)
    sh.save(OUT / f"{pack}_비교.jpg", quality=88)
    print(f"  시트 {OUT / (pack + '_비교.jpg')}")


if __name__ == "__main__":
    args = sys.argv[1:]
    compose = "--no-compose" not in args; args = [a for a in args if a != "--no-compose"]
    OUT = pathlib.Path(args.pop(0) if args and not args[0] in ("kitchit", "kkultemnote", "starpick", "stickers") and "," not in args[0] else ROOT / "out/check_bench_packs").resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    packs = args[0].split(",") if args else ["kitchit", "kkultemnote", "starpick", "stickers"]
    fails = []
    for p in packs:
        if p == "stickers":   # ⑦ 2단계 스티커
            def need(ok, msg):
                print(("  통과  " if ok else "★ 실패  ") + "[스티커] " + msg)
                if not ok: fails.append("[스티커] " + msg)
            tts = OUT / "v.wav"
            if not tts.exists():
                va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
            sticker_check(OUT, need, tts); continue
        if p not in PACKS:
            fails.append(f"계약 파일에 팩 {p} 없음"); print("★ 실패  계약 파일에 팩", p, "없음"); continue
        run(p, OUT, compose, fails)
    print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
    sys.exit(1 if fails else 0)
