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
  ⑩ (step4 안) 굿레터 팩: glPop 곡선·모든 조각 팝·줄 전체 색·큰 글·라벨 자리 / 자간·행간 3길
  ⑨ (step4) 범용 등장(관제 235 요청서 1~5): 키프레임·알파·이동 / 스냅샷 captionEnter / cps·글자 시각·커서·번짐 곡선 / 상자 투명도·모서리 / 퇴장 cut·fade·slide / 흔들림 + 캡컷·썸네일
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
# 스타픽룸 3D 재료 누끼(관제 235, 2026-10-19): 신라면 재료 영상(kitchit/sinramen/src)에서 rembg(u2net, 로컬)로 오린 PNG.
#   -o8gedIaYmA_5 1.6초 봉지 / Wy9--jw0ZsM_182 3.0초 참기름 병·계란판. 하이브리드는 자막표 sticker 에 이 경로를 src 로 싣는다.
STAR_OBJ = {k: BENCH / "starpickroom/hybrid_sungsikyung/stickers" / v for k, v in {"B2": "참기름.png", "B3": "계란.png", "B5": "신라면봉지.png"}.items()}


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
                   "want_hex": [e["hex"] for e in r.get("emph") or []], "variant": "", "sticker": "", "typing": bool(r.get("typing")),
                   "stickers": [{"kind": "object_pop", "src": str(STAR_OBJ[r["line"]]), "hold": "beat"}
                                for s_ in (r.get("sticker") or []) if isinstance(s_, dict) and s_.get("kind") == "sprObjectPop" and STAR_OBJ.get(r["line"], pathlib.Path("-")).exists()]}
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
                      "caption_marks": [{k: v for k, v in (("speaker", r["speaker"]), ("variant", r["variant"]), ("sticker", r["sticker"]), ("emph", r["emph"]), ("stickers", r.get("stickers")), ("place", r.get("place")), ("enter", r.get("enter"))) if v}
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
        want = [r["enter_pop"] or r["typing"] or bool(r.get("stickers")) for r in rows]; got = [bool(layers[i].get("enterMs")) for i in idx]   # 스티커 등장도 같은 장면 등장 길이에 든다
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
        if flash and (flash["color"].upper() in [h.upper() for h in rows[k]["want_hex"]] or rows[k].get("stickers")):
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
        want_y = None if pl is None else pl / 100 * 1920
        b = ink_box(still(k).crop((0, int(want_y - 62), 1080, int(want_y + 62)))) if want_y else None   # 자막 줄 ±62px 만(스티커 빼고)
        if b: b = (b[0], b[1] + int(want_y - 62), b[2], b[3] + int(want_y - 62))
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
    rows = [R("A", 0, 1.5, "보기만 해도 고급", stickers=[{"kind": "gem", "word": "고급"}]),
            R("B", 1.5, 3.0, "이렇게 똑", stickers=[{"kind": "spark_lines", "word": "똑"}]),
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
    BENCH_GEM_H, BENCH_FILL = 187, 69   # BRa 16.3 다이아 잉크 높이 / 키치잇 글자 채움 높이(우리 68)
    h_ratio = (b[3] - b[1]) / BENCH_GEM_H if b else 0
    need(bool(b) and .87 <= h_ratio <= 1.15 and b[0] >= cb[2] - (b[2] - b[0]) * .45 and b[0] <= cb[2] and abs(b[3] - cb[3]) <= 25,
         f"⑦ 💎 다이아: 상자 {b} 높이 {b and b[3] - b[1]}px = 벤치 {BENCH_GEM_H}px 의 {h_ratio:.2f}배 · 낱말 끝에 겹쳐 붙음(자막 흰 글자 {cb}) · 아래끝 맞춤")
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
    cb, _ = cbox(still(1).crop((0, 1290, 1080, 1360)), ["#FFFFFF"], 8); cb = (cb[0], cb[1] + 1290, cb[2], cb[3] + 1290)   # 글자 윗부분 띠만(선은 낱말 가운데 아래에서 시작)
    sp = lambda im: cbox(im.crop((cb[2] + 2, cb[1] - 20, 1080, 1700)), ["#FFFFFF"], 12)
    bb, _ = sp(still(1)); w_, h_ = (bb[2] - bb[0], bb[3] - bb[1]) if bb else (0, 0)
    a0, a2 = sp(frame(1, 0))[1], sp(frame(1, 2))[1]
    need(bool(bb) and abs(w_ / 217 - 1) <= .15 and abs(h_ / 153 - 1) <= .15 and a0 < max(1, a2) * .2,
         f"⑦ 강조선: 낱말 오른쪽 상자 {w_}×{h_}px = 벤치 Cs-Ka 10.2 217×153px ±15% · 첫 프레임 흰 점 {a0} → 2프레임 {a2}")
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
    need(bool(o6) and abs(o6[0] - (180 + 70 * 300 / 360)) <= 30 and o6[1] >= cap_abs(6)[3] and abs((o6[2] - o6[0]) - 160 * 300 / 360) <= 20 and max(ws) >= 1.04 and ws[1] < .8,
         f"⑦ 3D 재료: 병 상자 {o6}(그림 x180·폭≤280·높이≤300 → 견본 300×360 은 0.83배, 병 x≈238·폭≈133) · 팝 폭 비율 {ws}")
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
    # 시트: 벤치 · 우리를 **같은 배율·같은 칸**에(두 쪽 다 1080×1920 원본에서 같은 상자를 잘라 0.5배)
    PAIRS = [("💎 다이아", "kitchit/src/BRa5Iv4A3Y8.mp4", 16.3, 0, (200, 1100, 1000, 1500)),
             ("강조선", "kitchit/src/Cs-Ka_S8nDM.mp4", 10.2, 1, (150, 1150, 1050, 1550)),
             ("빨간 원+화살표", "kitchit/src/Cs-Ka_S8nDM.mp4", 0.5, 2, (100, 500, 1000, 1450)),
             ("ㅋㅋㅋ(벤치 프레임 없음)", None, 0, 3, (150, 1100, 1050, 1500)),
             ("댓글 카드", "kkultemnote/src/m0Ex0y1DN5s.mp4", 3.0, 4, (0, 1200, 1080, 1600)),
             ("3D 재료", "starpickroom/src/VbpdNba182M.mp4", 19.5, 6, (0, 1000, 1080, 1800))]
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    cells = []
    for title, rel, t, k, box in PAIRS:
        w, h = (box[2] - box[0]) // 2, (box[3] - box[1]) // 2
        if rel and (BENCH / rel).exists():
            va._run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", str(BENCH / rel), "-frames:v", "1", str(d / "_b.png")])
            bimg = Image.open(d / "_b.png").convert("RGB").resize((1080, 1920)).crop(box).resize((w, h))
        else:
            bimg = Image.new("RGB", (w, h), (30, 30, 30))
        bg = Image.new("RGBA", (1080, 1920), (70, 90, 110, 255)); bg.alpha_composite(still(k))
        cells.append((title, rel and f"{pathlib.Path(rel).stem} {t}초", bimg, bg.convert("RGB").crop(box).resize((w, h))))
    W = max(c[2].width for c in cells) * 2 + 30; H = sum(c[2].height + 34 for c in cells)
    sheet = Image.new("RGB", (W, H), (16, 18, 22)); dr = ImageDraw.Draw(sheet); y = 0
    for title, src_, b_, o_ in cells:
        dr.text((8, y + 5), f"{title} — 왼쪽 벤치({src_ or '-'}) · 오른쪽 우리 · 같은 배율(0.5)·같은 칸", fill=(240, 240, 240), font=font); y += 34
        sheet.paste(b_, (0, y)); sheet.paste(o_, (b_.width + 30, y)); y += b_.height
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


def _runs(im, box, want, gap=30, tol=30):
    """box 안에서 want 색 점들의 가로 덩어리 [(x0,x1,y0,y1)] — gap 보다 벌어지면 다른 덩어리."""
    px = im.load(); cols = {}
    for y in range(box[1], box[3], 2):
        for x in range(box[0], box[2], 2):
            c = px[x, y]
            if c[3] > 200 and all(abs(c[j] - want[j]) <= tol for j in range(3)):
                cols.setdefault(x, []).append(y)
    out = []
    for x in sorted(cols):
        if out and x - out[-1][1] <= gap:
            o = out[-1]; o[1] = x; o[2] = min(o[2], min(cols[x])); o[3] = max(o[3], max(cols[x]))
        else:
            out.append([x, x, min(cols[x]), max(cols[x])])
    return [tuple(o) for o in out if (o[1] - o[0]) > 6]


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def step3_check(out, need, tts):
    """⑧ 보강 3단계(관제 235) — 스타픽룸 글리치·오른쪽 닦기·무지개 / 자막 자리(place) / 하트 무리·효과음 글자·작은 글·만화 번쩍 /
    괄호 줄·이어 붙이기. 수치 = 벤치 프레임 실측(편·초는 계약 파일 bench 칸과 handoff/자막팩보강.md 표).
    ★벤치 수치는 전부 벤치 프레임 대비로 쟀다(우리 글자 대비 아님)."""
    d = out / "_step3"; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True, exist_ok=True)

    def build(pack, rows, tag):
        total = max(r["t1"] for r in rows)
        tl = rows_to_timeline(rows, tts, total); snap = snapshot(pack)
        ctx = scene_style.context_for(tl, {"text": "x"}, snap, None); idx = [i for i, s in enumerate(ctx["scenes"]) if s["caption"]]
        lay = scene_style.render_layers(tl, snap, d / tag, {"text": "x"}, "bench")
        return tl, snap, ctx, idx, lay, d / tag

    R = lambda line, t0, t1, text, **kw: {"line": line, "t0": t0, "t1": t1, "text": text, "speaker": "orig", "variant": "", "sticker": "", "emph": [], **kw}

    def frames_of(lay, L, k):
        a = lay[k].get("animation")
        return a, (lambda f: img(L / a["pattern"].replace("%04d", str(min(f, a["count"] - 1)).zfill(4))) if a else img(L / lay[k]["file"]))

    # ── 스타픽룸 세 가지 등장 + 줄 자리
    rows = [R("g", 0, 1.6, "땅콩버터에...", variant="glitch"), R("w", 1.6, 3.2, "가르쳐 드려요?", variant="wipe"),
            R("r", 3.2, 5.0, "최화정이 만들자마자", variant="rainbow"), R("p", 5.0, 6.5, "위치 옮기기", place={"y": 50, "x": 30})]
    tl, snap, ctx, idx, lay, L = build("starpick", rows, "star"); S1 = (lay, L, idx); B1 = (tl, snap, ctx)
    # rgbGlitch: 벤치 VbpdN 1.37~1.80초(0.43초) — 처음 0.1초 맨 글자 · 1.60~1.63 가장 벌어짐 · 1.80 끝
    a, fr = frames_of(lay, L, idx[0]); RED, CY = "#FF2D55", "#00B0FF"
    cnt = [cbox(fr(f), [RED], 40)[1] + cbox(fr(f), [CY], 40)[1] for f in range(16)]
    peak = max(cnt); hi = [f for f, c in enumerate(cnt) if c >= peak * .8]; pf = round(sum(hi) / len(hi)) if peak else -1   # 가장 벌어진 구간(80% 이상)의 가운데
    need(a is not None and peak > 300 and 6 <= pf <= 10 and max(cnt[:3]) <= peak * .1 and max(cnt[14:]) <= peak * .1,
         f"⑧ 글리치: 빨강·하늘 점 프레임별 {cnt} — 처음 3프레임 맨 글자 · 가장 벌어진 프레임 {pf}(벤치 6~10) · 14프레임부터 사라짐")
    sep = 0
    if peak:
        im = fr(pf); px = im.load(); xs = {RED: [], CY: []}
        for y in range(0, im.size[1], 2):
            for x in range(0, im.size[0], 2):
                c = px[x, y]
                if c[3] > 200:
                    for h in xs:
                        if all(abs(c[j] - _hex(h)[j]) <= 40 for j in range(3)): xs[h].append(x)
        sep = abs(sum(xs[RED]) / len(xs[RED]) - sum(xs[CY]) / len(xs[CY])) if xs[RED] and xs[CY] else 0
    need(peak > 0 and sep > 0, f"⑧ 글리치: 빨강 점이 하늘 점보다 왼쪽(가운데 차이 {sep:.1f}px — 빨강은 글자 왼 가장자리·하늘은 오른쪽에만 보이므로 양이 아니라 방향만)")
    stl = cbox(img(L / lay[idx[0]]["file"]), [RED, CY], 40)[1]
    need(stl == 0, f"⑧ 글리치: 정지 그림(캡컷·썸네일)에는 번짐 없음(점 {stl})")
    # wipeRTL: 오른쪽 끝부터 드러남 — 벤치 VbpdN 17.37~17.70(8자 0.33초) · EZQl 3.37~4.00(12자 0.63초) = 글자당 약 47ms
    a, fr = frames_of(lay, L, idx[1])
    wb = [ink_box(fr(f).crop((0, 1000, 1080, 1250)), 200) for f in range(16)]
    wd = [(b[2] - b[0]) if b else 0 for b in wb]; full = wd[-1] or 1
    rights = [b[2] for b in wb if b and b[2] - b[0] > full * .3] or [0]
    nfull = next((f for f, w_ in enumerate(wd) if w_ >= full * .98), 99)
    need(a is not None and wd[0] < full * .25 and max(rights) - min(rights) <= 10 and 9 <= nfull <= 13 and wd == sorted(wd),
         f"⑧ 오른쪽 닦기: 글 폭 비율 {[round(w_ / full, 2) for w_ in wd]} · 오른쪽 끝 고정(흔들림 {max(rights) - min(rights)}px) · 다 나옴 {nfull}프레임(8자×47ms=11프레임 ±2)")
    # rainbowCycle: 글자마다 파랑→노랑→흰→주황 돌림 250ms, 글자 번호만큼 위상 — 벤치 j5D 0.2~1.0초 글자 9개 실측(색 hex 는 중앙값)
    a, fr = frames_of(lay, L, idx[2]); COL = {"B": "#0795FC", "Y": "#FAED07", "W": "#FFFFFF", "O": "#FB5806"}

    def slice_color(im, k):
        b = ink_box(im.crop((0, 1000, 1080, 1250)), 200)
        if not b: return "?"
        w_ = (b[2] - b[0]) / 9; box = (int(b[0] + w_ * k), 1000 + b[1], int(b[0] + w_ * (k + 1)), 1000 + b[3])
        score = {c: sum((r[1] - r[0]) * (r[3] - r[2]) for r in _runs(im, box, _hex(COL[c]), 400, 24)) for c in COL}
        return max(score, key=score.get)

    seq0 = "".join(slice_color(fr(f), 0) for f in (0, 8, 16, 24)); seq1 = "".join(slice_color(fr(f), 1) for f in (0, 8, 16, 24))
    need(seq0 == "OBYW" and seq1 == "BYWO", f"⑧ 무지개: 첫 글자 0·0.27·0.53·0.8초 색 {seq0}(벤치 O→B→Y→W) · 둘째 글자 {seq1}(B→Y→W→O) — 250ms마다 · 글자 번호만큼 위상")
    st = img(L / lay[idx[2]]["file"]); s0, s1 = slice_color(st, 0), slice_color(st, 1)
    need(s0 == "O" and s1 == "B", f"⑧ 무지개: 정지 그림도 시작 색({s0}{s1}) — 캡컷·썸네일 = 렌더 첫 프레임")
    # 자막 자리 이동(caption_anchor): 줄마다 place{x,y}(%) — 벤치 키치잇 원음 타이핑 줄 y1300(기본 1351)
    pb = ink_box(img(L / lay[idx[3]]["file"]), 200)
    cx, cy = ((pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2) if pb else (0, 0)
    need(bool(pb) and abs(cx - 324) <= 30 and abs(cy - 960) <= 30, f"⑧ 줄 자리: place x30% y50% → 글 가운데 ({cx:.0f},{cy:.0f}) = (324,960) ±30")

    # ── 꿀템노트 스티커·줄 6종
    rows = [R("h", 0, 2.0, "너무 예쁘다!", stickers=[{"kind": "hearts", "x": 50, "y": 41}]),
            R("s", 2.0, 3.5, "엄청 맛있어", stickers=[{"kind": "sound_word", "text": "쿰", "x": 20.1, "y": 65.7, "r": -3}, {"kind": "sound_word", "text": "직", "x": 85.9, "y": 65.7, "r": 8}]),
            R("t", 3.5, 5.0, "지갑 열게 한 이유가 있다는데?", stickers=[{"kind": "small_text", "text": "WOW", "x": 72, "y": 55}]),
            R("b", 5.0, 6.0, "알고 보니 요즘", stickers=[{"kind": "comic_burst", "variant": "a"}]),
            R("c", 6.0, 7.0, "알고 보니 요즘", stickers=[{"kind": "comic_burst", "variant": "b"}]),
            R("a", 7.0, 9.0, "변신하는 식탁을 막 보여주면서", stickers=[{"kind": "aside_line", "text": "(난리가 났음)"}]),
            R("p", 9.0, 10.0, "되게 가벼워"), R("p", 10.0, 11.5, "되게 가벼워", stickers=[{"kind": "append_text", "text": "맞아!"}])]
    tl, snap, ctx, idx, lay, L = build("kkultemnote", rows, "kk"); S2 = (lay, L, idx); B2 = (tl, snap, ctx)
    still = lambda k: img(L / lay[idx[k]]["file"])
    # 하트 무리: 얼굴(50%,41%)에서 퍼짐 — 벤치 KCx 0.0~1.5초 하트 5~95% 가로 반폭 0.13초 165 · 0.27초 245 · 0.47초 325 · 0.87초 385px, 위 5% 끝 y 0.87초 440
    a, fr = frames_of(lay, L, idx[0]); HC = "#FF4D63"

    def hpts(im):
        px = im.load(); xs, ys = [], []
        for y in range(300, 1300, 2):
            for x in range(0, 1080, 2):
                c = px[x, y]
                if c[3] > 150 and all(abs(c[j] - _hex(HC)[j]) <= 28 for j in range(3)): xs.append(x); ys.append(y)
        return xs, ys

    half = {}
    for f, bench in ((4, 165), (8, 245), (14, 325), (26, 385)):
        sx = sorted(hpts(fr(f))[0]) if a else []
        half[f] = ((sx[int(len(sx) * .95)] - sx[int(len(sx) * .05)]) / 2 if len(sx) > 20 else 0, bench)
    ys26 = sorted(hpts(fr(26))[1]) if a else []
    top = ys26[int(len(ys26) * .05)] if len(ys26) > 20 else 0
    need(a is not None and all(abs(v / b_ - 1) <= .25 for v, b_ in half.values()) and abs(top - 440) <= 45,
         "⑧ 하트 무리: 가로 반폭 {프레임: (우리, 벤치)} " + str({k: (round(v[0]), v[1]) for k, v in half.items()}) + f" ±25% · 0.87초 위 5% 끝 y {top}(벤치 440 ±45)")
    # 효과음 글자: 빨강 #FD2628 + 흰 테 — 벤치 cLk 5.4~6.6초 쿰 192×227(중심 217,1265) · 직 172×233(중심 928,1259)
    im = still(1); rr = _runs(im, (0, 1000, 1080, 1500), (253, 38, 40), 120, 28)
    need(len(rr) == 2 and abs((rr[0][0] + rr[0][1]) / 2 - 217) <= 40 and abs((rr[1][0] + rr[1][1]) / 2 - 928) <= 40 and all(abs((r[3] - r[2]) / 230 - 1) <= .22 for r in rr),
         f"⑧ 효과음 글자 쿰·직: 덩어리 {rr} — 중심 x 217·928(±40) · 높이 ≈230(±22%) · 빨강 #FD2628")
    wr = cbox(im.crop((0, 1000, 1080, 1225)), ["#FFFFFF"], 8)[1]   # 자막 줄(y1244~) 위쪽 — 글자 윗부분 흰 테만
    need(wr > 250, f"⑧ 효과음 글자: 흰 테 점 {wr}(벤치 약 9px 테 — 자막 줄 위쪽 구간만)")
    # 작은 글 WOW: 노랑 글자 — 벤치 m0E 4.3~4.7초 폭 185 · 높이 55 · 가운데 (778,1058)
    im = still(2); ww = _runs(im, (0, 800, 1080, 1300), (255, 224, 0), 80, 40)
    w0 = max(ww, key=lambda r: r[1] - r[0]) if ww else None
    need(bool(w0) and abs((w0[1] - w0[0]) / 185 - 1) <= .25 and abs((w0[3] - w0[2]) / 55 - 1) <= .3 and abs((w0[0] + w0[1]) / 2 - 778) <= 40 and abs((w0[2] + w0[3]) / 2 - 1058) <= 40,
         f"⑧ 작은 글 WOW: {w0} — 폭 185·높이 55(±25~30%) · 가운데 (778,1058) ±40")
    # 만화 번쩍: 초록·주황 느낌표·별(a) / 빨강 느낌표·하늘 번개(b) — 벤치 j5D 6.9~7.3 · 9.3~9.9, 0.4초 안에 사라짐
    for k, name_, hexes in ((3, "a", ["#7ED321", "#F5A623"]), (4, "b", ["#E02020", "#4FC3F7"])):
        a, fr = frames_of(lay, L, idx[k]); capb = ink_box(still(k).crop((0, 1100, 1080, 1500)), 200)
        mid = [cbox(fr(f), hexes, 36)[1] for f in range(16)] if a else []
        bb = cbox(fr(5), hexes, 36)[0] if a else None
        need(a is not None and mid[5] > 150 and mid[-1] == 0 and bb is not None and capb is not None and bb[3] <= 1100 + capb[1] + 45,
             f"⑧ 만화 번쩍 {name_}: 색 점 프레임별 {mid} — 0.5초 안에 나왔다 사라짐 · 상자 {bb} 자막 위({capb and 1100 + capb[1]})")
    # 괄호 줄: 노랑 #FFDC06, 자막 가운데 −96px — 벤치 _dz 8.9~10.5초 가운데 y1190(자막 1286)
    ay = _runs(still(5), (0, 1000, 1080, 1250), (255, 220, 6), 120, 30)
    a0 = max(ay, key=lambda r: r[1] - r[0]) if ay else None
    need(bool(a0) and abs((a0[2] + a0[3]) / 2 - 1190) <= 20 and abs((a0[3] - a0[2]) / 69 - 1) <= .25 and abs((a0[1] - a0[0]) / 391 - 1) <= .25,
         f"⑧ 괄호 줄: {a0} — 가운데 y 1190 ±20 · 높이 69 · 폭 391(±25%)")
    # 이어 붙이기: 앞 글 제자리, 뒤 글 오른쪽에 61px 띄어 — 벤치 BpU 0.5→0.6초 '되게 가벼워' 226~574(높이65) · '맞아!' 635~844(높이110)
    r1 = _runs(still(6), (0, 1100, 1080, 1500), (255, 255, 255), 40, 12); r2 = _runs(still(7), (0, 1100, 1080, 1500), (255, 255, 255), 40, 12)
    need(len(r1) == 1 and len(r2) == 2 and abs(r1[0][0] - r2[0][0]) <= 3 and abs(r1[0][1] - r2[0][1]) <= 3 and 40 <= r2[1][0] - r2[0][1] <= 80
         and abs((r2[1][3] - r2[1][2]) / (r2[0][3] - r2[0][2]) - 110 / 65) <= .45,
         f"⑧ 이어 붙이기: 앞 {r1} → 뒤 {r2} — 앞 글 제자리(±3px) · 틈 61px(40~80) · 뒤 글 높이/앞 글 높이 = 벤치 110/65")
    # ── 캡컷 그림·썸네일 — 정지 그림과 같아야 한다(렌더 길 ② 캡컷 overlay_spans · ③ 썸네일 render_layer_one)
    for tag, S, B, ks in (("star", S1, B1, (0, 1, 2, 3)), ("kk", S2, B2, (0, 1, 2, 3, 4, 5, 7))):
        lay_, L_, idx_ = S; tl_, snap_, ctx_ = B
        spans = scene_style.overlay_spans(ctx_["scenes"], lay_, L_); bad = []
        for k in ks:
            sc = ctx_["scenes"][idx_[k]]; sp = [x for x in spans if sc["start"] - 1e-6 <= x["start"] < sc["end"] - 1e-6]
            st = img(L_ / lay_[idx_[k]]["file"])
            if not sp or alpha_sum(img(sp[-1]["path"])) < alpha_sum(st) * .97 or hard_diff(img(sp[-1]["path"]), st) > 30: bad.append(k)
        need(not bad, f"⑧ 캡컷 그림({tag}) = 다 나온 자막+스티커 정지 그림(어긋남 장면 {bad})")
        badt = []
        for k in ks:
            p = scene_style.render_layer_one(tl_, snap_, d / f"t_{tag}{k}", idx_[k], {"text": "x"}, "bench")
            if hard_diff(img(p), img(L_ / lay_[idx_[k]]["file"])) + hard_diff(img(L_ / lay_[idx_[k]]["file"]), img(p)) != 0: badt.append(k)
        need(not badt, f"⑧ 썸네일({tag}) = 정지 그림(어긋남 장면 {badt})")
    # ── 시트: 벤치 프레임 · 우리 프레임을 같은 상자 크기·같은 배율(0.5)로 나란히
    def ours(S, k, f=None):
        lay_, L_, idx_ = S; im = frames_of(lay_, L_, idx_[k])[1](f) if f is not None else img(L_ / lay_[idx_[k]]["file"])
        bg = Image.new("RGBA", (1080, 1920), (70, 90, 110, 255)); bg.alpha_composite(im); return bg.convert("RGB")
    PAIRS = [("RGB 글리치", "starpickroom/src/VbpdNba182M.mp4", 1.60, (200, 1040, 880, 1240), ours(S1, 0, 8), (200, 1040, 880, 1240)),
             ("오른쪽 닦기(0.17초 지점)", "starpickroom/src/VbpdNba182M.mp4", 17.50, (200, 1040, 880, 1240), ours(S1, 1, 5), (200, 1040, 880, 1240)),
             ("무지개 돌림 0초", "starpickroom/src/j5D30T2n0-w.mp4", 0.30, (150, 1040, 930, 1240), ours(S1, 2, 0), (150, 1040, 930, 1240)),
             ("무지개 돌림 0.27초", "starpickroom/src/j5D30T2n0-w.mp4", 0.57, (150, 1040, 930, 1240), ours(S1, 2, 8), (150, 1040, 930, 1240)),
             ("하트 무리 0.47초", "kkultemnote/src/KCxJ5qJft38.mp4", 0.47, (0, 300, 1080, 1250), ours(S2, 0, 14), (0, 300, 1080, 1250)),
             ("효과음 글자 쿰·직", "kkultemnote/src/cLk6fJly6OY.mp4", 6.0, (0, 1050, 1080, 1450), ours(S2, 1), (0, 1050, 1080, 1450)),
             ("작은 글 WOW", "kkultemnote/src/m0Ex0y1DN5s.mp4", 4.5, (300, 900, 1080, 1250), ours(S2, 2), (300, 900, 1080, 1250)),
             ("만화 번쩍 a", "starpickroom/src/j5D30T2n0-w.mp4", 7.00, (150, 950, 930, 1250), ours(S2, 3, 6), (150, 1050, 930, 1350)),
             ("만화 번쩍 b", "starpickroom/src/j5D30T2n0-w.mp4", 9.40, (150, 950, 930, 1250), ours(S2, 4, 6), (150, 1050, 930, 1350)),
             ("괄호 줄", "kkultemnote/src/_dzncUms1yQ.mp4", 9.50, (0, 1100, 1080, 1400), ours(S2, 5), (0, 1100, 1080, 1400)),
             ("이어 붙이기", "kkultemnote/src/BpUOIUwkoG4.mp4", 0.70, (0, 1150, 1080, 1400), ours(S2, 7), (0, 1150, 1080, 1400))]
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    cells = []
    for title, rel, t, bbox, o_im, obox in PAIRS:
        w, h = (bbox[2] - bbox[0]) // 2, (bbox[3] - bbox[1]) // 2
        va._run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", str(BENCH / rel), "-frames:v", "1", str(d / "_b.png")])
        bimg = Image.open(d / "_b.png").convert("RGB").resize((1080, 1920)).crop(bbox).resize((w, h))
        cells.append((title, f"{pathlib.Path(rel).stem} {t}초", bimg, o_im.crop(obox).resize((w, h))))
    W = max(c[2].width for c in cells) * 2 + 30; H = sum(c[2].height + 34 for c in cells)
    sheet = Image.new("RGB", (W, H), (16, 18, 22)); dr = ImageDraw.Draw(sheet); y = 0
    for title, src_, b_, o_ in cells:
        dr.text((8, y + 5), f"{title} — 왼쪽 벤치({src_}) · 오른쪽 우리 · 같은 배율(0.5)·같은 칸", fill=(240, 240, 240), font=font); y += 34
        sheet.paste(b_, (0, y)); sheet.paste(o_, (b_.width + 30, y)); y += b_.height
    sheet.save(out / "step3_시트.jpg", quality=88); print(f"  시트 {out / 'step3_시트.jpg'}")
    return d


# ── ⑨ 범용 등장(관제 235, 칼카피 요청서 §4-2 1·2·4·5) ─────────────────────────────────────────────────────────────────
# 벤치 수치가 있는 것: 키치잇 팝 키프레임(요청서 1: 0f 0%·1f 22%·…·13f 100%, 30fps) · 스타픽룸 타이핑 cps 10~15·커서 400ms 깜빡·번짐 0.3초(요청서 2).
# 벤치 수치가 없는 것(요청서에 수치 없음): 퇴장 cut/fade/slide(벤치는 전부 컷) · 흔들림 · 상자 투명도·모서리 — 입력 인자대로 나오는지만 잰다.
KITCHIT_POP = [(0, 0), (1, 22), (2, 42), (3, 59), (4, 75), (5, 88), (6, 97), (7, 105), (8, 109), (9, 109), (10, 105), (11, 102), (13, 100)]   # (프레임, 크기%) — 요청서 1 견본, 30fps


def patched_packs(patch):
    """계약 파일의 PACKS 에 시험용 값을 잠깐 덮고(상자 인자 — 실제 팩엔 벤치 상자가 없다) 끝나면 바이트 그대로 되돌린다."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        path = ROOT / "shopping_shorts/static/caption-motions.js"; raw = path.read_bytes(); text = raw.decode("utf-8")
        head, body, tail = text.split("/*PACKS*/")
        packs = json.loads(body)
        for k, v in patch.items():
            packs[k].update(v)
        try:
            path.write_bytes((head + "/*PACKS*/" + json.dumps(packs, ensure_ascii=False) + "/*PACKS*/" + tail).encode("utf-8"))
            yield
        finally:
            path.write_bytes(raw)
    return cm()


def step4_check(out, need, tts):
    d = out / "_step4"; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True, exist_ok=True)
    R = lambda line, t0, t1, text, **kw: {"line": line, "t0": t0, "t1": t1, "text": text, "speaker": "orig", "variant": "", "sticker": "", "emph": [], **kw}

    def build(pack, rows, tag, extra=None):
        total = max(r["t1"] for r in rows)
        tl = rows_to_timeline(rows, tts, total); snap = snapshot(pack)
        if extra:
            snap = scene_style.validate_snapshot({**snap, **extra})
        ctx = scene_style.context_for(tl, {"text": "x"}, snap, None); idx = [i for i, s in enumerate(ctx["scenes"]) if s["caption"]]
        lay = scene_style.render_layers(tl, snap, d / tag, {"text": "x"}, "bench")
        return tl, snap, ctx, idx, lay, d / tag

    def fr(S, k):
        lay, L, idx = S; a = lay[idx[k]].get("animation")
        still = img(L / lay[idx[k]]["file"])
        return a, (lambda f: img(L / a["pattern"].replace("%04d", str(min(f, a["count"] - 1)).zfill(4))) if a else still), still

    def bw(im):
        b = ink_box(im, 200); return (b[2] - b[0]) if b else 0

    def cx_(im, a=200):
        b = ink_box(im, a); return (b[0] + b[2]) / 2 if b else None

    # ── 서버가 스펙을 정리하는 한 곳(clean_caption_enter) — 범위 밖·모르는 이름은 버린다 / 스냅샷은 거절
    badspecs = [{"kind": "nope"}, {"kind": "pop", "ms": 99999}, {"keyframes": [{"t": 0, "alpha": 300}]}, {"keyframes": []}, {"cps": 0, "kind": "pop"},
                {"kind": "typeGlow", "cursor": {"char": "abc"}}, {"kind": "pop", "exit": {"kind": "spin"}}, {}, "pop"]
    got = [scene_style.clean_caption_enter(b) for b in badspecs]
    need(all(g is None for g in got), f"⑨ 스펙 정리: 범위 밖·모르는 값은 버림(통과한 번호 {[i for i, g in enumerate(got) if g is not None]} — 비어야 함)")
    try:
        scene_style.validate_snapshot({**snapshot("kitchit"), "captionEnter": {"kind": "pop", "ms": 99999}}); rej = False
    except ValueError:
        rej = True
    need(rej, "⑨ 스펙 정리: 스냅샷 captionEnter 가 범위 밖이면 거절")

    # ── 계약 파일 변환기(captionEnterMotion) = 요청서 키프레임 그대로(offset = 프레임/13, scale = %/100)
    js = ("global.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));"
          "const kf=JSON.parse(process.argv[2]);const m=window.captionEnterMotion({keyframes:kf},window.CAPTION_MOTIONS);console.log(JSON.stringify(m))")
    spec_kf = [{"t": round(f / 30, 4), "scale": sc} for f, sc in KITCHIT_POP]
    r_ = subprocess.run(["node", "-e", js, str(ROOT / "shopping_shorts/static/caption-motions.js"), json.dumps(spec_kf)], capture_output=True, text=True, encoding="utf-8")
    try:
        m = json.loads(r_.stdout)
        sc_ = [float(f["scale"]) for f in m["frames"]]; off = [f["offset"] for f in m["frames"]]
        ok = (len(sc_) == len(KITCHIT_POP) and all(abs(a - b / 100) < 1e-6 for a, (_, b) in zip(sc_, KITCHIT_POP))
              and all(abs(o - f / 13) < .01 for o, (f, _) in zip(off, KITCHIT_POP)) and abs(m["ms"] - 433) <= 1 and m["frames"][-1]["opacity"] == 1)
    except Exception:
        ok = False
    need(ok, f"⑨ 변환: 요청서 팝 키프레임 13개 → 모션 프레임(크기·offset=f/13·길이 433ms ±1·끝=제자리) {r_.stderr[:80]}")

    # ── 렌더 1: 키프레임·알파/이동·cps·글자 시각·커서·번짐·흔들림·퇴장
    rows = [R("a", 0, 1.2, "1년 내내", enter={"keyframes": spec_kf}),
            R("b", 1.2, 2.4, "알파 이동", enter={"keyframes": [{"t": 0, "alpha": 50, "dy": 60}, {"t": .2, "alpha": 100, "dy": 0}]}),
            R("c", 2.4, 4.4, "가나다라마바", enter={"kind": "typeGlow", "cps": 10, "glow": {"decay_ms": 300}}),
            R("d", 4.4, 6.4, "가나다라마바", enter={"kind": "typeGlow", "cps": 10}, chars=[round(4.4 + k * .3, 3) for k in range(6)]),
            R("e", 6.4, 8.4, "가나다라마바", enter={"kind": "typeCursor", "cps": 10, "cursor": {"char": "|", "blink_ms": 300}}),
            R("f", 8.4, 10.4, "흔들림 하나", enter={"kind": "shake"}),
            R("g", 10.4, 12.4, "흔들림 둘", enter={"kind": "shake", "amp": 2}),
            R("h", 12.4, 14.4, "퇴장 컷", enter={"kind": "none", "exit": {"kind": "cut"}}),
            R("i", 14.4, 16.4, "퇴장 페이드", enter={"kind": "none", "exit": {"kind": "fade", "ms": 300}}),
            R("j", 16.4, 18.4, "퇴장 밀기", enter={"kind": "none", "exit": {"kind": "slide", "ms": 300, "dx": -400}}),
            R("k", 18.4, 19.6, "기본 팩 등장")]
    tl, snap, ctx, idx, lay, L = build("kitchit", rows, "kit"); S = (lay, L, idx)
    # 1) 키프레임 크기 곡선 = 요청서 ±5%p, 길이
    a, f_, still = fr(S, 0); full = bw(still) or 1
    bad = []
    for fno, pct in KITCHIT_POP:
        w = bw(f_(fno)) / full * 100
        if abs(w - pct) > 5: bad.append((fno, pct, round(w)))
    need(a is not None and not bad and lay[idx[0]].get("enterMs") in range(430, 440), f"⑨ 키프레임 등장: 잉크 폭 곡선 = 요청서(13프레임) ±5%p · 길이 {lay[idx[0]].get('enterMs')}ms(433) · 어긋남 {bad}")
    # 2) 알파·이동
    a, f_, still = fr(S, 1); sa = alpha_sum(still); r0 = alpha_sum(f_(0)) / sa; c0 = ink_box(f_(0), 60); cs = ink_box(still, 60)
    dy = (c0[1] - cs[1]) if c0 and cs else 999
    need(a is not None and abs(r0 - .5) <= .08 and abs(dy - 60) <= 4 and alpha_sum(f_(a["count"] - 1)) >= sa * .98,
         f"⑨ 알파·이동: 첫 프레임 투명도 {r0:.2f}(0.5 ±0.08) · 아래로 {dy}px(60 ±4) · 끝 = 정지 그림")
    # 3) cps(글자·어절 시각이 없을 때 기본 속도) — 6글자, 10글자/초: 0.27초 3글자(0.5) · 0.4초 5글자(0.83). 기본 간격(80ms)이면 4글자(.67)·6글자(1.0)
    a, f_, still = fr(S, 2); full = bw(still) or 1; w8, w12 = bw(f_(8)) / full, bw(f_(12)) / full
    need(a is not None and abs(w8 - .5) <= .07 and abs(w12 - .83) <= .07, f"⑨ 타이핑 cps=10: 0.27초 글 폭 {w8:.2f}(0.50 ±.07) · 0.4초 {w12:.2f}(0.83 ±.07)")
    # 3b) 글자 시각이 있으면 그것이 이긴다(0.3초마다 한 글자 → 0.27초 1글자 .17 · 0.5초 2글자 .33 — cps 10 이면 이미 6글자)
    a, f_, still = fr(S, 3); full = bw(still) or 1; w8, w15 = bw(f_(8)) / full, bw(f_(15)) / full
    need(a is not None and w8 <= .32 and .3 <= w15 <= .5, f"⑨ 글자 시각 > cps: 0.27초 {w8:.2f}(1글자 ≤.32) · 0.5초 {w15:.2f}(2글자 .30~.50) — cps 10 이면 이미 0.5/0.9 이상이라 구별됨")
    # 4) 번짐 시간 곡선: 마지막 글자(0.5초) 뒤 0.1초 = 가장 짙음(알파 합이 정지 그림보다 큼) · 번짐 끝난 뒤 = 정지 그림과 같음
    a, f_, still = fr(S, 2); sa = alpha_sum(still); peak = max(alpha_sum(f_(f)) / sa for f in range(15, 22)); late = alpha_sum(f_(34)) / sa
    need(a is not None and peak >= 1.03 and abs(late - 1) <= .02, f"⑨ 번짐 곡선(0.3초): 마지막 글자 뒤 번짐 최대 {peak:.3f}배(≥1.03) · 번짐 끝난 뒤 {late:.3f}배(1.00 ±.02)")
    # 5) 커서: 글자 '|' · 300ms 깜빡(보임 300 · 숨김 300) — 0.73초 보임 · 1.03초 숨김 · 1.33초 보임
    a, f_, still = fr(S, 4)
    r_ = [(ink_box(f_(f), 200) or (0, 0, 0, 0))[2] for f in (22, 31, 40)]
    need(a is not None and r_[0] - r_[1] >= 6 and abs(r_[2] - r_[0]) <= 3, f"⑨ 커서 '|' 깜빡 300ms: 글 오른쪽 끝 0.73초 {r_[0]} · 1.03초 {r_[1]}(숨김) · 1.33초 {r_[2]} — 보임>숨김 6px↑ · 다시 보임")
    # 6) 흔들림: 끝은 제자리 · amp 2 는 amp 1 의 2배 안팎
    pk = []
    for k in (5, 6):
        a, f_, still = fr(S, k); c_s = cx_(still)
        xs = [abs((cx_(f_(f)) or c_s) - c_s) for f in range(0, 12)]
        pk.append((max(xs), abs((cx_(f_(a["count"] - 1)) or c_s) - c_s)))
    need(pk[0][0] >= 4 and 1.6 <= pk[1][0] / max(pk[0][0], 1e-6) <= 2.4 and max(pk[0][1], pk[1][1]) <= 1.0,
         f"⑨ 흔들림: 최대 이동 amp1 {pk[0][0]:.1f}px · amp2 {pk[1][0]:.1f}px(2배 ±.4) · 끝 제자리 {pk[0][1]:.1f}/{pk[1][1]:.1f}px")
    # 7) 퇴장: 컷 = 마지막 프레임도 다 나온 자막 / 페이드·밀기 = 장면 끝 300ms 동안 선형(투명도 1-p · 이동 dx×p) — p = (프레임 시각 − (길이−300))/300
    def prog(k, f):
        sc = ctx["scenes"][idx[k]]; dur = (sc["end"] - sc["start"]) * 1000
        return max(0.0, min(1.0, (f / 30 * 1000 - (dur - 300)) / 300))
    a, f_, still = fr(S, 7); sa = alpha_sum(still)
    need(a is not None and alpha_sum(f_(a["count"] - 1)) >= sa * .98, f"⑨ 퇴장 cut: 마지막 프레임 = 다 나온 자막({alpha_sum(f_(a['count'] - 1)) / sa:.2f})")
    a, f_, still = fr(S, 8); sa = alpha_sum(still); n_ = a["count"] if a else 0
    got_ = [(f, alpha_sum(f_(f)) / sa, 1 - prog(8, f)) for f in (n_ - 1, n_ - 5, n_ - 10, n_ - 15, 5)] if a else []
    need(a is not None and n_ >= 55 and all(abs(g - e) <= .08 for _, g, e in got_) and sa > 1000,
         f"⑨ 퇴장 fade 300ms: 프레임별 투명도(우리, 기대) {[(f, round(g, 2), round(e, 2)) for f, g, e in got_]} ±.08 · 정지 그림은 다 나옴(알파 합 {sa})")
    a, f_, still = fr(S, 9); n_ = a["count"] if a else 0; c_s = cx_(still, 30)
    sl = [(f, (cx_(f_(f), 30) or c_s) - c_s, -400 * prog(9, f)) for f in (n_ - 5, n_ - 10, 5)] if a else []
    need(a is not None and all(abs(g - e) <= 25 for _, g, e in sl) and alpha_sum(still) > 1000,
         f"⑨ 퇴장 slide 300ms dx-400: 프레임별 이동(우리, 기대 px) {[(f, round(g), round(e)) for f, g, e in sl]} ±25 · 정지 그림은 다 나옴")
    # 8) 스펙 없는 줄은 종전 팩 등장 그대로
    a, f_, still = fr(S, 10)
    need(a is not None and a["count"] >= 10, "⑨ 스펙 없는 줄은 종전 팩 등장 그대로(애니메이션 프레임 있음)")

    # ── 렌더 2: 스냅샷 captionEnter(팩 없음) — 칼카피 설명서의 등장 길이·키프레임이 스냅샷까지 간다
    rows2 = [R("a", 0, 1.5, "스냅샷 등장"), R("b", 1.5, 3.0, "두번째")]
    tl2, snap2, ctx2, idx2, lay2, L2 = build("", rows2, "snap", {"captionEnter": {"keyframes": [{"t": 0, "alpha": 20}, {"t": .5, "alpha": 100}]}}); S2 = (lay2, L2, idx2)
    a, f_, still = fr(S2, 0); r0 = alpha_sum(f_(0)) / max(1, alpha_sum(still))
    need(a is not None and lay2[idx2[0]].get("enterMs") in range(495, 506) and abs(r0 - .2) <= .06 and bool(snap2.get("captionEnter", {}).get("keyframes")),
         f"⑨ 스냅샷 captionEnter: 길이 {lay2[idx2[0]].get('enterMs')}ms(500) · 첫 프레임 투명도 {r0:.2f}(0.20 ±.06)")
    tl3, snap3, ctx3, idx3, lay3, L3 = build("", rows2, "snap0"); need(not lay3[idx3[0]].get("animation"), "⑨ 스냅샷 captionEnter 없으면 등장 없음(종전)")

    # ── 렌더 3: 상자 투명도·둥근 모서리(팩 box) — 시험용 팩 값(실제 팩엔 벤치 상자가 없다)
    rows4 = [R("a", 0, 1.0, "상자 시험")]
    with patched_packs({"kitchit": {"box": {"color": "#102030", "alpha": 40, "radius": 30}}}):
        _, _, _, idx4, lay4, L4 = build("kitchit", rows4, "box")
    with patched_packs({"kitchit": {"box": {"color": "#102030", "alpha": 100, "radius": 0}}}):
        _, _, _, idx5, lay5, L5 = build("kitchit", rows4, "box0")
    _, _, _, idx6, lay6, L6 = build("kitchit", rows4, "box_none")
    def ytop(im, x, lo):   # 열 x 에서 알파가 lo 이상인 첫 y(위에서부터)
        al = im.split()[3]
        return next((y for y in range(1200, 1450) if al.getpixel((x, y)) >= lo), None)
    b_im = img(L4 / lay4[idx4[0]]["file"]); sq = img(L5 / lay5[idx5[0]]["file"])
    mid_ = b_im.getpixel((300, ytop(b_im, 300, 95) + 8)) if ytop(b_im, 300, 95) else (0, 0, 0, 0)
    t_edge, t_mid = ytop(b_im, 3, 95), ytop(b_im, 200, 95); q_edge, q_mid = ytop(sq, 3, 250), ytop(sq, 200, 250)
    none_a = img(L6 / lay6[idx6[0]]["file"]).getpixel((540, 20))[3]
    need(t_edge is not None and t_mid is not None and abs(mid_[3] - 102) <= 6 and all(abs(mid_[i] - c) <= 8 for i, c in enumerate((16, 32, 48))) and t_edge - t_mid >= 14,
         f"⑨ 자막 상자(alpha 40%·radius 30px): 안쪽 {mid_}(알파 102 ±6 · 색 #102030) · 왼쪽 끝 열이 가운데 열보다 {None if t_edge is None else t_edge - t_mid}px 아래서 시작(원 반지름 30 → x=3 에서 약 17 · ≥14 = 둥글게 깎임)")
    need(q_edge is not None and q_edge == q_mid and none_a == 0, f"⑨ 자막 상자 radius 0·alpha 100%: 왼쪽 끝 열 {q_edge} = 가운데 열 {q_mid}(각진 상자) · 상자 없는 팩은 투명(알파 {none_a})")

    # ── 자간·행간(팩 text.style.letterSpacing·lineHeight) — 값을 바꾸면 그림이 실제로 달라지고 세 길(렌더·캡컷·썸네일)이 같은 그림
    def spaced(tag, text, style):
        base = PACKS["kitchit"]["text"]
        with patched_packs({"kitchit": {"text": {**base, "style": {**base.get("style", {}), **style}}}}):
            tl_, sn_, cx_s, ix_, ly_, L_s = build("kitchit", [R("a", 0, 1.0, text)], tag)
            th = img(scene_style.render_layer_one(tl_, sn_, d / (tag + "_t"), ix_[0], {"text": "x"}, "bench"))   # 썸네일도 같은 팩 값으로(with 안)
        im = img(L_s / ly_[ix_[0]]["file"])
        sp_ = scene_style.overlay_spans(cx_s["scenes"], ly_, L_s); cap_ = img(sp_[-1]["path"]) if sp_ else None
        return im, ink_box(im, 200), (hard_diff(th, im) + hard_diff(im, th), (hard_diff(cap_, im) if cap_ else 999))
    LONG = "이것은 아주 길어서 한 줄에 다 들어가지 않을 정도로 매우매우 긴 자막 문장입니다 그래서 두 줄로 나뉩니다"
    _, b0, r0_ = spaced("ls0", "짧은 글", {"letterSpacing": "0em"}); _, b1, r1_ = spaced("ls1", "짧은 글", {"letterSpacing": "0.3em"})
    w0, w1 = b0[2] - b0[0], b1[2] - b1[0]
    need(w1 >= w0 * 1.15 and r0_ == (0, 0) or w1 >= w0 * 1.15 and r1_[0] == 0 and r1_[1] <= 30,
         f"⑨ 자간: letterSpacing 0em→0.3em 잉크 폭 {w0}→{w1}px(+15%↑) · 썸네일=렌더 그림 차이 {r1_[0]} · 캡컷 그림 차이 {r1_[1]}")
    _, h1, q1 = spaced("lh1", LONG, {"lineHeight": "1"}); _, h2, q2 = spaced("lh2", LONG, {"lineHeight": "2"})
    need(h2[3] - h2[1] >= (h1[3] - h1[1]) + 25 and q2[0] == 0 and q2[1] <= 30,
         f"⑨ 행간: lineHeight 1→2 잉크 높이 {h1[3] - h1[1]}→{h2[3] - h2[1]}px(+25↑) · 썸네일=렌더 차이 {q2[0]} · 캡컷 그림 차이 {q2[1]}")

    # ── 굿레터 팩(관제 235, 칼카피 굿레터 보강안 ed56bd44c): glPop 빠른 톡(28%→110%@0.1초→100%@0.175초) · 줄 전체 한 색 · 큰 글 · 라벨 자리
    #   벤치(굿레터 60fps 실측): 753r 27→110%(0.117초)→100%(0.183초) · vcb 26%→110%@0.100→100%@0.167 · 자리 y68.75%(sMx9 잉크 y1288~1353) · 라벨 y65%
    curve_ms = lambda t: curve("glPop", t)
    peak_v = max(curve_ms(t) for t in range(100, 126, 5))
    need(abs(curve_ms(0) - .28) <= .02 and 1.08 <= peak_v <= 1.12 and abs(curve_ms(175) - 1) <= .01 and abs(MOTIONS["glPop"]["ms"] - 175) <= 8,
         f"⑩ glPop 곡선(벤치): 시작 {curve_ms(0) * 100:.0f}%(26~28) · 0.10~0.125초 최대 {peak_v * 100:.0f}%(108~112) · 0.175초 {curve_ms(175) * 100:.0f}%(100) · 길이 {MOTIONS['glPop']['ms']}ms(167~183)")
    grows = [R("a", 0, 1.2, "굿레터 시험"), R("b", 1.2, 2.0, "앞 조각"), R("b", 2.0, 2.8, "뒤 조각"), R("c", 2.8, 4.0, "호박색 줄", variant="hi"),
             R("d", 4.0, 5.2, "계란 2개", variant="big"), R("e", 5.2, 6.4, "제품 이름", variant="label")]
    tlg, snapg, ctxg, idxg, layg, Lg = build("goodletter", grows, "gl"); SG = (layg, Lg, idxg)
    a, f_, still = fr(SG, 0); full = bw(still) or 1
    bad = [(f, round(bw(f_(f)) / full * 100), round(curve_ms(f / 30 * 1000) * 100)) for f in range(0, 7) if abs(bw(f_(f)) / full - (curve_ms(f / 30 * 1000) if f / 30 * 1000 < 175 else 1)) > .06]
    need(a is not None and not bad and layg[idxg[0]].get("enterMs") in range(170, 181), f"⑩ glPop 렌더: 30fps 잉크 폭 곡선 = 계약 곡선 ±6%p(어긋남 {bad}) · 길이 {layg[idxg[0]].get('enterMs')}ms(175) · 첫 프레임 불투명")
    a1, _, _ = fr(SG, 1); a2, _, _ = fr(SG, 2)
    need(a1 is not None and a2 is not None and layg[idxg[1]].get("enterMs") in range(170, 181) and layg[idxg[2]].get("enterMs") in range(170, 181),
         f"⑩ 모든 조각에 빠른 톡: 줄 앞 조각 {layg[idxg[1]].get('enterMs')}ms · 같은 줄 뒤 조각 {layg[idxg[2]].get('enterMs')}ms (kitchit 은 줄 첫 조각만)")
    # 줄 전체 한 색(호박 #FCB53F) — 채움(검정 테 제외) 색 점 중 호박 비율
    def fill_ratio(im, hex_):
        want = _hex(hex_); n = m_ = 0
        for px in im.get_flattened_data():
            if px[3] > 200 and max(px[:3]) > 90:
                n += 1; m_ += all(abs(px[i] - want[i]) <= 16 for i in range(3))
        return m_ / max(n, 1)
    _, _, st_h = fr(SG, 3); _, _, st_w = fr(SG, 0)
    rh, rw = fill_ratio(st_h, "#FCB53F"), fill_ratio(st_w, "#FCB53F")
    need(rh >= .8 and rw <= .02, f"⑩ 줄 전체 한 색 hi: 호박 #FCB53F 채움 비율 {rh:.2f}(≥0.8 = 줄 전체) · 보통 줄 {rw:.2f}(≤0.02)")
    _, _, st_big = fr(SG, 4); bb, bn = ink_box(st_big, 200), ink_box(st_w, 200)
    ab, _, _ = fr(SG, 4)
    need(ab is None and 1.9 <= (bb[3] - bb[1]) / (bn[3] - bn[1]) <= 2.7, f"⑩ 큰 글 big: 잉크 높이 {(bb[3] - bb[1])}px = 보통 줄의 {(bb[3] - bb[1]) / (bn[3] - bn[1]):.2f}배(벤치 약 2.3배) · 등장 없음({ab is None})")
    _, _, st_lab = fr(SG, 5); lb, al = ink_box(st_lab, 200), fr(SG, 5)[0]
    cy_l, cy_n = (lb[1] + lb[3]) / 2, (bn[1] + bn[3]) / 2
    need(al is None and abs(cy_l - .65 * 1920) <= 30 and abs(cy_n - .6875 * 1920) <= 30, f"⑩ 자리: 라벨 가운데 y {cy_l:.0f}(y65%=1248 ±30) · 보통 줄 {cy_n:.0f}(y68.75%=1320 ±30) · 라벨 등장 없음({al is None})")
    spg = scene_style.overlay_spans(ctxg["scenes"], layg, Lg); badg = []
    for k in range(6):
        sc = ctxg["scenes"][idxg[k]]; sp = [x for x in spg if sc["start"] - 1e-6 <= x["start"] < sc["end"] - 1e-6]
        st = img(Lg / layg[idxg[k]]["file"]); th = img(scene_style.render_layer_one(tlg, snapg, d / f"gt{k}", idxg[k], {"text": "x"}, "bench"))
        if not sp or hard_diff(img(sp[-1]["path"]), st) > 30 or hard_diff(th, st) + hard_diff(st, th) != 0: badg.append(k)
    need(not badg, f"⑩ 굿레터 캡컷 그림·썸네일 = 다 나온 정지 그림(어긋남 {badg})")

    # ── 세 길: 캡컷 그림(overlay_spans)·썸네일(render_layer_one) = 다 나온 정지 그림(퇴장·등장 도중이 아님)
    lay_, L_, idx_ = S; badc, badt = [], []
    spans = scene_style.overlay_spans(ctx["scenes"], lay_, L_)
    for k in range(10):
        sc = ctx["scenes"][idx_[k]]; sp = [x for x in spans if sc["start"] - 1e-6 <= x["start"] < sc["end"] - 1e-6]
        st = img(L_ / lay_[idx_[k]]["file"])
        if not sp or alpha_sum(img(sp[-1]["path"])) < alpha_sum(st) * .97 or hard_diff(img(sp[-1]["path"]), st) > 30: badc.append(k)
        if alpha_sum(st) < 1000: badc.append(f"빈 정지 그림{k}")
        p = scene_style.render_layer_one(tl, snap, d / f"t{k}", idx_[k], {"text": "x"}, "bench")
        if hard_diff(img(p), st) + hard_diff(st, img(p)) != 0: badt.append(k)
    need(not badc, f"⑨ 캡컷 그림 = 다 나온 자막 정지 그림(키프레임·타이핑·흔들림·퇴장 10장면, 어긋남 {badc})")
    need(not badt, f"⑨ 썸네일 = 정지 그림(어긋남 {badt})")


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
    OUT = pathlib.Path(args.pop(0) if args and not args[0] in ("kitchit", "kkultemnote", "starpick", "stickers", "step3", "step4") and "," not in args[0] else ROOT / "out/check_bench_packs").resolve()
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
        if p == "step3":   # ⑧ 보강 3단계
            def need(ok, msg):
                print(("  통과  " if ok else "★ 실패  ") + "[3단계] " + msg)
                if not ok: fails.append("[3단계] " + msg)
            tts = OUT / "v.wav"
            if not tts.exists():
                va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
            step3_check(OUT, need, tts); continue
        if p == "step4":   # ⑨ 범용 등장(관제 235 요청서 1~5)
            def need(ok, msg):
                print(("  통과  " if ok else "★ 실패  ") + "[4단계] " + msg)
                if not ok: fails.append("[4단계] " + msg)
            tts = OUT / "v.wav"
            if not tts.exists():
                va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
            step4_check(OUT, need, tts); continue
        if p not in PACKS:
            fails.append(f"계약 파일에 팩 {p} 없음"); print("★ 실패  계약 파일에 팩", p, "없음"); continue
        run(p, OUT, compose, fails)
    print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
    sys.exit(1 if fails else 0)
