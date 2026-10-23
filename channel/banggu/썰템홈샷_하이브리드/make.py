# -*- coding: utf-8 -*-
"""썰템홈샷 하이브리드 한 편 제작기 (관제 097, 2026-10-22 사장님 "썰템홈샷 스타일 영상 · 방구석이랑 다르게 · 표절 안 걸리게").

    PYTHONUTF8=1 py channel/banggu/썰템홈샷_하이브리드/make.py <단계> <편>
    단계: frames | tts | scenes(훅·썸네일 장면 검색) | plan | render(썸네일.json 있으면 thumbs 까지) | thumbs | checks | all(=frames→tts→plan→render→checks)

편 = 이 폴더의 <편>/ — 대본.json(topic·hook[2줄]·post·tempo·final.lines[{fn,text,seg:A|B,facts,sources}]·facts) · 재료.json · 근거.md
작업물(git 밖) = C:/숏템_칼카피/banggu/썰템홈샷_하이브리드/<편>/ (src·narr·final.mp4)

하이브리드 = 앞(seg A) 썰 + 뒤(seg B) "저도 사 봤는데" 체험 — 한 렌더(같은 목소리·같은 틀·같은 BGM, §14 앞뒤 전환).
틀 = 썰템홈샷 외관(10-17 샘플 B 차콜·민트 — make_썰템홈샷.py 의 header/text/band/CORNER 를 그대로 부른다).
목소리 = 박창수 tc_6059dad0b83880769a50502f · tempo 기본(대본 tempo 로만 바꿈, 상한 1.25) — 필재 금지(§12).
받아쓰기 = 스피치매틱스(asr_local, 규칙 12) — narr_video 줄 시작 캐시(<mp3>.asr.json)를 먼저 채워 제미나이를 부르지 않는다.
컷 시각 = narr_video.plan_times 한 곳(plan 표와 렌더가 같은 계산). 재료.json sfx 는 t(초) 또는 line(대본 줄 번호 — 그 줄 첫 자막 시각).
관문(checks) = 길이 · LUFS · bench_distance(방구석 표절) · 나레 받아쓰기 대조 · 쉼표·줄 끝 쉼(narr_pause) · 광고 표시(engine/ad_mark) · 1초 시트.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
sys.path.insert(0, str(ROOT))
WORK = Path("C:/숏템_칼카피/banggu/썰템홈샷_하이브리드")
VOICE = "tc_6059dad0b83880769a50502f"   # 박창수
TEMPO_MAX = 1.25
LENGTH = (30.0, 42.0)                   # 앞 썰(방구석 결 중앙 ~26초) + 뒤 체험 10~15초
BGM, BGM_RATIO, LUFS = "honwaka_puppu", 0.22, -14.0
CHUNK = 13
TTEUTGI = ROOT / "channel/banggu/칼카피_ILIi/뜯기2/뜯기.json"   # 그림 칸 분포만 씀(내용 아님)

_spec = importlib.util.spec_from_file_location("make_sth", H.parent / "make_썰템홈샷.py")
K = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(K)


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _w(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def paths(piece: str) -> dict:
    d, w = H / piece, WORK / piece
    w.mkdir(parents=True, exist_ok=True)
    return {"d": d, "w": w, "script": d / "대본.json", "mat": d / "재료.json", "full": w / "narr_full.mp3", "tts": w / "narr_tight.mp3",
            "hook": d / "frame_hook.json", "body": d / "frame_body.json", "out": w / "render"}


def frames(piece: str):
    P = paths(piece); S = _j(P["script"])
    hook, post = S["hook"], S["post"]
    meta = K.BRAND + " · 14:25"
    post2 = K.split2(post)
    body = {"canvas": [1080, 1920], "made_by": K.schema.MADE_BY, "source": None,
            "made_from": {"tool": "channel/banggu/썰템홈샷_하이브리드/make.py", "note": "썰템홈샷 외관(샘플 B 차콜·민트) — make_썰템홈샷 body 와 같은 층"},
            "layers": [
                {"kind": "bg", "rgb": K.PAGE},
                {"kind": "video", "x": 0, "y": 510, "w": 1080, "h": 1300, "radius": 0},
                K.band(0, 510, 48, 1300, K.PAGE, 0), K.band(1032, 510, 48, 1300, K.PAGE, 0),
                {"kind": "image", "src": K.CORNER, "x": 48, "y": 510, "w": 984, "h": 1300},
                *K.header(),
                K.band(48, 250, 984, 220, K.WHITE, K.R),
                K.text("label", "CcPretendard-SemiBold", meta, 284, 24, 540, 900, "center", K.MINT_DK, text=meta),
                K.text("label", "SUITBold", post2, 336, 50, 540, 920, "center", K.INK, lines=2, line_h=70, text=post2),
                K.text("caption", "CcPretendard-Bold", "아웃백에서 사람들이", 1604, 50, 540, 900, "center", K.WHITE, lines=2, line_h=82, valign="top",
                       box={"rgb": K.CHAR, "pad": 22, "radius": 22}),
            ]}
    hookf = {"canvas": [1080, 1920], "made_by": K.schema.MADE_BY, "source": None,
             "made_from": {"tool": "channel/banggu/썰템홈샷_하이브리드/make.py", "note": "훅 카드 — make_썰템홈샷 hook 과 같은 층"},
             "layers": [
                 {"kind": "bg", "rgb": K.CHAR},
                 {"kind": "video", "x": 0, "y": 780, "w": 1080, "h": 1140, "radius": K.R},
                 *K.header(),
                 K.text("title", "SUITBold", hook[0], 290, 92, 540, 1000, "center", K.WHITE, lines=2, line_h=150,
                        text=chr(10).join(hook), line_rgb=[K.WHITE, [90, 240, 200]]),
                 K.text("label", "CcPretendard-SemiBold", post, 650, 36, 540, 960, "center", [168, 180, 184], text=post),
             ]}
    for p, f in ((P["hook"], hookf), (P["body"], body)):
        K.schema.validate(f); _w(p, f)
    print("틀 ok", P["hook"].name, P["body"].name)


def _lines(S):
    return [l["text"] for l in S["final"]["lines"]]


def tts(piece: str):
    P = paths(piece); S = _j(P["script"])
    tempo = S.get("tempo")
    if tempo and tempo > TEMPO_MAX:
        raise SystemExit(f"tempo {tempo} > 상한 {TEMPO_MAX} — 배속 말고 글을 줄인다")
    from tools.calcopy import narr_pause
    text = " ".join(_lines(S))
    stamp = P["w"] / "narr_tight.txt"
    if not (P["tts"].exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == f"{tempo}|{text}"):
        from shopping_shorts.channelkit import providers
        # ★줄마다 따로 합성 + 줄 사이 쉼은 우리가 넣는다 — 한 번에 보내면 타입캐스트가 쉼표 쉼을 버린다(10-22 실측, narr_pause)
        narr_pause.synth_lines(providers.typecast_synth(VOICE, tempo=tempo), _lines(S), P["w"] / "lines", P["tts"])
        stamp.write_text(f"{tempo}|{text}", encoding="utf-8")
        print("TTS 줄별(박창수):", P["tts"])
    asr = asr_cache(P["tts"])
    heard = "".join(s["text"] for s in asr)
    from tools.calcopy.narr_video import speech_segments
    from tools.calcopy.hybrid.common import nchar as nchar_ko
    dur = speech_segments(str(P["tts"]))[1]
    n = nchar_ko(text)
    print(f"나레 {dur:.2f}초 · {n}자 · {n / dur:.2f}자/초(벤치 8.32)")
    print("받아쓰기 대조:", round(SequenceMatcher(None, _flat(text), _flat(heard)).ratio(), 3), "\n  들린 글:", heard)


def _flat(s):
    import re
    return re.sub(r"[\s,.!?~'\"·…ㅋ]", "", s or "")


def asr_cache(mp3: Path) -> list[dict]:
    """스피치매틱스 받아쓰기 → narr_video.tts_transcript 캐시 꼴({md5, model, segments[start,end,text]})."""
    cache = mp3.with_name(mp3.name + ".asr.json")
    md5 = hashlib.md5(mp3.read_bytes()).hexdigest()
    if cache.exists():
        c = _j(cache)
        if c.get("md5") == md5 and (len(c["segments"]) > 3 or c.get("unit") == "word"):   # 한 덩어리 옛 캐시는 다시 받는다
            return c["segments"]
    from tools.calcopy.engine import asr_local
    r = asr_local.transcribe(str(mp3), engine="speechmatics")
    # ★낱말 단위로 넣는다 — 쉼을 0.07초로 줄인 나레는 구절이 한 덩어리(36초)라 줄 시작이 글자 비례로 밀렸다(10-22 01 요플레 B 첫 줄 1.3초 이름)
    seg = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in (r.get("words") or r.get("segments") or []) if s.get("text")]
    if not seg:
        raise SystemExit("받아쓰기 빈 답 — 멈춤")
    _w(cache, {"md5": md5, "model": r.get("engine"), "unit": "word" if r.get("words") else "segment", "note": r.get("note"), "segments": seg})
    print("받아쓰기:", r.get("engine"), r.get("note") or "")
    return seg


def _plan(P):
    return {"tteutgi": str(TTEUTGI), "frames": [{"frame": str(P["hook"]), "t_end": None}, {"frame": str(P["body"]), "t_end": None}],
            "script": str(P["script"]), "tts": str(P["tts"]), "materials": str(P["w"] / "재료_시각.json"), "out": str(P["out"]),
            "bgm": BGM, "bgm_ratio": BGM_RATIO, "lufs": LUFS, "chunk": CHUNK}


def plan(piece: str) -> dict:
    """컷 계획표 — 컷마다 시각·그 동안의 자막·줄(A 썰/B 체험). 재료.json shots 는 이 순번대로 채운다."""
    from tools.calcopy import narr_video as nv
    P = paths(piece); S = _j(P["script"])
    asr_cache(P["tts"])
    T = nv.plan_times(_plan(P), S)
    seg_of = [l.get("seg", "A") for l in S["final"]["lines"]]
    rows = []
    for k, (a, b) in enumerate(T["shots"]):
        caps = [s for s in T["steps"] if s["t0"] < b - 1e-6 and s["t1"] > a + 1e-6]
        li = caps[0]["sent"] if caps else 0
        rows.append({"shot": k, "t0": round(a, 2), "t1": round(b, 2), "dur": round(b - a, 2), "line": li, "seg": seg_of[li],
                     "caption": " / ".join(dict.fromkeys(c["text"] for c in caps)), "hook_card": a < T["hook_end"] - 1e-6})
    first = {}
    for s in T["steps"]:
        first.setdefault(s["sent"], s["t0"])
    out = {"dur": round(T["dur"], 2), "hook_end": round(T["hook_end"], 2), "line_t0": first, "shots": rows}
    _w(P["w"] / "계획.json", out)
    for r in rows:
        print(f"#{r['shot']:02d} {r['t0']:6.2f}~{r['t1']:6.2f} ({r['dur']:.2f}) 줄{r['line']} {r['seg']} {'[훅]' if r['hook_card'] else ''} {r['caption']}")
    print(f"컷 {len(rows)} · 길이 {out['dur']}초 · 훅 끝 {out['hook_end']}초 → 재료.json shots {len(rows)}개 필요")
    return out


def render(piece: str):
    from tools.calcopy import narr_video as nv
    import inspect
    P = paths(piece)
    pl = plan(piece)
    M = _j(P["mat"])
    for x in M.get("sfx") or []:   # line = 그 줄 첫 자막 시각(판단 한 곳 = plan 의 line_t0)
        if "line" in x:
            x["t"] = round(pl["line_t0"][int(x["line"])] + float(x.get("dt", 0)), 3)
    _w(P["w"] / "재료_시각.json", M)
    _orig = nv.shot_clip

    def _wide(*a, **k):   # 썰템홈샷 v2 와 같게: 그림 칸 = 창 전체(가로 984 둥근 카드·cover), 자막은 그림 위 아래쪽
        b = inspect.signature(_orig).bind(*a, **k); b.apply_defaults(); g = b.arguments
        if not g["full"]:
            g["box"] = [48, 0, 984, g["win"]["h"]]; g["min_y"] = 0; g["anchor"] = True; g["fit"] = "cover"
        return _orig(*b.args, **b.kwargs)
    nv.shot_clip = _wide
    try:
        fin = nv.build(_plan(P))
    finally:
        nv.shot_clip = _orig
    from tools.calcopy.engine import ad_mark   # 모든 렌더 오른쪽 위 '광고'(사장님 10-22, 주인 한 곳)
    ad_mark.apply_inplace(Path(fin))
    print("final", fin)
    if (P["d"] / "썸네일.json").exists():
        thumbs(piece)


# ── 썸네일 카드(맨 앞 2프레임) — 사장님 10-24 "썸네일 장면은 제일 후킹될 만한 장면으로 아주 잠깐 / 샘플 만들어서 보여줘"
# 잇템로그(thumb.py, 10-23~24)와 같은 규칙: 본편에 실제로 나오는 장면 + 빨간 원·화살표·노란 ?·빨강 굵은 글, 3안 → 무작위 1안(pick 고정),
# 꼬리표 funny = 편 번호 홀수 ㅋㅋ·짝수 ㅎㅎ / wow = ㄷㄷ. 그리기 도구·꼬리표·고르기·입히기는 thumb.py 것을 부른다(주인 한 곳).
# <편>/썸네일.json options[{id,why,mood,src,ss,crop[x,y,w,h],zoom?,circle?,arrow?,q?,text[{lines,xy,px,rot?}]}] — 좌표 = 창(1080×1140) 안.
def _card(P, M, opt, base, win, out, ep):
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid import thumb as TH
    from tools.calcopy.hybrid.render_bench import _font
    x0, y0, ww, wh = win
    src = Path(opt["src"]) if Path(opt["src"]).is_absolute() else Path(M["cand_dir"]) / opt["src"]
    cx, cy, cw, ch = opt["crop"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{float(opt['ss']):.3f}", "-i", str(src), "-frames:v", "1", "-vf",
                          f"crop={cw}:{ch}:{cx}:{cy},scale={ww}:{wh}:force_original_aspect_ratio=increase,crop={ww}:{wh}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    if len(raw) != ww * wh * 3:
        raise SystemExit(f"썸네일 장면을 못 뽑음: {src} @{opt['ss']}")
    scene = Image.frombytes("RGB", (ww, wh), raw).convert("RGBA")
    lay = Image.new("RGBA", scene.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for ex, ey, r in opt.get("circle") or []:
        d.ellipse([ex - r - 3, ey - r - 3, ex + r + 3, ey + r + 3], outline=(0, 0, 0, 200), width=20)
        d.ellipse([ex - r, ey - r, ex + r, ey + r], outline=TH.CARD_RED + (255,), width=13)
    for a, b in opt.get("arrow") or []:
        TH._arrow(d, a, b)
    for qx, qy, px in opt.get("q") or []:
        TH._shadow_text(lay, (qx, qy), ["?"], _font(TH.CARD_FONT, px), (255, 225, 0), max(8, px // 12))
    tag = TH.mood_tag(Path(f"ep{ep}"), opt.get("mood"))
    for i, tx in enumerate(opt.get("text") or []):
        lines = list(tx["lines"])
        if i == 0 and tag:
            lines[-1] = f"{lines[-1]} {tag}"
        px = tx.get("px", 120)
        while px > 70 and max(_font(TH.CARD_FONT, px).getlength(t) for t in lines) > 1000:
            px -= 4
        TH._shadow_text(lay, tx["xy"], lines, _font(TH.CARD_FONT, px), tuple(tx.get("color", TH.CARD_RED)), tx.get("stroke", 11), rot=tx.get("rot", 0.0))
    scene.alpha_composite(lay)
    full = base.copy(); full.paste(scene, (x0, y0))
    out.parent.mkdir(parents=True, exist_ok=True)
    full.convert("RGB").save(out, quality=94)
    return out


def _body_cuts(P, M) -> list[dict]:
    """본편 컷 [{src,ss,dur}] — 재료.json 컷 안 토막은 그 dur, 통 컷은 계획.json 의 그 컷 길이."""
    rows = {r["shot"]: r for r in (_j(P["w"] / "계획.json")["shots"] if (P["w"] / "계획.json").exists() else [])}
    out = []
    for k, sh in enumerate(M.get("shots") or []):
        for c in sh.get("cuts") or [{"src": sh.get("src"), "ss": sh.get("ss", 0), "dur": rows.get(k, {}).get("dur", 0)}]:
            out.append({"src": c.get("src"), "ss": float(c.get("ss") or 0), "dur": float(c.get("dur") or rows.get(k, {}).get("dur", 0))})
    return out


def scenes(piece: str) -> dict:
    """훅·썸네일 장면 찾기(구글·네이버 단서 → 유튜브 공식 원본) → <편>/장면후보.json. 순서 = thumb_rule.FIND_ORDER."""
    from tools.calcopy import scene_search
    P = paths(piece); S = _j(P["script"])
    r = scene_search.run(S.get("scene_query") or S["topic"], S.get("brand", ""), serp=int(S.get("scene_serp", 4)))
    _w(P["d"] / "장면후보.json", r)
    for v in r["videos"][:10]:
        print(("○" if v["official"] else "·"), v["id"], (v.get("channel") or "")[:16], "|", (v.get("title") or "")[:40], "|", v["from"][:40])
    return r


def thumbs(piece: str) -> dict:
    import re
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid import thumb as TH, thumb_rule
    from tools.calcopy.hybrid.render_bench import _font
    P = paths(piece); M = _j(P["mat"]); spec = _j(P["d"] / "썸네일.json")
    bad = thumb_rule.check(spec, cuts=_body_cuts(P, M))
    if bad:
        raise SystemExit("썸네일 3안 반려(thumb_rule):" + "".join("\n  " + b for b in bad) + "\n\n" + thumb_rule.FIND_ORDER)
    fin = P["out"] / "final.mp4"
    v = next(l for l in _j(P["hook"])["layers"] if l.get("kind") == "video")
    win = (int(v["x"]), int(v["y"]), int(v["w"]), int(v["h"]))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(fin), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout   # 틀(제목 2줄) = 훅 화면 그대로(0.5초 — 맨 앞 카드 뒤)
    base = Image.frombytes("RGB", (1080, 1920), raw).convert("RGBA")
    ep = int(re.match(r"\d+", piece).group())
    outs = [(o, _card(P, M, o, base, win, P["d"] / "thumb" / f"{o['id']}.jpg", ep)) for o in spec["options"]]
    tw, th = 432, 768
    sheet = Image.new("RGB", (len(outs) * (tw + 16) + 16, th + 80), (24, 24, 24)); dd = ImageDraw.Draw(sheet)
    for i, (o, p) in enumerate(outs):
        sheet.paste(Image.open(p).resize((tw, th), Image.LANCZOS), (16 + i * (tw + 16), 64))
        dd.text((16 + i * (tw + 16), 12), f"{o['id']}  {o.get('why', '')}"[:40], font=_font("Pretendard-Bold.otf", 30), fill=(255, 230, 0))
    sheet.save(P["d"] / "thumb" / "시트.jpg", quality=90)
    pk = TH.pick_option(P["d"], spec)
    TH.stamp_video(fin, P["d"] / "thumb" / f"{pk}.jpg")
    print("썸네일 3안:", P["d"] / "thumb" / "시트.jpg", "· 넣은 안:", pk)
    return {"pick": pk}


def _thumb_ok(P):
    """맨 앞 2프레임 = 고른 카드, 3번째 프레임부터 본편(카드와 다름)."""
    import numpy as np
    sp = P["d"] / "썸네일.json"
    if not sp.exists():
        return ["썸네일.json 없음", False]
    from tools.calcopy.hybrid import thumb_rule
    bad = thumb_rule.check(_j(sp), cuts=_body_cuts(P, _j(P["mat"])))
    if bad:
        return [bad, False]
    pk = _j(sp).get("pick")
    from PIL import Image
    card = np.asarray(Image.open(P["d"] / "thumb" / f"{pk}.jpg").convert("RGB").resize((270, 480)), dtype=float)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(P["out"] / "final.mp4"), "-frames:v", "3", "-vf", "scale=270:480",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 480, 270, 3).astype(float)
    dif = [round(float(abs(f - card).mean()), 1) for f in fr]
    return [{"안": pk, "프레임별 차이": dif}, dif[0] < 12 and dif[1] < 12 and dif[2] > dif[0] + 5]


def line_gap(P, S, segs) -> list:
    """렌더에 쓴 줄 시작(timeline.json 각 줄 첫 자막) vs 나레 낱말 받아쓰기의 그 줄 머리 시각 — 가장 큰 차이 ≤0.15초면 ○."""
    from tools.calcopy.narr_video import asr_line_starts
    tl = _j(P["out"] / "timeline.json")["steps"]
    used = {}
    for s in tl:
        used.setdefault(s["sent"], s["t0"])
    heard = asr_line_starts(_lines(S), segs)
    gaps = {k: round(used[k] - h, 2) for k, h in enumerate(heard) if h is not None and k in used}
    worst = max(gaps.values(), key=abs) if gaps else None
    return [{"가장 큰 차이": worst, "줄별": gaps}, worst is not None and abs(worst) <= 0.15]


def _pause(P, S, segs):
    from tools.calcopy import narr_pause
    r = narr_pause.pause_check(P["tts"], _lines(S), segs)
    return [[f'{x["kind"]} {x["pause"]}초 「{x["at"]}」' for x in r["bad"]] or f'{len(r["rows"])}자리 통과', r["ok"]]


def checks(piece: str) -> dict:
    from tools.calcopy import bench_distance as BD
    from tools.calcopy.engine import ad_mark
    P = paths(piece); S = _j(P["script"])
    fin = P["out"] / "final.mp4"
    au = _j(P["out"] / "audio.json")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(fin)],
                               capture_output=True, text=True).stdout.strip())
    bd = BD.check("banggu", P["script"], P["mat"])
    segs = asr_cache(P["tts"])
    heard = "".join(s["text"] for s in segs)
    asr_ratio = round(SequenceMatcher(None, _flat(" ".join(_lines(S))), _flat(heard)).ratio(), 3)
    sheet = P["out"] / "final_sheet_1s.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(fin), "-vf", "fps=1,scale=216:384,tile=8x5", "-frames:v", "1", str(sheet)], check=True)
    text_all = " ".join(_lines(S))
    import re
    r = {"길이": [round(dur, 2), LENGTH[0] <= dur <= LENGTH[1]],
         "LUFS": [au["final"]["I"], abs(au["final"]["I"] - LUFS) <= 0.5],
         "최고점": [au["final"]["TP"], au["final"]["TP"] <= -0.5],
         "방구석 표절": [bd["fails"] or "없음", bd["ok"]],
         "같은 소재 벤치 편(나란히 볼 것)": [[n["title"] for n in bd["same_topic"]], True],
         "나레 받아쓰기 대조": [asr_ratio, asr_ratio >= 0.9],
         "금액 없음": [re.findall(r"\d[\d,]*\s*(?:원|만원)", text_all) or "없음", not re.search(r"\d[\d,]*\s*(?:원|만원)", text_all)],
         "뒤 체험 줄 있음": [sum(l.get("seg") == "B" for l in S["final"]["lines"]), any(l.get("seg") == "B" for l in S["final"]["lines"])],
         "줄 시작 받아쓰기 낱말 단위": [len(segs), len(segs) > len(_lines(S))],   # 한 덩어리면 줄 시작이 글자 비례로 밀린다(98 #52)
         "줄 시작 = 실제 말(±0.15초)": line_gap(P, S, segs),
         "쉼표·줄 끝 쉼(붙여 읽기 없음)": _pause(P, S, segs),
         "썸네일 맨 앞 2프레임": _thumb_ok(P),
         "광고 표시": [ad_mark.MARK in ad_mark._probe(fin)[2], ad_mark.MARK in ad_mark._probe(fin)[2]],
         "시트": [str(sheet), True]}
    _w(P["out"] / "자동검사.json", r)
    ok = all(v[1] for v in r.values())
    for k, v in r.items():
        print(("○" if v[1] else "✗"), k, v[0])
    print("자동 검사", "통과" if ok else "실패", "— 사람 눈 확인 전")
    return r


if __name__ == "__main__":
    step, piece = sys.argv[1], sys.argv[2]
    for s in (["frames", "tts", "plan", "render", "checks"] if step == "all" else [step]):
        globals()[s](piece)
