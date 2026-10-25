# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — **벤치 판 공용 렌더러**(키치잇판·꿀템노트판·스타픽룸판 …). 판 설정(styles/<판>.json)만 보고 그린다 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/render_bench.py <판> <doc_dir> <work_dir> [--plan]
    (보통은 run.py <연예인> render --version <판>)

편 전용 렌더 3벌(channel/kitchit/…/render_kitchit.py · channel/kkultemnote/…/render_kkt.py · channel/starpickroom/hybrid/render_spr.py)의 공통을 뽑았다.
같은 판단 두 벌 금지:
  · 시각 = timeline() 한 곳(줄 이어 붙이기·자막 덩어리 시각·컷)            · 나레 = render_itssum.tts_once/make_sentences(Typecast·미나 서버 합성 캐시)
  · 자막·효과 배치 = placement.place() 한 곳(벤치 줄판독 빈도)              · 자막 그리기 = scene_style.compose(자막팩 길) — PNG 자막 없음
  · 자막표 → 비트 = tools/caption_pack/check_bench_packs.rows_to_timeline(자막팩 쪽 견본 그대로)
  · 틀 그림 = frame_png() 한 곳(판 설정 frame 칸) · 마스터 = −14 LUFS 2단 loudnorm(판 설정 loudness)

대본.json: slug · title_lines [[[글, 'hi'|null|'#hex'], …], …] · source_label · (comment{text,likes,from,to}) ·
  lines[{id, kind:'tts', tts, caps[{text, key?, key_color?, object_src?} | 글]} | {id, kind:'orig', src, spans[[a,b]…] | span, caps_rel[[글, s0, s1, key?]…]}
        | {id, kind:'sub', dur, caps[{text, s0?, …} | 글]}]   ← sub = 나레 없는 자막 줄(TTS 없이 dur 초 동안 자막만 — 신박·썰풀다A·숏비타민 꼴, 관제 263 02 2차)
재료.json: cand_dir · cuts{줄 id: [{src, ss?, crop[x,y,w,h] | 'face', w?, at?, max?, move?, see}]} · blur{src: [[x,y,w,h(,a,b)]…]}(원본에 박힌 글 흐림 — 잘라서 피하지 말고)
  tts 줄 = w(무게) 비례로 줄 칸 [시작, 다음 줄 시작) 을 나눔 · orig 줄 = at(줄 시작부터 초), ss 를 안 적으면 원음 구간에 입을 맞춘 초 · 비어 있으면 구간마다 얼굴 크롭 한 컷
출력(work/render/): final.mp4 · timeline.json · 자막표.json(배치 결과) · render_info.json · (doc) final_sheet_1s.jpg
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FACE_MODEL, FPS, ROOT, SR, StageError, dur_of, jload, jsave, lufs, nchar, probe, run  # noqa: E402
from tools.calcopy.engine.encoder import venc  # noqa: E402 — 인코더 주인(GPU 있으면 NVENC, 화질 같게, 98 #79)

W, H = 1080, 1920
FONTS = ROOT / "shopping_shorts/static/fonts"
SFX_DIR = ROOT / "shopping_shorts/assets/sfx_packs"
BGM_DIR = ROOT / "shopping_shorts/assets/bgm_lib"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
CAP_EXTRA = ("key", "key_color", "object_src", "aside", "append", "sound", "small")   # 대본 caps 덩어리 칸 → 배치(placement)가 읽는다


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(c, str) else tuple(c)


def _font(name, px):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), int(px))


def caps_of(L: dict) -> list[dict]:
    """줄 자막 덩어리 → [{text, key?, …}] (글만 적은 꼴도 받는다)."""
    if L["kind"] == "orig":
        out = []
        for c in L.get("caps_rel") or []:
            d = {"text": c[0], "s0": float(c[1]), "s1": float(c[2])}
            if len(c) > 3 and c[3]:
                d["key"] = c[3]
            out.append(d)
        return out
    return [c if isinstance(c, dict) else {"text": c} for c in L.get("caps") or []]


def spans_of(L: dict) -> list[list[float]]:
    return [list(s) for s in (L.get("spans") or [L["span"]])]


# ── 시간표(판단 주인) ───────────────────────────────────────────────────
LINE_KINDS = ("tts", "orig", "sub")      # sub = 나레 없는 자막 줄(dur 초) — 시각·컷은 나레 줄과 같은 길(소리만 없다)


def gap_between(st: dict, prev: str | None, cur: str) -> float:
    T = st.get("timing") or {}
    if prev is None:
        return 0.0
    if prev == "orig" and cur == "orig" and "gap_oo" in T:
        return T["gap_oo"]
    key = "gap_after_tts" if prev in ("tts", "sub") else "gap_after_orig"
    return T.get(key, T.get("gap", 0.1))


def sub_cap_starts(L: dict, dur: float) -> list[float]:
    """나레 없는 자막 줄(kind sub) 덩어리 시작(줄 시작부터 초): 덩어리에 s0 가 있으면 그것(자막 시간표 그대로), 없으면 글자 수 비례."""
    caps = caps_of(L)
    if caps and all(c.get("s0") is not None for c in caps):
        return [round(float(c["s0"]), 3) for c in caps]
    w = [max(1, nchar(c["text"])) for c in caps]
    acc, out = 0, []
    for x in w:
        out.append(round(dur * acc / sum(w), 3)); acc += x
    return out


def narr_cap_starts(L: dict, sent: dict | None, align: dict | None, tts_char0: int) -> list[float]:
    """나레 덩어리 시작(줄 시작부터 초). 글자 시각(align)이 있으면 그 덩어리 첫 글자의 소리 시각(배속·앞자르기 갚음),
    없으면 글자 수 비례. 자막 글(숫자 표기)과 tts 글(한글 읽기)이 다르면 덩어리 비율로 tts 글자 자리를 잡는다."""
    caps = caps_of(L)
    w = [max(1, nchar(c["text"])) for c in caps]
    dur = sent["dur"] if sent else sum(w) / 7.0
    if not (sent and align):
        acc, out = 0, []
        for x in w:
            out.append(round(dur * acc / sum(w), 3)); acc += x
        return out
    ch, st = align["characters"], align["character_start_times_seconds"]
    idx = [i for i, c in enumerate(ch) if re.match(r"[가-힣A-Za-z0-9]", c)]
    n_line = nchar(L["tts"])
    out, acc = [], 0
    for j, x in enumerate(w):
        if j == 0:
            out.append(0.0)
        else:
            k = tts_char0 + round(acc / sum(w) * n_line)
            k = min(k, len(idx) - 1)
            t_raw = float(st[idx[k]])
            x0 = max(0.0, sent["raw"][0] - 0.02)
            out.append(round(max(0.0, min(dur - 0.15, (t_raw - x0) / sent["tempo"])), 3))
        acc += x
    return out


def timeline(S: dict, M: dict, st: dict, sent: dict | None, align: dict | None) -> dict:
    """sent = {줄 id: {dur, raw, tempo}} (None 이면 글자÷cps 어림). 반환 = lines(줄 시각)·rows(자막 덩어리)·cuts(화면)·opos(원음 조각)·end."""
    t, prev, lines, rows, opos, char0 = 0.0, None, {}, [], [], 0
    est = st.get("cps_target", 7.0)
    for L in S["lines"]:
        if L["kind"] not in LINE_KINDS:
            raise StageError(f"줄 {L.get('id')} kind '{L['kind']}' 모름 — {LINE_KINDS}")
        t += gap_between(st, prev, L["kind"])
        if L["kind"] == "sub":          # 나레 없는 자막 줄 — 자막 시간표(dur·s0)만, 소리 없음
            d = round(float(L["dur"]), 3)
            lines[L["id"]] = [round(t, 3), round(t + d, 3)]
            starts = sub_cap_starts(L, d)
            caps = caps_of(L)
            for j, c in enumerate(caps):
                a = t + starts[j]
                b = t + (starts[j + 1] if j + 1 < len(caps) else d)
                rows.append({"line": L["id"], "j": j, "speaker": "narr", "text": c["text"], "t0": round(a, 3), "t1": round(b, 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
            t += d
        elif L["kind"] == "orig":
            t0 = t
            for k, (a, b) in enumerate(spans_of(L)):
                opos.append({"line": L["id"], "k": k, "src": L["src"], "span": [a, b], "t0": round(t, 3), "t1": round(t + b - a, 3)})
                t += b - a
            lines[L["id"]] = [round(t0, 3), round(t, 3)]
            for j, c in enumerate(caps_of(L)):
                rows.append({"line": L["id"], "j": j, "speaker": "orig", "text": c["text"], "t0": round(t0 + c["s0"], 3), "t1": round(t0 + c["s1"], 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
        else:
            s = (sent or {}).get(L["id"])
            d = s["dur"] if s else round(nchar(L["tts"]) / est, 3)
            lines[L["id"]] = [round(t, 3), round(t + d, 3)]
            starts = narr_cap_starts(L, s, align, char0)
            caps = caps_of(L)
            for j, c in enumerate(caps):
                a = t + starts[j]
                b = t + (starts[j + 1] if j + 1 < len(caps) else d)
                rows.append({"line": L["id"], "j": j, "speaker": "narr", "text": c["text"], "t0": round(a, 3), "t1": round(b, 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
            char0 += nchar(L["tts"])
            t += d
        prev = L["kind"]
    end = round(t + (st.get("timing") or {}).get("tail", 0.35), 3)
    end = round(round(end * FPS) / FPS, 4)
    order = [L["id"] for L in S["lines"]]
    Lm = {L["id"]: L for L in S["lines"]}
    cuts = []
    for i, lid in enumerate(order):
        a = lines[lid][0]
        nxt = lines[order[i + 1]][0] if i + 1 < len(order) else end
        L = Lm[lid]
        cs = (M.get("cuts") or {}).get(lid)
        if L["kind"] == "orig":
            if not cs:
                cs = [{"at": round(p["t0"] - a, 3), "src": p["src"], "ss": p["span"][0], "crop": "face", "see": "원음 구간(자동 얼굴 크롭)"}
                      for p in opos if p["line"] == lid]
            for c in cs:
                if "at" not in c and c.get("ss") is not None:   # ss 만 적은 컷 = 원음 초 → 그 초가 들리는 줄 안 시각(입 맞춤 그대로, 10-23 꿀템노트 재료)
                    p = next((p for p in opos if p["line"] == lid and p["span"][0] - 1e-3 <= float(c["ss"]) < p["span"][1]), None)
                    c = {**c, "at": round(p["t0"] - a + float(c["ss"]) - p["span"][0], 3) if p else 0.0}
                c0 = a + float(c.get("at", 0.0))
                ss = c.get("ss")
                if ss is None:      # 입 맞춤: 그 시각에 들리는 원음 조각의 원본 초
                    p = next((p for p in opos if p["line"] == lid and p["t0"] - 1e-3 <= c0 < p["t1"]), None)
                    if not p:
                        raise StageError(f"{lid} 컷 at {c.get('at')} 가 원음 조각 밖")
                    ss = round(p["span"][0] + (c0 - p["t0"]), 3)
                cuts.append({**c, "line": lid, "ss": ss, "src": c.get("src", L["src"]), "t0": round(c0, 3), "kind": "orig"})
        else:
            if not cs:
                raise StageError(f"재료.json cuts 에 나레 줄 {lid} 컷이 없다")
            ws = [float(c.get("w", 1)) for c in cs]
            acc = 0.0
            for c, w in zip(cs, ws):
                c0 = a + float(c["at"]) if "at" in c else a + (nxt - a) * acc / sum(ws)
                cuts.append({**c, "line": lid, "t0": round(c0, 3), "kind": "tts"})
                acc += w
    cuts[0]["t0"] = 0.0
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    for i, c in enumerate(cuts):
        c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else end
        c["dur"] = round(c["t1"] - c["t0"], 3)
        c["over"] = round(c["dur"] - c["max"], 3) if c.get("max") is not None and c["dur"] > c["max"] else 0.0
        if src_dir and c["kind"] == "tts" and c.get("ss") is not None and not c.get("no_snap"):
            s2 = snap_ss(src_dir / c["src"], float(c["ss"]), (round(c["t1"] * FPS) - round(c["t0"] * FPS)) / FPS)   # 실제 뽑을 프레임 길이로      # 원음 컷은 입 맞춤이라 옮기지 않는다(검사만)
            if s2 != float(c["ss"]):
                c["ss_planned"], c["ss"] = c["ss"], s2
        if src_dir:
            left = src_left(src_dir / c["src"], float(c.get("ss") or 0.0))
            if left is not None and c["dur"] > left:
                c["src_left"] = left
                c["over"] = max(c["over"], round(c["dur"] - left, 3))
    for i, r in enumerate(rows):      # 자막은 다음 덩어리 시작까지(줄 사이 틈도 앞 자막이 덮는다 — 벤치: 자막 없는 틈 거의 없음)
        r["show"] = [r["t0"], round(rows[i + 1]["t0"] if i + 1 < len(rows) else end, 3)]
    return {"lines": lines, "rows": rows, "cuts": cuts, "opos": opos, "end": end}


# ── 틀 그림(판단 주인: 판 설정 frame) ─────────────────────────────────────
FRAME_KINDS = ("window", "post", "full")      # 표준 §3-3 B1 — frame.kind 하나로 갈린다(채널 이름 분기 없음)


def frame_kind(F: dict) -> str:
    k = F.get("kind") or "window"
    if k not in FRAME_KINDS:
        raise StageError(f"frame.kind '{k}' 모름 — {FRAME_KINDS}")
    return k


def frame_window(F: dict) -> list[int]:
    """영상 창 [x,y,w,h] 한 곳 — full = 화면 전체(창 칸을 안 적어도 된다), 그 밖 = frame.window."""
    return [0, 0, W, H] if frame_kind(F) == "full" else list(F["window"])


def _glow(lay, G: dict):
    """글자 층 둘레 번짐(네온·글로우) — G{px(번짐 반지름), color, strength(진하기 배수, 기본 1)}. 층 크기 그대로(여백은 부른 쪽이 둔다).
    머리띠 채널 글·로고가 쓴다(관제 263 02 2차 ⑦ — 손 스크립트 make_썰템홈샷 민트 네온·make_맛템썰템 크림골드 네온 자리)."""
    from PIL import Image, ImageFilter
    a = lay.getchannel("A").filter(ImageFilter.GaussianBlur(float(G["px"])))
    k = float(G.get("strength", 1.0))
    if k != 1.0:
        a = a.point(lambda v: min(255, int(v * k)))
    g = Image.new("RGBA", lay.size, _rgb(G["color"]) + (255,))
    g.putalpha(a)
    return Image.alpha_composite(g, lay)


def _spaced(dl, xy, text, f, ls: float, **kw) -> float:
    """글을 그린다 — ls(자간 px, 글자 사이 더 띄우기)가 0 이면 한 번에(옛 그림 그대로), 아니면 글자마다. 반환 = 그린 폭(끝 자간 뺌)."""
    if not ls:
        dl.text(xy, text, font=f, **kw)
        return f.getlength(text)
    x = xy[0]
    for ch in text:
        dl.text((x, xy[1]), ch, font=f, **kw)
        x += f.getlength(ch) + ls
    return x - xy[0] - (ls if text else 0)


def _text_w(f, text: str, ls: float) -> float:
    return f.getlength(text) + (ls * (len(text) - 1) if ls and text else 0)


def _draw_text(im, T: dict, text: str):
    """한 줄 글(게시글 작성자·조회수·본문·머리띠 채널 글): font·px·color · x(왼쪽 x) 또는 cx(가운데 x) · cy(잉크 가운데 y) 또는 ink_top ·
    word_spacing(어절 사이 더 띄우기 px) · letter_spacing(글자 사이 px, 음수 = 좁힘) · max_w(넘치면 px 줄임) ·
    선택 stroke{px,color}(외곽선) · glow{px,color,strength}(번짐). 자리(x·cx·cy·ink_top)는 글자 잉크 기준 — 번짐은 밖으로 붙는다."""
    from PIL import Image, ImageDraw
    if not text:
        return
    px = float(T["px"])
    ws = float(T.get("word_spacing", 0))
    ls = float(T.get("letter_spacing", 0))
    words = text.split(" ")
    while True:
        f = _font(T["font"], px)
        sp = f.getlength(" ") + ws + (2 * ls if ls else 0)
        tw = sum(_text_w(f, w_, ls) for w_ in words) + sp * (len(words) - 1)
        if tw <= T.get("max_w", W) or px <= 20:
            break
        px -= 2
    asc, desc = f.getmetrics()
    SK, G = T.get("stroke") or {}, T.get("glow")
    sw = int(SK.get("px", 0))
    pad = 4 + sw + (int(math.ceil(3 * float(G["px"]))) if G else 0)       # 칸 없으면 4 = 옛 그림 그대로
    lay = Image.new("RGBA", (int(tw) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    xx = pad
    col = _rgb(T.get("color", "#000000")) + (255,)
    kw = {"fill": col, **({"stroke_width": sw, "stroke_fill": _rgb(SK.get("color", "#000000")) + (255,)} if sw else {})}
    for w_ in words:
        _spaced(dl, (xx, pad), w_, f, ls, **kw)
        xx += _text_w(f, w_, ls) + sp
    bb = lay.getbbox()
    if not bb:
        return
    if G:
        lay = _glow(lay, G)
        gb = lay.getbbox()
        lay = lay.crop(gb)
        off = (gb[0] - bb[0], gb[1] - bb[1])          # 자리는 잉크 기준 — 번짐만큼 비켜 붙인다
        iw, ih = bb[2] - bb[0], bb[3] - bb[1]
    else:
        lay = lay.crop(bb)
        off = (0, 0)
        iw, ih = lay.size
    left = int(T["x"]) if "cx" not in T else int(T["cx"]) - iw // 2
    top = int(T["ink_top"]) if "ink_top" in T else int(T["cy"]) - ih // 2
    im.alpha_composite(lay, (left + off[0], top + off[1]))


def _draw_rect(im, box, color, fade=None, radius=0):
    """[x0,y0,x1,y1](끝 제외) 채움 — fade [위 px, 아래 px] = 그 폭만큼 위·아래 끝이 투명→불투명(게시글 본문 상자 번짐) · radius 둥근 모서리."""
    from PIL import Image, ImageDraw
    import numpy as np
    x0, y0, x1, y1 = (int(v) for v in box)
    lay = Image.new("RGBA", (x1 - x0, y1 - y0), _rgb(color) + (255,))
    a = np.full((y1 - y0, x1 - x0), 255, np.uint8)
    if fade:
        col = np.full((y1 - y0,), 255.0)
        ft, fb = int(fade[0]), int(fade[1])
        if ft:
            col[:ft] = np.linspace(0, 255, ft, endpoint=False)
        if fb:
            col[-fb:] = np.linspace(255, 0, fb, endpoint=False)
        a = np.repeat(col.astype(np.uint8)[:, None], x1 - x0, axis=1)
    if radius:
        m = Image.new("L", lay.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, lay.size[0] - 1, lay.size[1] - 1], radius=int(radius), fill=255)
        a = (a.astype(np.uint16) * np.asarray(m, np.uint16) // 255).astype(np.uint8)
    lay.putalpha(Image.fromarray(a, "L"))
    im.alpha_composite(lay, (x0, y0))


def _paste_image(im, src, x, y, w, h):
    """그림 한 장(PNG 투명 그대로)을 [x,y,w,h] 에 늘려 붙인다 — 머리띠 그림 아이콘(관제 263 02 2차 ⑦). src = 저장소 상대 또는 절대 경로."""
    from PIL import Image
    p = Path(src)
    p = p if p.is_absolute() else ROOT / p
    if not p.exists():
        raise StageError(f"그림 아이콘 파일 없음: {p}")
    m = Image.open(p).convert("RGBA").resize((int(w), int(h)), Image.LANCZOS)
    im.alpha_composite(m, (int(x), int(y)))


def _draw_post(im, P: dict, S: dict):
    """게시글형 틀(B1): head_bar{box,color,icons[bars|search|text]} · rules[{box,color}](가는 줄) · author_line ·
    body_box{box,color,fade,radius,rules,text} · views_line · meme_slot{box[x,y,w,h]}.
    글은 대본 post{brand,author,body,views,meme} 가 있으면 그것, 없으면 판 칸 text."""
    from PIL import Image, ImageDraw
    SP = S.get("post") or {}
    HB = P.get("head_bar")
    if HB:
        _draw_rect(im, HB["box"], HB["color"])
        d = ImageDraw.Draw(im)
        for ic in HB.get("icons") or []:
            col = _rgb(ic.get("color", "#000000"))
            if ic["kind"] == "bars":        # 메뉴(가로 막대 여러 개)
                for yy in ic["ys"]:
                    d.rectangle([ic["x"], yy, ic["x"] + ic["w"] - 1, yy + ic["h"] - 1], fill=col)
            elif ic["kind"] == "search":    # 돋보기(고리 + 손잡이) — 84px 기준 꼴(설명서 frame.json 아이콘과 같은 비율)
                k = ic["size"] / 84.0
                sw = max(1, int(round(ic.get("stroke", 7) * k)))
                cx, cy, r = ic["x"] + 34 * k, ic["y"] + 34 * k, 28 * k
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=sw)
                d.line([ic["x"] + 54 * k, ic["y"] + 54 * k, ic["x"] + 80 * k, ic["y"] + 80 * k], fill=col, width=sw)
            elif ic["kind"] == "text":      # 머리띠 안 채널 글(브랜드) — stroke·glow 칸이면 외곽선·네온
                _draw_text(im, ic, SP.get(ic.get("from", "brand")) or ic.get("text"))
            elif ic["kind"] == "image":     # 그림 아이콘(화살표·포크 접시 등 글꼴에 없는 꼴) — src 를 [x,y,w,h] 에 붙인다
                _paste_image(im, ic["src"], ic["x"], ic["y"], ic["w"], ic["h"])
            else:
                raise StageError(f"머리띠 아이콘 kind '{ic['kind']}' 모름 — bars·search·text·image")
    for r in P.get("rules") or []:
        _draw_rect(im, r["box"], r["color"])
    BB = P.get("body_box")
    if BB:
        _draw_rect(im, BB["box"], BB["color"], BB.get("fade"), BB.get("radius", 0))
        for r in BB.get("rules") or []:
            _draw_rect(im, r["box"], r["color"])
        if BB.get("text"):
            _draw_text(im, BB["text"], SP.get("body") or BB["text"].get("text"))
    for key, sk in (("author_line", "author"), ("views_line", "views")):
        if P.get(key):
            _draw_text(im, P[key], SP.get(sk) or P[key].get("text"))
    MS = P.get("meme_slot")
    if MS and SP.get("meme") and Path(SP["meme"]).exists():      # 반응 짤 자리(채워 자르기)
        x, y, w, h = MS["box"]
        m = Image.open(SP["meme"]).convert("RGBA")
        s = max(w / m.size[0], h / m.size[1])
        m = m.resize((max(1, round(m.size[0] * s)), max(1, round(m.size[1] * s))), Image.LANCZOS)
        l, t = (m.size[0] - w) // 2, (m.size[1] - h) // 2
        im.alpha_composite(m.crop((l, t, l + w, t + h)), (x, y))


def _draw_full(im, FL: dict | None):
    """전체화면 틀(B1): 창 = 화면 전체, 위에 얹는 것은 가운데 자막 띠(선택) — band{cy,h,rgba}."""
    from PIL import Image
    B = (FL or {}).get("band")
    if B:
        im.alpha_composite(Image.new("RGBA", (W, int(B["h"])), tuple(B["rgba"])), (0, int(B["cy"]) - int(B["h"]) // 2))


TITLE_ALIGNS = ("center", "left", "right")


def _title_line(im, spec: dict, segs):
    """제목 한 줄(낱말 색·기울임·박스) 한 곳 — 선택 칸 stroke{px,color}·shadow{dx,dy,color}(게시글형 제목 외곽선·그림자) ·
    align(center 기본|left|right) + x(left = 왼쪽 끝 x · right = 오른쪽 끝 x · center = 가운데 x, 기본 화면 가운데) · letter_spacing(글자 사이 px).
    칸이 없으면 외곽선 0·그림자 없음·가운데·자간 0 = 옛 그림과 같은 픽셀(회귀 검사 대상)."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(im)
    segs = [(s, None) if isinstance(s, str) else (s[0], s[1] if len(s) > 1 else None) for s in segs]
    col = lambda c: _rgb(spec["hi"]) if c == "hi" else (_rgb(c) if c else _rgb(spec["color"]))
    al = spec.get("align", "center")
    if al not in TITLE_ALIGNS:
        raise StageError(f"제목 align '{al}' 모름 — {TITLE_ALIGNS}")
    ls = float(spec.get("letter_spacing", 0))
    px = spec["px"]
    while True:
        f = _font(spec["font"], px)
        tw = sum(f.getlength(t) for t, _ in segs) + (ls * (sum(len(t) for t, _ in segs) - 1) if ls else 0)
        if tw <= spec.get("max_w", 1000) or px <= 50:
            break
        px -= 2
    asc, desc = f.getmetrics()
    SK, SH = spec.get("stroke") or {}, spec.get("shadow")
    sw = int(SK.get("px", 0))
    pad = int(px * 0.5) + sw + (max(abs(SH["dx"]), abs(SH["dy"])) if SH else 0)
    sh = float(spec.get("shear") or 0)
    lay = Image.new("RGBA", (int(tw) + 2 * pad + int((asc + desc) * sh), asc + desc + 2 * pad), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    x0 = pad + int((asc + desc) * sh * 0.5)
    if SH:
        xx = x0
        for t, c in segs:
            xx += _spaced(dl, (xx + SH["dx"], pad + SH["dy"]), t, f, ls, fill=_rgb(SH["color"]) + (255,), stroke_width=sw,
                          stroke_fill=_rgb(SH["color"]) + (255,)) + (ls if ls and t else 0)
    xx = x0
    for t, c in segs:
        xx += _spaced(dl, (xx, pad), t, f, ls, fill=col(c) + (255,), stroke_width=sw,
                      stroke_fill=_rgb(SK.get("color", "#000000")) + (255,)) + (ls if ls and t else 0)
    if sh:
        lay = lay.transform(lay.size, Image.AFFINE, (1, sh, -sh * lay.size[1] * 0.5, 0, 1, 0), resample=Image.BICUBIC)
    lay = lay.crop(lay.getbbox())
    if spec.get("box"):
        bx = spec["box"]
        d.rectangle(bx, fill=_rgb(spec["box_color"]) + (255,))
        top = (bx[1] + bx[3]) // 2 - lay.size[1] // 2
    elif "center" in spec:
        top = spec["center"] - lay.size[1] // 2
    else:
        top = spec["ink_top"]
    if al == "left":
        left = int(spec["x"])
    elif al == "right":
        left = int(spec["x"]) - lay.size[0]
    else:
        left = int(spec.get("x", W // 2)) - lay.size[0] // 2
    im.alpha_composite(lay, (left, int(top)))


def _seg_time(v, S: dict, T: dict) -> float:
    """구간 끝 시각: 숫자(초) · '<줄 id>.start|end' · '#<k>.start|end'(k번째 줄, 1부터)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.fullmatch(r"(#?)([^.]+)\.(start|end)", str(v))
    if not m:
        raise StageError(f"frame.segments 시각 '{v}' 모름 — 초 · '<줄id>.start|end' · '#k.start|end'")
    ids = [L["id"] for L in S["lines"]]
    lid = ids[int(m.group(2)) - 1] if m.group(1) else m.group(2)
    if lid not in T["lines"]:
        raise StageError(f"frame.segments 줄 '{lid}' 이 대본에 없다")
    a, b = T["lines"][lid]
    return a if m.group(3) == "start" else b


SEG_CAPTIONS = ("show", "hide")


def frame_segments(S: dict, T: dict, st: dict) -> list[dict]:
    """시간 구간별 틀(관제 263 02 2차 ①) — 판 칸 frame.segments[{t0, t1, frame{…덮을 칸}, captions show|hide, body_text lines|null, why}].
    구간 밖은 판 frame 그대로, 구간 안은 frame 에 구간 frame 을 깊게 덮은 틀(kind·window·title… 전부 바꿀 수 있다 — 훅 카드 → 본문 틀, A/B 하이브리드).
    body_text=lines = 그 구간에서 시작하는 나레·자막 줄 글을 게시글 본문(post.body) 자리에 — 훅 카드 가운데 흰 띠 나레 문장.
    captions=hide = 그 구간 자막팩 자막을 그리지 않는다(훅 카드 띠가 자막을 대신). 시각은 프레임 격자에 맞춘다. 겹치면 멈춘다.
    판단 주인 = 이 함수 하나(render_base·caption_rows·devices 가 이것만 읽는다)."""
    F = st.get("frame") or {}
    segs = F.get("segments") or []
    if not segs:
        return []
    from tools.calcopy.hybrid import styles as ST
    base = {k: v for k, v in F.items() if k != "segments"}
    end = T["end"]
    out = []
    for i, sg in enumerate(segs):
        t0 = _seg_time(sg.get("t0", 0.0), S, T)
        t1 = _seg_time(sg["t1"], S, T)
        t0 = round(round(max(0.0, t0) * FPS) / FPS, 4)
        t1 = round(round(min(end, t1) * FPS) / FPS, 4)
        if t1 <= t0:
            raise StageError(f"frame.segments[{i}] 길이 0 이하({t0}~{t1})")
        Fi = ST._merge(base, sg.get("frame") or {})
        frame_kind(Fi)
        cap = sg.get("captions", "show")
        if cap not in SEG_CAPTIONS:
            raise StageError(f"frame.segments[{i}].captions '{cap}' 모름 — {SEG_CAPTIONS}")
        bt = sg.get("body_text")
        text = None
        if bt == "lines":
            text = " ".join((L.get("tts") or " ".join(c["text"] for c in caps_of(L))).strip() for L in S["lines"]
                            if L["kind"] != "orig" and t0 - 1e-3 <= T["lines"][L["id"]][0] < t1 - 1e-3)
        elif bt is not None:
            raise StageError(f"frame.segments[{i}].body_text '{bt}' 모름 — lines 또는 비움")
        out.append({"i": i, "t0": t0, "t1": t1, "frame": Fi, "kind": frame_kind(Fi), "window": frame_window(Fi), "captions": cap,
                    "body_text": text, "why": sg.get("why")})
    out.sort(key=lambda g: g["t0"])
    for a, b in zip(out, out[1:]):
        if b["t0"] < a["t1"]:
            raise StageError(f"frame.segments 겹침: {a['t0']}~{a['t1']} · {b['t0']}~{b['t1']}")
    return out


def seg_frame_png(S: dict, st: dict, sg: dict, out: Path) -> Path:
    """구간 틀 한 장 — 구간 frame + (body_text 가 있으면) 대본 post.body 를 그 글로."""
    S2 = S if sg.get("body_text") is None else {**S, "post": {**(S.get("post") or {}), "body": sg["body_text"]}}
    return frame_png(S2, {**st, "frame": sg["frame"]}, out)


def title_segs(F: dict, S: dict) -> list:
    """틀 제목 줄 칸(frame.title[i]) ↔ 대본 title_lines 짝 한 곳. 칸에 join(이을 글, 예 " ")이 있으면 그 칸이 대본의 남은 줄을 전부 이어 한 줄로 그린다
    (게시글 본문 제목 = 훅 2줄을 한 줄로 — 07 2차 썰템홈샷판: 칸 1개라 1줄째만 나오던 것). join 없으면 옛 짝(i번째 칸 = i번째 줄) 그대로."""
    TL = S.get("title_lines") or []
    out = []
    for i, spec in enumerate(F.get("title") or []):
        if i >= len(TL):
            break
        if spec.get("join") is None:
            out.append(TL[i])
            continue
        segs = []
        for k, ln in enumerate(TL[i:]):
            if k:
                segs.append(str(spec["join"]))
            segs += list(ln)
        out.append(segs)
        break
    return out


def frame_png(S: dict, st: dict, out: Path) -> Path:
    """틀 한 장(창 자리는 투명). frame.kind = window(바탕 + 제목 줄들 + 로고 + 출처 + 워터마크, 기본) ·
    post(게시글형: 머리띠·작성자 줄·본문 상자·조회수 줄·짤 자리 + 같은 제목 줄·출처·로고) · full(전체화면 — 창 = 화면 전체, 가운데 자막 띠·제목·로고만)."""
    from PIL import Image, ImageDraw
    F = st["frame"]
    kind = frame_kind(F)
    im = Image.new("RGBA", (W, H), _rgb(F.get("bg", [0, 0, 0])) + (255,))
    x, y, w, h = frame_window(F)
    rad = int(F.get("window_radius") or 0) if kind != "full" else 0
    if rad:      # 둥근 창(관제 263 02 2차 ⑤) — 모서리는 틀 바탕이 덮는다. 4배로 그려 줄여 가장자리 부드럽게
        m = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=rad * 4, fill=255)
        im.paste(Image.new("RGBA", (w, h), (0, 0, 0, 0)), (x, y), m.resize((w, h), Image.LANCZOS))
    else:
        im.paste((0, 0, 0, 0), (x, y, x + w, y + h))
    if kind == "post":
        _draw_post(im, F.get("post") or {}, S)
    elif kind == "full":
        _draw_full(im, F.get("full"))
    d = ImageDraw.Draw(im)
    for spec, segs in zip(F.get("title") or [], title_segs(F, S)):
        _title_line(im, spec, segs)
    C = F.get("credit")
    if C and S.get("source_label"):
        f = _font(C["font"], C["px"])
        bb = d.textbbox((0, 0), S["source_label"], font=f)
        top = C["ink_top"] - bb[1] if "ink_top" in C else C["center"] - (bb[1] + bb[3]) // 2
        d.text((W // 2 - (bb[2] - bb[0]) // 2 - bb[0], top), S["source_label"], font=f, fill=_rgb(C["color"]))
    WM = F.get("watermark")
    if WM:
        f = _font(WM["font"], WM["px"])
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        bb = f.getbbox(WM["text"])
        dl.text((WM["x1"] - f.getlength(WM["text"]), WM["cy"] - (bb[1] + bb[3]) // 2), WM["text"], font=f, fill=(255, 255, 255, WM["alpha"]))
        im.alpha_composite(lay)
    LG = F.get("logo")
    if LG and LG.get("kind") == "spr_gold":
        sys.path.insert(0, str(ROOT / "channel/starpickroom/_tools"))
        import spr_overlay
        spr_overlay.logo_layer(im, LG["text"])
    elif LG:
        f = _font(LG["font"], LG["px"])
        G = LG.get("glow")              # 로고 번짐(네온) — {px,color,strength} · 외곽선 = stroke(px)·stroke_rgba
        mg = int(math.ceil(3 * float(G["px"]))) if G else 0
        lay = Image.new("RGBA", (W, 160 + 2 * mg), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((LG["x"], 10 + mg), LG["text"], font=f, fill=tuple(LG["rgba"]), stroke_width=LG.get("stroke", 0), stroke_fill=tuple(LG.get("stroke_rgba", [0, 0, 0, 255])))
        if G:
            lay = _glow(lay, G)
        im.alpha_composite(lay, (0, LG["y"] - 10 - mg))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def comment_png(C: dict, px: int, out: Path) -> tuple[int, int]:
    """유튜브 댓글 카드(꿀템노트 벤치 m0Ex·KCx 실측: 흰 상자, 글 검정, 아래 줄 엄지·숫자·'답글')."""
    from PIL import Image, ImageDraw
    f, fs = _font("Pretendard-Regular.otf", px), _font("Pretendard-Regular.otf", 28)
    try:
        from PIL import ImageFont
        sym = ImageFont.truetype("C:/Windows/Fonts/segmdl2.ttf", 32)
    except OSError:
        sym = fs
    w = int(min(980, f.getlength(C["text"]) + 44)); h = 142
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    d.text((20, 14), C["text"], font=f, fill=(15, 15, 15))
    d.text((20, 86), "\ue8e1", font=sym, fill=(30, 30, 30))
    d.text((66, 88), str(C.get("likes", "")), font=fs, fill=(96, 96, 96))
    d.text((130, 86), "\ue8e0", font=sym, fill=(30, 30, 30))
    d.text((210, 88), "답글", font=fs, fill=(30, 30, 30))
    im.save(out)
    return w, h


# ── 화면 ────────────────────────────────────────────────────────────────
_det = None


def face_crop(src: Path, t: float, ar: float) -> list[int]:
    """그 프레임의 가장 큰 얼굴을 가운데로 둔 ar(가로/세로) 크롭 — 높이는 원본 전체."""
    import cv2
    global _det
    sw, sh, _ = probe(src)
    ch = sh; cw = int(round(ch * ar)); cw = min(cw, sw)
    if cw == sw:
        ch = int(round(sw / ar))
    cap = cv2.VideoCapture(str(src)); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read(); cap.release()
    cx = sw / 2
    if ok:
        if _det is None:
            _det = cv2.FaceDetectorYN.create(FACE_MODEL, "", (320, 320), 0.6, 0.3, 50)
        _det.setInputSize((f.shape[1], f.shape[0]))
        _, faces = _det.detect(f)
        if faces is not None and len(faces):
            fx, fy, fw, fh = max(faces, key=lambda z: z[2] * z[3])[:4]
            cx = fx + fw / 2
    x = int(min(max(cx - cw / 2, 0), sw - cw))
    return [x, 0, cw, ch]


BLUR_SIGMA = 25.0     # 가림 흐림 세기 = 제품 가림막 흐림의 최저값(deco_frame.blur_sigma 25~80)과 같은 gblur


def blur_vf(regs, ss: float, dur: float, sigma: float = BLUR_SIGMA) -> str:
    """원본에 박힌 자막·글 자리를 흐린다(원본 픽셀 좌표, 잘라 내기 전). regs = [[x, y, w, h(, a, b)], …], a~b = 원본 초(없으면 늘).
    10-22 사장님 "자막을 가리려고 확대를 많이 해서 너무 커지거나 가운데로 안 간다 → 가림막 흐림으로": 잘라서 피하던 걸 흐림으로 바꾼다.
    흐림은 제품 렌더(video_assemble)와 같은 gblur — 다만 여기는 원본 좌표라 마스크 그림 대신 사각 영역(crop→gblur→overlay)."""
    out = []
    for r in regs or []:
        x, y, w, h = (int(v) for v in r[:4])
        a, b = (float(r[4]), float(r[5])) if len(r) >= 6 else (None, None)
        if a is not None and (b <= ss or a >= ss + dur):
            continue                                           # 이 컷 구간과 안 겹침
        en = f":enable='between(t,{max(0.0, a - ss):.3f},{b - ss:.3f})'" if a is not None else ""
        out.append(f"split[bo][bi];[bi]crop={w}:{h}:{x}:{y},gblur=sigma={sigma}[bb];[bo][bb]overlay={x}:{y}{en}")
    return ",".join(out)


_src_len: dict[str, float] = {}


def src_left(src: Path, ss: float) -> float | None:
    """원본 영상에서 ss 뒤로 남은 화면 초(마지막 프레임 하나 뺌). 사진은 None(얼마든 늘린다).
    10-23 사장님 "뒤에 멈추거나 중간중간 튄다": 컷이 원본 끝을 넘으면 clip 이 n프레임보다 적게 뽑고, 뒤 컷이 전부 앞당겨져
    (09 딸기라떼 27프레임 = 0.9초 어긋남) 끝 화면이 멈췄다. 그때까지 아무 검사도 안 걸렸다(05·08·09·11 네 편)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return None
    k = str(src)
    if k not in _src_len:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration:format=duration", "-of", "json", src]).stdout
        j = json.loads(out)
        d = (j.get("streams") or [{}])[0].get("duration") or (j.get("format") or {}).get("duration")
        _src_len[k] = float(d)
    return round(_src_len[k] - ss - 1 / FPS, 3)


MIN_PIECE_SEC = 0.4   # 컷을 원본 장면 경계로 나눈 조각이 이보다 짧으면 번쩍임(오류기록 55·84) — 계획(snap_ss)·관문·품질 검사가 이 한 상수를 쓴다
SLIVER_SEC = MIN_PIECE_SEC      # 컷 처음·끝 이 안에 장면 경계가 있으면 '번쩍임'(앞뒤 샷이 몇 프레임 끼어 튀어 보인다)


def shot_starts(video: Path) -> list[float]:
    """영상의 장면 경계(새 샷이 시작하는 초, 30fps 격자) — '경계가 어디냐'의 주인 한 곳(오류기록 84).
    후보 = readline_tools.cutdet(상대 문턱 max(12, 3.5×이웃 중앙값) 또는 히스토그램차), 확정 = 경계 앞뒤 프레임 상관 < CUT_CORR_MAX(_real_cut, 오류기록 85).
    snap_ss(계획)·cut_boundary_gate(관문)·quality_gate.part_slivers(완성본 검사) 모두 이걸 부른다. 파일 옆 json 캐시.
    (옛 판은 절대 문턱 max(25, 4×중앙값)이라 차 22~31 인 진짜 편집점을 놓쳤다 — 10-25 잇템로그 05·09 번쩍임.)"""
    w, h = probe(Path(video))[:2]
    return _src_cuts(Path(video), 0, int(h), int(w))


def short_pieces(starts: list[float], a: float, b: float) -> list[float]:
    """구간 [a,b) 를 경계(첫 프레임 직후·마지막 프레임 이후는 제외)로 쪼갠 조각 중 MIN_PIECE_SEC 보다 짧은 것의 길이."""
    pts = [a] + [t for t in starts if a + 1.5 / FPS < t <= b - 1 / FPS + 1e-3] + [b]
    if len(pts) == 2:
        return []
    return [round(y - x, 2) for x, y in zip(pts, pts[1:]) if y - x < MIN_PIECE_SEC - 1e-3]


def slivers(starts: list[float], a: float, b: float, edge: float = SLIVER_SEC) -> list[float]:
    """구간 [a,b) 안 경계 중 처음·끝 edge 안에 있는 것."""
    return [s for s in starts if a + 1e-3 < s < b - 1e-3 and (s - a < edge - 1e-3 or b - s < edge - 1e-3)]      # 딱 0.2초(6프레임)는 통과


def snap_ss(src: Path, ss: float, dur: float, reach: float = 0.4) -> float:
    """나레 컷 시작 초를 ±reach 안에서 가장 덜 움직여 번쩍임 없는 자리로(원본 끝도 넘지 않게). 못 찾으면 그대로(검사가 잡는다)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return ss
    st = shot_starts(src)
    if not short_pieces(st, ss, ss + dur):
        return ss
    for k in range(1, int(reach * FPS) + 1):
        for s in (ss + k / FPS, ss - k / FPS):
            left = src_left(src, s)
            if s >= 0 and (left is None or dur <= left) and not short_pieces(st, s, s + dur):
                return round(s, 3)
    return ss


CUT_CORR_MAX = 0.86   # 경계 앞뒤 프레임 회색 상관이 이보다 낮으면 진짜 편집점(오류기록 85: 146개 오푸스 눈 판정 P 0.94·R 0.97, 0.6 이면 R 0.43)
CUTBOUNDS_VER = 2     # 경계 판정(문턱·읽는 법)이 바뀌면 올린다 — 파일 옆 캐시 이름에 들어가 옛 판정 캐시를 안 쓴다


def _cut_corr(src: Path, t: float, y0: int, y1: int, w: int) -> float | None:
    """cutdet 후보 t(새 샷 첫 프레임) 앞뒤 이웃 프레임 쌍 3개(t-2→t-1, t-1→t, t→t+1) 회색 상관 중 최솟값. 못 재면 None.
    ±1프레임을 보는 건 -ss 찾기가 한두 프레임 어긋나도 경계를 놓치지 않게(ep09 j2B 14.97 이 같은 프레임 두 장으로 1.00 이 나왔다).
    영상 첫 3프레임 안 후보는 읽기 시작을 0 으로 당기고 쌍 위치를 그만큼 옮긴다(옛 판은 경계 뒤 프레임끼리 재서 0.95~0.99 로 놓쳤다)."""
    import numpy as np
    import subprocess
    H = max(16, y1 - y0)
    k = round(t * FPS)
    s0 = max(0, k - 3)
    c = k - s0                       # 읽은 프레임 중 t 의 자리
    K = c + 2
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s0 / FPS:.4f}", "-i", str(src), "-vf",
                          f"fps={FPS},crop={w}:{H}:0:{y0},scale=90:-2,format=gray", "-frames:v", str(K), "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    n = len(raw) // K
    if n < 2 or len(raw) % K:
        return None
    F = [np.frombuffer(raw[q * n:(q + 1) * n], np.uint8).astype(float) for q in range(K)]
    cs = [float(np.corrcoef(F[q], F[q + 1])[0, 1]) for q in range(max(0, c - 2), c + 1) if F[q].std() > 1e-6 and F[q + 1].std() > 1e-6]
    return min(cs) if cs else None


def _real_cut(src: Path, t: float, y0: int, y1: int, w: int) -> bool:
    """cutdet 후보가 진짜 편집점(다른 샷·각도·점프컷)인지 — 판정 주인 한 곳. 상관 < CUT_CORR_MAX.
    10-25 오푸스 눈 판정 146개(잇템로그 05·09·13 + 키칫·꿀템노트·스타픽룸·성시경 가로 원본): 같은 배경 점프컷이 0.6~0.85 에 몰려 있어
    옛 0.6 은 진짜 편집점 절반 이상을 놓쳤다. 같은 샷(걷기·손·자막만 바뀜·번쩍 효과)은 대부분 0.86 이상. 표본: readline_tools/fixtures/cut_corr_labels.json.
    못 재면 진짜로 본다(놓치는 쪽이 번쩍임을 통과시키므로)."""
    r = _cut_corr(src, t, y0, y1, w)
    return True if r is None else r < CUT_CORR_MAX


def _src_cuts(src: Path, y0: int, y1: int, w: int) -> list[float]:
    """원본 한 파일의 장면 경계 초(주인 = readline_tools.cutdet.cutdet — 상대 문턱 max(12, 3.5×이웃 중앙값) 또는 히스토그램차, 불러 쓴다). 파일 옆 json 캐시."""
    cp = src.parent / f"_cutbounds_{src.stem}_{y0}_{y1}_v{CUTBOUNDS_VER}.json"
    try:
        if cp.exists() and cp.stat().st_mtime >= src.stat().st_mtime:
            return jload(cp)
    except Exception:
        pass
    from tools.calcopy.engine.readline_tools.cutdet import cutdet
    ts = [t for t in (float(r["t"]) for r in cutdet(str(src), y0, y1, float(FPS), w)["cuts"]) if _real_cut(src, t, y0, y1, w)]
    try:
        jsave(cp, ts)
    except Exception:
        pass
    return ts



def cut_boundary_gate(T: dict, M: dict, st: dict | None = None) -> list[str]:
    """렌더 전 관문 ③(10-25 잇템로그 05·09 번쩍임): 계획된 컷마다 원본 [ss, ss+길이] 안(가장자리 포함, 맨 앞 1프레임 제외)에
    장면 경계로 나눈 조각 중 MIN_PIECE_SEC(0.4초)보다 짧은 것이 있으면 막는다. 옛 shot_starts(절대 문턱 25)는 차 22~31 인 진짜 편집점을 놓쳤고 slivers 는 가장자리 0.2초만 봤다.
    경계는 shot_starts(원본 전체 화면) — 크롭 밖 편집점도 센다. 계획(snap_ss)이 같은 경계로 먼저 피하고 이 관문은 확인만 한다."""
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    if not src_dir:
        return []
    bad = []
    for c in T["cuts"]:
        src = src_dir / c["src"]
        if c.get("ss") is None or src.suffix.lower() in IMG_EXT or not src.exists():
            continue
        ss = float(c["ss"])
        n = c.get("frames") or (round(c["t1"] * FPS) - round(c["t0"] * FPS))
        end = ss + n / FPS
        hit = [t for t in shot_starts(src) if ss + 1.5 / FPS < t <= end - 1 / FPS + 1e-3]
        short = short_pieces(hit, ss, end)
        if hit and short:      # 양쪽이 긴 조각이면 원본 자체의 이어진 편집이라 통과 — 짧은 조각(번쩍임)만 막는다(오류기록 55: 0.3초 꼬리도 결함)
            bad.append(f"컷 경계 {c['line']} {c['src']} ss={ss:.2f}~{end:.2f} 안 원본 장면 경계 {[round(t, 2) for t in hit]}초 → 짧은 조각 {short}초(<{MIN_PIECE_SEC})")
    return bad


def count_frames(p: Path) -> int:
    return int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                    "-of", "csv=p=0", p]).stdout.strip().split(",")[0] or 0)   # ICC side_data 면 '78,' (98 #73)


def pic_box(c: dict, win: tuple[int, int]) -> list[int] | None:
    """컷 그림 칸(관제 263 02 2차 ⑥) — 재료.json 컷 pic[x,y,w,h](창 안 px). 없으면 None(창 가득, 옛 그림). 창 밖이면 멈춘다."""
    pb = c.get("pic")
    if not pb:
        return None
    x, y, w, h = (int(v) for v in pb)
    if x < 0 or y < 0 or w < 16 or h < 16 or x + w > win[0] or y + h > win[1]:
        raise StageError(f"컷 pic {pb} 가 창 {list(win)} 밖")
    return [x, y, w - (w & 1), h - (h & 1)]          # yuv420 = 짝수 크기


def clip(src: Path, ss: float, n: int, crop, win: tuple[int, int], out: Path, push: float = 0.0, move=None, blur=None, pic=None, pic_bg=None):
    """컷 조각 하나 — 창 크기(win) 영상. pic[x,y,w,h] 를 주면 그 칸 크기로 그리고 창 나머지는 pic_bg 색(틀 바탕)으로 채운다(컷마다 그림 칸 크기)."""
    ww, wh = win
    tw, th = (pic[2], pic[3]) if pic else (ww, wh)
    pad = f",pad={ww}:{wh}:{pic[0]}:{pic[1]}:color=0x{''.join(f'{v:02X}' for v in _rgb(pic_bg or [0, 0, 0]))}" if pic else ""
    if src.suffix.lower() in IMG_EXT:
        from tools.calcopy import narr_video as nv
        x, y, cw, ch = crop
        mv = nv.still_move(src, crop, tw / th, n / FPS, move or "in")
        # 사진(JPG)은 yuvj420p·pc·bt470bg 로 나온다 → 영상 조각(yuv420p·tv·bt709)과 이어 붙이면 render_base 가 그 경계에서
        # 필터를 다시 세우며 틀(제목·로고·출처 줄)을 2~4프레임 빠뜨린다(10-21 장윤주 실측: 쿠팡 사진 컷 앞뒤 2+4프레임 → 고친 뒤 0.
        # 최화정_피부 완성본에도 제목 빠짐 2+2프레임이 있었다 — 원인 대조는 안 함). 영상 조각과 같은 꼴로 맞춘다.
        vf = (f"crop={cw}:{ch}:{x}:{y},{mv}scale={tw}:{th}:flags=lanczos:out_range=tv:out_color_matrix=bt709{pad},"
              f"format=yuv420p,setsar=1")
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", src, "-vf", vf, "-frames:v", n, "-r", FPS, *venc(16), "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", out])
        return
    x, y, cw, ch = crop
    bl = blur_vf(blur, ss, n / FPS)
    pre = bl + "," if bl else ""
    vf = f"{pre}crop={cw}:{ch}:{x}:{y},scale={tw}:{th}:flags=lanczos,setsar=1{pad},fps={FPS}"
    if push:
        vf = (f"{pre}crop={cw}:{ch}:{x}:{y},scale={tw * 2}:{th * 2}:flags=lanczos,fps={FPS},"
              f"zoompan=z='1+{push}*on/{max(1, n)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={tw}x{th}:fps={FPS},setsar=1{pad}")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.3f}", "-i", src, "-an", "-vf", vf, "-frames:v", n, *venc(16), "-pix_fmt", "yuv420p", out])


# ── 장면 전환(A1) — 종류·자리 결정 = placement.place(placed["transitions"]), 여기는 읽기·그리기만 ──────────────
TRANSITION_KINDS = ("cut", "flash", "zoomblur", "black", "edge_glow")
TRANSITION_MS = {"flash": 100, "zoomblur": 200, "black": 33, "edge_glow": 450}     # 판 칸 cuts.transition.ms 가 0/없을 때 종류별 기본 길이 · edge_glow 450 = shark rules flash.dur(사건 길이, α 는 dur 칸)
ZOOMBLUR_ZOOM, ZOOMBLUR_SIGMA = 0.12, 14.0                         # 줌블러: 경계에서 최대 12% 확대 + gblur(가림 흐림 BLUR_SIGMA 와 별개 — 움직임 번짐)


def transitions_of(T: dict, st: dict, placed: dict, log=None) -> list[dict]:
    """전환 목록 [{t, kind, ms, sec?, why}] 한 곳 — render_window(줌블러·검은 프레임, 창 안)·render_base(흰 번쩍, 화면 전체)가 이것만 읽는다.
    종류·자리 판단 주인 = placement.place → placed["transitions"](지시서 03, 판 칸 cuts.transition.kinds 비율도 거기서 읽는다).
    여기는 **읽기·정리만**: 모르는 종류는 막고, ms 가 비면 판 cuts.transition.ms → 종류별 기본(TRANSITION_MS). cut 은 그릴 것 없음.
    placed 에 transitions 칸이 없는 옛 배치 결과(03 전)는 옛 키 flashes 를 kind=flash 로 읽는다(변환만 — 흰 번쩍 그림 그대로)."""
    F = st.get("frame") or {}
    ms_set = (st.get("cuts") or {}).get("transition", {}).get("ms") or 0
    ncf: dict = {}

    def norm(e):
        k = e.get("kind", "cut")
        if k not in TRANSITION_KINDS:
            raise StageError(f"전환 종류 '{k}' 모름 — {TRANSITION_KINDS}")
        m = e.get("ms") or (ms_set.get(k) if isinstance(ms_set, dict) else ms_set) or TRANSITION_MS.get(k, 0)
        out = {"t": round(float(e["t"]), 3), "kind": k, "ms": float(m)}
        if k in ("flash", "edge_glow"):
            out.update(flash_color_of(e, st, ncf.setdefault(k, [0])))
        if e.get("sec") is not None:
            out["sec"] = float(e["sec"])
        if e.get("why"):
            out["why"] = e["why"]
        return out
    if placed.get("transitions") is not None:
        return sorted((norm(e) for e in placed["transitions"] if e.get("kind", "cut") != "cut"), key=lambda e: e["t"])
    fsec = F.get("flash_sec", 0.1)
    if log and any(k != "cut" for k in ((st.get("cuts") or {}).get("transition", {}).get("kinds") or {})):
        log("[전환] 배치 결과에 transitions 칸이 없다(옛 placement) — 판 cuts.transition.kinds 는 placement.place 가 자리를 정해야 그려진다")
    return [{"t": t, "kind": "flash", "ms": round(fsec * 1000), "sec": fsec, "why": "placement flashes(옛 키)"} for t in placed.get("flashes") or []]


def flash_color_of(e: dict, st: dict, cnt: list) -> dict:
    """번쩍 두 종류의 색·세기(표준 §11-6 ㉝ — 그리기 정본 = render_bench).
    flash = 창 전체 색 덮기(벤치 실측: 경계 프레임 α → ms 뒤 0, 선형). 색 = 사건 칸 rgb(자리·색 = placement 03) > 판 cuts.transition.flash.colors(사건 차례 돌림),
      α = 사건 alpha > 판 flash.alpha. 둘 다 색이 없으면 {} = 옛 흰 번쩍(화면 전체 밝히기, 그림 그대로 — 흰 번쩍은 이 경우).
    edge_glow = 가장자리 빛(사장님 R4 — shark/fx.py 에서 옮김) · 업그레이드 판 전용(판에 base 가 없으면 멈춘다). 칸 = 판 cuts.transition.edge_glow
      {alpha0, dur, clear, soft, tint, bright{luma,alpha_gain}, colors} · 색 = 사건 rgb > colors 돌림. 빠진 칸은 멈춘다(숨은 기본 금지)."""
    k = e.get("kind")
    C = ((st.get("cuts") or {}).get("transition") or {}).get(k) or {}
    cols = C.get("colors")
    rgb = e.get("rgb") or (cols[cnt[0] % len(cols)] if cols else None)
    if rgb is not None and not e.get("rgb"):
        cnt[0] += 1
    if k == "flash":
        if rgb is None:
            return {}
        alpha = e.get("alpha", C.get("alpha"))
        if alpha is None:
            raise StageError(f"flash {e.get('t')} 색 {rgb} 에 alpha 가 없다 — 사건 칸 또는 판 cuts.transition.flash.alpha")
        return {"rgb": [int(v) for v in rgb], "alpha": float(alpha)}
    if not st.get("base"):
        raise StageError(f"edge_glow({e.get('t')}) 는 업그레이드 판 전용(표준 §11-6 ㉝, 벤치에 없음) — 판 '{st.get('name')}' 은 1차 판(base 없음)")
    miss = [x for x in ("alpha0", "dur", "clear", "soft", "tint") if C.get(x) is None]
    if rgb is None or miss:
        raise StageError(f"edge_glow({e.get('t')}) 칸 모자람 {miss + ([] if rgb is not None else ['rgb/colors'])} — 판 cuts.transition.edge_glow")
    return {"rgb": [int(v) for v in rgb], "edge": {x: C[x] for x in ("alpha0", "dur", "clear", "soft", "tint", "bright") if C.get(x) is not None}}


# ── 가장자리 빛(edge_glow) — tools/calcopy/shark/fx.py(_edge_mask·flash_look·flash_image·pose flash edge)를 인자 그대로 옮김(㉝) ──
def edge_mask(w: int, h: int, clear: float, soft: float):
    """번쩍 가장자리 빛 모양(0~1) — 타원 거리 clear 안쪽 0, 가장자리 1(부드럽게). = shark fx._edge_mask(rules flash.clear·soft)."""
    import numpy as np
    ys, xs = np.mgrid[0:h, 0:w]
    dd = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2) / math.sqrt(2)   # 모서리 = 1, 변 가운데 = 0.71
    c0 = clear * 0.7071
    u = np.clip((dd - c0) / max(1e-6, (0.7071 - c0) * (1 + soft)), 0, 1)
    return (u * u * (3 - 2 * u)).astype(np.float32)


def edge_look(luma, tint: float, bright: dict | None) -> tuple[float, float]:
    """장면 밝기 luma(0~255, 없으면 None) → (tint, α 배율) = shark fx.flash_look(rules flash.bright)."""
    if luma is None or not bright:
        return tint, 1.0
    u = min(1.0, max(0.0, (luma - bright["luma"][0]) / (bright["luma"][1] - bright["luma"][0])))
    return tint * (1 - u), 1.0 + bright["alpha_gain"] * u


def edge_glow_image(rgb, alpha: float, w: int, h: int, clear: float, soft: float, tint: float):
    """가장자리 빛 한 장(PIL RGBA, 곧은 알파) = shark fx.flash_image(style edge)."""
    import numpy as np
    from PIL import Image
    col = np.array(rgb, float)
    col = col + (255 - col) * tint
    a = (edge_mask(w, h, clear, soft) * alpha * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([np.broadcast_to(col.astype(np.uint8), (h, w, 3)), a]), "RGBA")


def edge_glow_alpha(dt: float, alpha0: float, dur: float) -> float:
    """사건 시작에서 dt 초 뒤 α = alpha0·(1−u)², u = dt/dur(감속으로 사라짐) = shark fx.pose(flash edge)."""
    u = min(1.0, dt / dur)
    return max(0.0, alpha0 * (1 - u) ** 2)


def edge_scene_luma(video: Path, t: float, w: int, h: int, clear: float, soft: float) -> float | None:
    """번쩍 얹기 전 창 영상의 그 시각(+0.02초) 가장자리(mask>0.5) 평균 밝기 = shark fx.flash_scene_luma."""
    import numpy as np
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t + 0.02:.3f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    if len(raw) != w * h * 3:
        return None
    f = np.frombuffer(raw, np.uint8).reshape(h, w, 3)[edge_mask(w, h, clear, soft) > 0.5].astype(float)
    return round(float((f @ np.array([0.299, 0.587, 0.114])).mean()), 1)


def flash_layers(trans: list[dict], rect, R: Path, ins: list, last: str, n: int, win_video: Path | None) -> tuple[str, str]:
    """창 자리에 색 번쩍(flash+rgb)·가장자리 빛(edge_glow)을 얹는 식 조각(render_base — 꾸밈 스티커 위·자막 아래, shark rules flash.order 와 같음).
    반환 (덧붙일 filter_complex 조각, 끝 이름). 색 없는 flash(옛 흰 번쩍)는 여기서 안 그린다(render_base 옛 길)."""
    x, y, ww, wh = rect
    fc = ""
    for j, e in enumerate(e for e in trans if e["kind"] == "flash" and e.get("rgb")):
        n0 = round(e["t"] * FPS)
        k = max(1, round(e["ms"] / 1000 * FPS))
        hexc = "".join(f"{v:02X}" for v in e["rgb"])
        fc += (f";color=c=0x{hexc}:s={ww}x{wh}:r={FPS}:d={k / FPS:.4f},format=rgba,"
               f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='255*{e['alpha']:.3f}*(1-N/{k})',setpts=PTS-STARTPTS+{n0}/({FPS}*TB)[cf{j}];"
               f"[{last}][cf{j}]overlay={x}:{y}:eof_action=pass:enable='between(n,{n0},{n0 + k - 1})'[cfo{j}]")
        last = f"cfo{j}"
    eg = [e for e in trans if e["kind"] == "edge_glow"]
    if eg:
        import subprocess
        spans = [(round(e["t"] * FPS), min(n, round(e["t"] * FPS) + max(1, round(e["ms"] / 1000 * FPS)))) for e in eg]
        f0, f1 = min(a for a, _ in spans), max(b for _, b in spans)
        for e in eg:
            E = e["edge"]
            e["scene_luma"] = edge_scene_luma(win_video, e["t"], ww, wh, E["clear"], E["soft"]) if win_video else None
        out = R / "edge_glow.mov"
        pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{ww}x{wh}", "-r", str(FPS), "-i", "-",
                               "-c:v", "qtrle", str(out)], stdin=subprocess.PIPE)
        from PIL import Image
        for f in range(f0, f1):
            cv = Image.new("RGBA", (ww, wh), (0, 0, 0, 0))
            for e, (a, b) in zip(eg, spans):
                if a <= f < b:
                    E = e["edge"]
                    tint, gain = edge_look(e["scene_luma"], E["tint"], E.get("bright"))
                    al = edge_glow_alpha((f - a) / FPS, E["alpha0"], E["dur"])
                    cv.alpha_composite(edge_glow_image(e["rgb"], round(min(1.0, al * gain), 3), ww, wh, E["clear"], E["soft"], round(tint, 3)))
            pr.stdin.write(cv.tobytes())
        pr.stdin.close()
        if pr.wait() != 0:
            raise StageError("가장자리 빛 층 인코딩 실패")
        k = len([a for a in ins if a == "-i"])
        ins += ["-i", out]
        fc += (f";[{k}:v]setpts=PTS-STARTPTS+{f0}/({FPS}*TB)[egl];"
               f"[{last}][egl]overlay={x}:{y}:eof_action=pass:enable='between(n,{f0},{f1 - 1})'[ego]")
        last = "ego"
    return fc, last


def window_fx(trans: list[dict], ww: int, wh: int) -> str:
    """창 안 전환 필터(filter_complex, 입력 [0:v] → [v]). 줌블러 = 경계 ±ms/2 동안 확대 사다리꼴 + gblur 덮기 · 검은 = 경계 프레임부터 ms 만큼 검정.
    그릴 것이 없으면 '' (창 영상을 다시 굽지 않는다 — 장치 끈 판은 그림이 그대로)."""
    zb = [e for e in trans if e["kind"] == "zoomblur"]
    bk = [e for e in trans if e["kind"] == "black"]
    if not (zb or bk):
        return ""
    fc, last = [], "0:v"
    if zb:
        terms = "+".join(f"max(0,1-abs(in/{FPS}-{e['t']:.3f})/{e['ms'] / 2000:.3f})" for e in zb)
        en = "+".join(f"between(t,{max(0.0, e['t'] - e['ms'] / 2000):.3f},{e['t'] + e['ms'] / 2000:.3f})" for e in zb)
        fc.append(f"[0:v]split[zm][zc];[zc]zoompan=z='1+{ZOOMBLUR_ZOOM}*({terms})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                  f"s={ww}x{wh}:fps={FPS},gblur=sigma={ZOOMBLUR_SIGMA}[zb];[zm][zb]overlay=0:0:enable='{en}'[z]")
        last = "z"
    if bk:
        rng = []
        for e in bk:
            n0 = round(e["t"] * FPS)
            k = max(1, round(e["ms"] / 1000 * FPS))
            rng.append(f"between(n,{n0},{n0 + k - 1})")
        fc.append(f"[{last}]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{'+'.join(rng)}'[k]")
        last = "k"
    fc.append(f"[{last}]format=yuv420p[v]")
    return ";".join(fc)


# ── 전환 세기 자(표준 §11-2 ⑯) — 우리 완성본과 벤치를 **같은 함수·같은 마스크 규칙**으로 잰다 ──────────────
TD_BAND_S = 0.1                 # 경계 띠 = 경계 ±0.05초(0.1초 띠)
TD_AROUND = (0.2, 0.4)          # 비교 바탕 = 경계 앞뒤 0.2~0.4초
TD_LOW = 0.7                    # 바탕 대비 분산이 이 비율 밑인 연속 프레임 = 전환이 보이는 길이(ms 실측)
TD_PAD = 8                      # 자막·스티커 상자 테두리(px)


def _gray_seg(video: Path, t0: float, t1: float, crop) -> tuple:
    """[t0,t1) 프레임(회색, crop=[x,y,w,h]) 배열과 그 프레임들의 시각."""
    import subprocess
    import numpy as np
    x, y, w, h = crop
    t0 = max(0.0, t0)
    # 시각 → 프레임은 trim(start_frame) 으로(입력 -ss 는 파일마다 시작 pts 가 달라 한 프레임씩 어긋났다 — 완성본(광고 표시 다시 굽기)↔captioned 마스크가 1프레임 밀림, 10-25 실측)
    f0, f1 = round(t0 * FPS), round(t1 * FPS)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                          f"trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},format=gray", "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
    return fr, [round((f0 + k) / FPS, 4) for k in range(len(fr))]


def _masked_lapvar(fr, mask) -> float:
    import cv2
    import numpy as np
    lap = cv2.Laplacian(fr, cv2.CV_64F)
    keep = ~mask if mask is not None else np.ones(fr.shape, bool)
    return float(lap[keep].var()) if keep.sum() > 1000 else float("nan")


def transition_drop(video: Path, ts: list[float], crop, mask_of=None) -> list[dict]:
    """경계마다 drop = 1 − (경계 ±0.05초 띠 라플라시안 분산 평균)/(앞뒤 0.2~0.4초 바탕 평균) · ms = 바탕의 TD_LOW 밑으로 떨어진 연속 프레임 길이.
    crop = 창 [x,y,w,h](화면 픽셀) · mask_of(t, shape) → bool 배열(True = 빼는 픽셀: 자막 띠·스티커, 테두리 8px 포함) | None.
    우리 완성본·벤치 원본 둘 다 이 함수(⑯ '같은 자'). 품질 관문(04)은 이 함수를 부르면 된다."""
    import numpy as np
    out = []
    for t in ts:
        a0, a1 = TD_AROUND
        fr, tt = _gray_seg(video, t - a1, t + a1, crop)
        if not len(fr):
            continue
        lv = np.array([_masked_lapvar(f, mask_of(ti, f.shape) if mask_of else None) for f, ti in zip(fr, tt)])
        rel = np.array(tt) - t
        band = np.abs(rel) <= TD_BAND_S / 2 + 1e-3
        around = (np.abs(rel) >= a0 - 1e-3) & (np.abs(rel) <= a1 + 1e-3)
        base = float(np.nanmean(lv[around])) if around.any() else float("nan")
        drop = 1 - float(np.nanmean(lv[band])) / base if band.any() and base > 0 else float("nan")
        k0 = int(np.argmin(np.abs(rel)))
        low = lv < TD_LOW * base
        a = b = k0
        if low[k0]:
            while a > 0 and low[a - 1]:
                a -= 1
            while b + 1 < len(low) and low[b + 1]:
                b += 1
            ms = round((b - a + 1) * 1000 / FPS)
        else:
            ms = 0
        out.append({"t": round(t, 3), "drop": round(drop, 3), "ms": ms, "band_var": round(float(np.nanmean(lv[band])), 1), "around_var": round(base, 1)})
    return out


def overlay_mask_of(base: Path, over: Path, crop, pad: int = TD_PAD, th: int = 12):
    """우리 완성본 마스크: 바탕(base.mp4, 자막 없음)과 자막 입힌 영상(captioned.mp4)이 다른 픽셀 = 자막·스티커 → 테두리 pad px 넓혀 뺀다."""
    import cv2
    import numpy as np
    cache = {}
    k = np.ones((2 * pad + 1, 2 * pad + 1), np.uint8)

    def mask_of(t, shape):
        key = round(t * FPS)
        if key not in cache:          # 1초 덩어리로 한 번에 읽어 둔다(프레임마다 영상 열기 금지)
            a, ta = _gray_seg(base, t, t + 1.0, crop)
            b, _ = _gray_seg(over, t, t + 1.0, crop)
            for fa, fb, ti in zip(a, b, ta):
                m = (np.abs(fa.astype(np.int16) - fb.astype(np.int16)) > th).astype(np.uint8)
                cache[round(ti * FPS)] = cv2.dilate(m, k) > 0
        return cache.get(key)
    return mask_of


def rect_mask_of(rects, crop, pad: int = TD_PAD):
    """벤치 마스크: 줄판독 자막 띠·스티커 상자 [x0,y0,x1,y1,t0,t1](화면 픽셀·초) → 그 시각에 걸린 상자를 pad px 넓혀 뺀다."""
    import numpy as np
    cx, cy, cw, ch = crop

    def mask_of(t, shape):
        m = np.zeros(shape, bool)
        for x0, y0, x1, y1, a, b in rects:
            if a - 1e-3 <= t < b + 1e-3:
                m[max(0, int(y0) - pad - cy):max(0, int(y1) + pad - cy), max(0, int(x0) - pad - cx):max(0, int(x1) + pad - cx)] = True
        return m
    return mask_of


def bench_transition_drop(line_read: Path, video: Path, kind: str = "zoomblur") -> dict:
    """벤치 한 편: 줄판독 lines[].transition==kind 인 줄 시작 근처(±0.2초) 장면 경계(shot_starts, 없으면 줄 시작)에서 transition_drop.
    마스크 = 줄판독 자막 띠(y)·스티커 상자 · 창 = layout.window(화면 밖은 잘라 냄)."""
    import json as _j
    d = _j.loads(Path(line_read).read_text(encoding="utf-8"))
    x, y, w, h = d["layout"]["window"]
    h = min(h, H - y)
    crop = [x, y, w, h]
    rects = []
    for l in d["lines"]:
        yy = l.get("y")
        if isinstance(yy, list) and len(yy) == 2:
            rects.append([0, yy[0], W, yy[1], l["t0"], l["t1"]])
        for s in l.get("sticker") or []:
            b = s.get("bbox") if isinstance(s, dict) else None
            if isinstance(b, list) and len(b) == 4:
                rects.append([*b, l["t0"], l["t1"]])
    st = shot_starts(Path(video))
    ts = []
    for l in d["lines"]:
        if l.get("transition") == kind:
            near = [s for s in st if abs(s - l["t0"]) <= 0.2]
            ts.append(min(near, key=lambda s: abs(s - l["t0"])) if near else l["t0"])
    return {"id": d.get("id"), "kind": kind, "window": crop, "boundaries": transition_drop(Path(video), ts, crop, rect_mask_of(rects, crop))}


def render_transition_drop(R: Path, style_name: str, kinds=("zoomblur",)) -> dict:
    """우리 완성본 한 편: render/자막표.json transitions(kind) 경계에서 transition_drop — 완성본(final.mp4) 창 영역,
    마스크 = base.mp4(자막 없음) ↔ captioned.mp4 가 다른 픽셀(자막·스티커) + 8px. 벤치(bench_transition_drop)와 같은 함수."""
    from tools.calcopy.hybrid import styles as ST
    R = Path(R)
    st = ST.load(style_name)
    crop = frame_window(st["frame"])
    crop = [crop[0], crop[1], crop[2], min(crop[3], H - crop[1])]
    tab = jload(R / "자막표.json")
    ts = [e["t"] for e in tab.get("transitions") or [] if e["kind"] in kinds]
    return {"style": style_name, "window": crop, "boundaries": transition_drop(R / "final.mp4", ts, crop, overlay_mask_of(R / "base.mp4", R / "captioned.mp4", crop))}


def render_window(T: dict, M: dict, st: dict, R: Path, trans: list[dict] | None = None) -> Path:
    src_dir = Path(M["cand_dir"])
    x, y, ww, wh = frame_window(st["frame"])
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * FPS) - round(c["t0"] * FPS)
        c["frames"] = n
        src = src_dir / c["src"]
        crop = c.get("crop", "face")
        pb = pic_box(c, (ww, wh))          # 컷마다 그림 칸 — 자르기 비율도 그 칸 비율로
        aw, ah = (pb[2], pb[3]) if pb else (ww, wh)
        if src.suffix.lower() in IMG_EXT and not (isinstance(crop, list) and len(crop) == 4):
            # 사진 재료(쿠팡 상품 사진)는 얼굴 크롭·시작 초가 없다 — 창 비율로 가운데를 자른다(10-22 강주은: 사진 컷에 ss·crop 없음 → KeyError 'ss' 로 렌더 멈춤)
            iw, ih = probe(src)[:2]
            cw = min(iw, round(ih * aw / ah)); chh = min(ih, round(cw * ah / aw))
            crop = [(iw - cw) // 2, (ih - chh) // 2, cw, chh]
            c["crop_used"] = crop
        elif crop == "face":
            crop = face_crop(src, float(c.get("ss") or 0.0) + min(0.5, c["dur"] / 2), aw / ah)
            c["crop_used"] = crop
        push = (st.get("cuts") or {}).get("push_orig" if c["kind"] == "orig" else "push_tts", 0.0)
        p = parts / f"c{k:02d}.mp4"
        clip(src, float(c.get("ss", 0.0)), n, crop, (ww, wh), p, push=float(c.get("push", push)), move=c.get("move"),
             blur=(M.get("blur") or {}).get(c["src"]), pic=pb, pic_bg=c.get("pic_bg") or st["frame"].get("bg"))
        got = count_frames(p)
        if got != n:      # 모자라면 뒤 컷이 전부 앞당겨지고 끝이 멈춘다 — 조용히 넘기지 않는다
            raise StageError(f"컷 조각 프레임 모자람: {c['line']} {c['src']}@{c.get('ss')} 계획 {n} · 실제 {got}")
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    win = R / "window.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", win])
    return window_transitions(win, T, st, R, trans)


def window_transitions(win: Path, T: dict, st: dict, R: Path, trans: list[dict] | None) -> Path:
    """창 영상에 전환(줌블러·검은 프레임)을 입힌다 — 그릴 것이 없으면 창 그대로(다시 굽지 않는다)."""
    x, y, ww, wh = frame_window(st["frame"])
    fx = window_fx(trans or [], ww, wh)
    if fx:
        n_all = sum(c["frames"] for c in T["cuts"])
        out = R / "window_tr.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", win, "-filter_complex", fx, "-map", "[v]", "-frames:v", n_all, "-r", FPS,
             *venc(16), "-pix_fmt", "yuv420p", out])
        got = count_frames(out)
        if got != n_all:
            raise StageError(f"전환 입힌 창 프레임 {got} ≠ 계획 {n_all}")
        return out
    return win


FX_STICKERS = ("red_circle", "dashed_circle", "arrow_green_down", "arrow_pink_up", "arrow_curve_red", "money_emoji")   # = tools/calcopy/shark/fx.py KINDS(번쩍·emoji 빼고)


def fx_effects(placed: dict) -> list[dict]:
    """배치가 자리를 받은 꾸밈 스티커(종류·자리 = placement + fx_target, 03) → 샤크 fx 사건 {kind, at:[x,y] 완성본 px, T:[t0,t1], radius?/size?/stroke?}.
    모양·움직임·크기 기본값의 주인 = tools/calcopy/shark/fx.py(sprite·pose·place, 값 rules.json — 샤크탱크 벤치 실측). 자리 못 받은(pending) 것은 안 그림."""
    out = []
    for r in placed.get("rows") or []:
        for s in r.get("stickers") or []:
            if s.get("kind") not in FX_STICKERS or s.get("site") not in ("detected", "fixed") or s.get("x") is None:
                continue
            e = {"kind": s["kind"], "at": [round(float(s["x"]) / 100 * W), round(float(s["y"]) / 100 * H)],
                 "T": [round(float(r["t0"]), 3), round(float(r["t0"]) + float(s.get("len_s", 1.0)), 3)]}
            for k in ("radius", "size", "stroke", "w", "h"):
                if isinstance(s.get(k), (int, float)):
                    e[k] = s[k]
            out.append(e)
    return out


def fx_layer(effects: list[dict], R: Path, n: int) -> tuple[Path, int, int] | None:
    """꾸밈 사건 → 투명 층 mov(1080×1920, 사건이 있는 프레임 구간만) + (첫 프레임, 끝 프레임). 그리기 = shark fx.pose·place·_sprite_im(그 채널 렌더러와 같은 함수)."""
    if not effects:
        return None
    from PIL import Image
    from tools.calcopy.shark import fx as FXS
    f0 = max(0, min(round(e["T"][0] * FPS) for e in effects))
    f1 = min(n, max(round(e["T"][1] * FPS) for e in effects))
    if f1 <= f0:
        return None
    out = R / "fx_layer.mov"
    pr = __import__("subprocess").Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                         "-c:v", "qtrle", str(out)], stdin=__import__("subprocess").PIPE)
    for f in range(f0, f1):
        t = f / FPS
        cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for e in effects:
            p = FXS.pose(e, t)
            if p is None:
                continue
            im = FXS._sprite_im(e["kind"], FXS._key(e), round(p["scale"], 2), round(p["deg"] / 3) * 3.0, round(p["alpha"], 2), round(p["rot"], 1), round(p["sweep"], 3))
            pl = FXS.place(e, p)
            x0, y0 = int(round(pl["cx"] - im.size[0] / 2)), int(round(pl["cy"] - im.size[1] / 2))
            cv.alpha_composite(im, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
        pr.stdin.write(cv.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise StageError(f"꾸밈 층 인코딩 실패 {out}")
    return out, f0, f1


def meme_overlays(placed: dict) -> list[dict]:
    """배치가 자리를 받은 짤(placement meme_step → site detected|fixed) → [{src, t0, len, box[x0,y0,w,h]}]. 자리 못 받은 짤(pending)은 안 그린다."""
    out = []
    for r in placed.get("rows") or []:
        for s in r.get("stickers") or []:
            if s.get("kind") != "meme" or s.get("site") not in ("detected", "fixed") or not s.get("src"):
                continue
            w, h = int(s.get("w") or 420), int(s.get("h") or 420)
            cx, cy = float(s["x"]) / 100 * W, float(s["y"]) / 100 * H
            out.append({"src": s["src"], "t0": float(r["t0"]), "len": float(s.get("len_s", 1.0)), "box": [round(cx - w / 2), round(cy - h / 2), w, h]})
    return out


def _seg_on(g: dict) -> str:
    """구간 켜짐 식 — [t0, t1) 반 프레임 앞당긴 경계(경계 프레임은 뒤 구간 것)."""
    e = 0.5 / FPS
    return f"gte(t,{g['t0'] - e:.4f})*lt(t,{g['t1'] - e:.4f})"


def seg_layers(S: dict, st: dict, segs: list[dict], R: Path, ins: list, base_win, end: float) -> str:
    """구간 틀 합성 식(입력 0 = 검정 바탕 · 1 = 창 영상 · 2 = 판 틀) → 끝 이름 [b]. 구간 밖 = 판 창 자리·판 틀,
    구간 안 = 구간 창 자리(크기가 다르면 창 영상을 채워 자른다 — 창 하나를 다시 굽지 않는다)·구간 틀. ins 에 구간 틀 PNG 입력을 덧붙인다."""
    x, y, ww, wh = base_win
    off = "not(" + "+".join(_seg_on(g) for g in segs) + ")"
    fc = [f"[1:v]split={len(segs) + 1}" + "".join(f"[w{i}]" for i in range(len(segs) + 1)),
          f"[0:v][w0]overlay={x}:{y}:shortest=0:enable='{off}'[a0]"]
    last = "a0"
    for i, g in enumerate(segs, 1):
        sx, sy, sw, sh = g["window"]
        src = f"w{i}"
        if (sw, sh) != (ww, wh):
            fc.append(f"[w{i}]scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,crop={sw}:{sh},setsar=1[ws{i}]")
            src = f"ws{i}"
        fc.append(f"[{last}][{src}]overlay={sx}:{sy}:enable='{_seg_on(g)}'[a{i}]")
        last = f"a{i}"
    fc.append(f"[{last}][2:v]overlay=0:0:enable='{off}'[f0]")
    last = "f0"
    for i, g in enumerate(segs, 1):
        p = seg_frame_png(S, st, g, R / f"frame_seg{i}.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-t", f"{end:.3f}", "-i", p]
        fc.append(f"[{last}][{k}:v]overlay=0:0:enable='{_seg_on(g)}'[f{i}]")
        last = f"f{i}"
    fc.append(f"[{last}]null[b]")
    return ";".join(fc)


def render_base(S: dict, T: dict, st: dict, placed: dict, R: Path, win: Path, trans: list[dict] | None = None, name: str = "base.mp4",
                color: str | None = None) -> Path:
    """틀 + 창 + 댓글 카드 + 짤 + 흰 번쩍임(자막 없는 바탕). 번쩍임 = 전환 목록(transitions_of) kind=flash — 화면 전체.
    짤 = 배치가 검출로 자리를 받은 meme 스티커(자막팩은 짤을 안 그린다 — 여기 한 곳)."""
    F = st["frame"]
    x, y, ww, wh = frame_window(F)
    png = frame_png(S, st, R / "frame.png")
    n = sum(c["frames"] for c in T["cuts"])
    end = n / FPS
    ins = ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={end:.3f}", "-i", win, "-loop", "1", "-t", f"{end:.3f}", "-i", png]
    segs = frame_segments(S, T, st)
    if not segs:
        fc = f"[0:v][1:v]overlay={x}:{y}:shortest=0[a];[a][2:v]overlay=0:0[b]"
    else:
        fc = seg_layers(S, st, segs, R, ins, (x, y, ww, wh), end)
    last = "b"
    C = placed.get("comment")
    if C:
        cw, ch = comment_png(C, F["comment"]["px"], R / "comment.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-t", f"{end:.3f}", "-i", R / "comment.png"]
        fc += f";[b][{k}:v]overlay={(W - cw) // 2}:{F['comment']['bottom'] - ch}:enable='between(t,{C['t0']:.3f},{C['t1']:.3f})'[c]"
        last = "c"
    for j, m in enumerate(meme_overlays(placed)):
        k = len([a for a in ins if a == "-i"])
        mx, my, mw, mh = m["box"]
        ins += ["-i", m["src"]]
        fc += (f";[{k}:v]trim=duration={m['len']:.3f},setpts=PTS-STARTPTS+{m['t0']:.3f}/TB,fps={FPS},"
               f"scale={mw}:{mh}:force_original_aspect_ratio=decrease[mm{j}];"
               f"[{last}][mm{j}]overlay={mx}+({mw}-w)/2:{my}+({mh}-h)/2:eof_action=pass:enable='between(t,{m['t0']:.3f},{m['t0'] + m['len']:.3f})'[m{j}]")
        last = f"m{j}"
    FL = fx_layer(fx_effects(placed), R, n)          # 꾸밈 스티커(빨간 원·점선 원·화살표) — 창·짤 위, 자막 아래(샤크 fx 겹침 순서와 같다)
    if FL:
        k = len([a for a in ins if a == "-i"])
        ins += ["-i", FL[0]]
        fc += (f";[{k}:v]setpts=PTS-STARTPTS+{FL[1]}/({FPS}*TB)[fxl];"
               f"[{last}][fxl]overlay=0:0:eof_action=pass:enable='between(n,{FL[1]},{FL[2] - 1})'[fxo]")
        last = "fxo"
    trs = trans if trans is not None else transitions_of(T, st, placed)
    add, last = flash_layers(trs, (x, y, ww, wh), R, ins, last, n, win)
    fc += add
    fl = [(e["t"], e["sec"] if "sec" in e else e["ms"] / 1000) for e in trs if e["kind"] == "flash" and not e.get("rgb")]     # 옛 흰 번쩍(색 없는 flash)
    if fl:
        e = "+".join(f"between(T,{t:.3f},{t + dsec:.3f})*(1-(T-{t:.3f})/{dsec})" for t, dsec in fl)
        fc += f";[{last}]geq=lum='min(255,lum(X,Y)+255*({e}))':cb='cb(X,Y)':cr='cr(X,Y)'[f]"
        last = "f"
    out = R / name
    cf = f"{color.strip()}," if color and color.strip() else ""          # 모션그래픽팩 색감(자막 전 — 고객 엔진 video_assemble 과 같은 순서)
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc + f";[{last}]{cf}format=yuv420p[v]", "-map", "[v]", "-frames:v", n, "-r", FPS,
         *venc(16), out])
    return out


# ── 자막(자막팩 길) ──────────────────────────────────────────────────────
PACK_XY_KINDS = ("circle_arrow", "object_pop", "hearts", "sound_word", "small_text")   # 자막팩 그리기(out/precision20-ui.js renderStickers)가 s.x·s.y 를 읽는 종류(10-25 코드 실측) — 나머지(gem·spark_lines·kk_doodle·comic_burst·aside_line·append_text·comment_card)는 자막·낱말 기준 고정 자리
STACK_BREAKS = ("full", "line")


def stack_rows(rows: list[dict], st: dict) -> list[dict]:
    """자막 쌓기(관제 263 02 2차 ③ — 누적형 방구석·맛템·썰템쇼): 판 칸 caption.stack{lines(2~3), break full|line}.
    덩어리마다 앞 덩어리 밑에 한 줄씩 덧붙여(글 = '앞줄\n새줄') lines 줄이 차면 다음 덩어리에서 페이지를 지우고 새로 시작.
    break=line 이면 대본 줄(문장)이 바뀔 때도 지운다(맛템: 문장 단위 누적). 칸 없으면 그대로(한 줄 교체, 옛 그림).
    y(첫 줄 가운데 px)·pitch(줄 간격 px)를 적으면 첫 줄이 제자리에 서고 새 줄이 밑으로 붙는다 — 자막팩은 여러 줄 덩어리를 가운데 기준으로
    세우므로(10-25 실측: clean 팩 place y = 덩어리 가운데) 쌓인 줄 수 k 마다 place y = y + (k−1)·pitch/2. 안 적으면 팩 자리(덩어리 가운데 기준).
    쌓인 줄의 타이핑 글자 시각은 버린다(새 줄만 치는 표현은 자막팩 몫 — 벤치 셋 다 typing 0)."""
    SK = (st.get("caption") or {}).get("stack")
    if not SK:
        return rows
    n = int(SK.get("lines", 1))
    brk = SK.get("break", "full")
    if brk not in STACK_BREAKS or not 2 <= n <= 4 or (SK.get("y") is None) != (SK.get("pitch") is None):
        raise StageError(f"caption.stack {SK} — lines 2~4 · break {STACK_BREAKS} · y·pitch 는 짝")
    page, prev = [], None
    for r in rows:
        if len(page) >= n or (brk == "line" and prev is not None and r["line"] != prev):
            page = []
        page.append(r["text"])
        r["text"] = "\n".join(page)
        r["stack"] = len(page)
        if SK.get("y") is not None:
            r["place"] = {"x": 50, "y": round((float(SK["y"]) + (len(page) - 1) * float(SK["pitch"]) / 2) / H * 100, 3)}
        if len(page) > 1:
            r.pop("chars", None)
        prev = r["line"]
    return rows


def caption_hidden(rows: list[dict], segs: list[dict]) -> list[dict]:
    """구간 틀 captions=hide 구간의 자막을 뺀다(frame_segments 가 주인) — 구간 안에서 **시작한** 덩어리는 통째로 뺀다(그 말은 훅 카드 띠가 대신했다.
    끝만 잘라 남기면 구간 끝에 몇 프레임 번쩍 뜬다 — 10-25 _test_hook 실측 3.533~3.607초 2프레임) · 구간 앞에서 시작해 걸치면 구간 시작에서 내린다."""
    hide = [(g["t0"], g["t1"]) for g in segs if g["captions"] == "hide"]
    if not hide:
        return rows
    out = []
    for r in rows:
        a, b = r["t0"], r["t1"]
        if any(h0 - 1e-3 <= a < h1 - 1e-3 for h0, h1 in hide):
            continue
        for h0, h1 in hide:
            if a < h0 < b:
                b = h0
        if b - a < 1 / FPS:
            continue
        r = {**r, "t1": round(b, 3)}
        if r.get("chars"):
            r["chars"] = [c for c in r["chars"] if c < b]
        out.append(r)
    return out


def caption_rows(placed: dict, st: dict, segs: list[dict] | None = None) -> list[dict]:
    """배치 결과 → 자막팩 견본(check_bench_packs.rows_to_timeline) 공통 줄 꼴. 타이핑 덩어리는 글자 시각(판 caption.typing_cps).
    segs(frame_segments) 의 captions=hide 구간은 빼고, 판 caption.stack 이면 쌓는다."""
    cps = float(st["caption"].get("typing_cps", 10.0))
    out = []
    for r in placed["rows"]:
        a, b = r["show"]
        row = {"line": r["line"], "t0": a, "t1": b, "text": r["text"], "speaker": r["speaker"], "variant": r.get("variant") or "",
               "emph": r.get("emph") or [], "sticker": "", "stickers": [], "enter": r.get("enter") or "instant"}   # enter = 검증 자(kal_analyze)가 등장을 잰다
        for s in r.get("stickers") or []:
            if s["kind"] == "heart":
                row["sticker"] = "heart"
            elif s["kind"] not in ("comment_card", "meme") + FX_STICKERS and s.get("site") != "pending":   # 짤·꾸밈 스티커 = render_base · 자리 못 받은 것 = 안 그림(눈대중 금지, 03)
                if s.get("site") in ("detected", "fixed") and s["kind"] not in PACK_XY_KINDS:
                    # 배치가 자리(x·y)를 정했는데 자막팩 그리기(편집기 renderStickers)가 이 종류는 x·y 를 안 읽고 자막 옆 고정 자리에 그린다 →
                    # 엉뚱한 곳에 그리느니 안 그린다(10-25 15 ep13: kk_doodle 자리 91.5%·60.7% 인데 화면 x240~555). 편집기 쪽 수리 = 그 파일 주인.
                    placed.setdefault("log", []).append(f"스티커 {s['kind']} 자리 {s.get('x')}%·{s.get('y')}% — 자막팩이 이 종류는 자리(x·y)를 안 읽어 안 그림({r['line']})")
                    continue
                row["stickers"].append({k: v for k, v in s.items() if k != "follow"})
        if r["enter"] == "typing":
            n = len(r["text"].replace(" ", ""))
            step = min(1.0 / cps, (b - a) * 0.85 / max(1, n))
            row["chars"] = [round(a + k * step, 3) for k in range(n)]
        out.append(row)
    return pack_place_x(stack_rows(caption_hidden(out, segs or []), st), st)


def caption_packs() -> dict:
    """자막팩 계약 파일(shopping_shorts/static/caption-motions.js /*PACKS*/ 사이 json) — 자막 모양의 주인(표준 ㉑)."""
    t = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
    return json.loads(t.split("/*PACKS*/")[1])


def pack_place_x(rows: list[dict], st: dict, packs: dict | None = None) -> list[dict]:
    """자막팩 가로 자리 place.x(화면 %, 자막 가운데)를 줄마다 place 표식으로 싣는다 — 편집기 renderCaption 은 가로 자리를 장면 place.x 에서만 읽어
    팩 place.x 가 렌더에 안 먹었다(10-25 자막팩 작업자 보고). 우선 = 줄 변형(variants) > 화자(speakers) > 팩. 팩에 x 가 없으면 아무것도 안 바꾼다
    (장면 자리 표식은 y 가 함께여야 받아지므로 y = 쌓기(stack)가 정한 y, 없으면 팩 place.y — 팩 세로 자리와 같다)."""
    P = (packs if packs is not None else caption_packs()).get((st.get("caption") or {}).get("pack")) or {}

    def get(r, k):
        for sec, key in (("variants", r.get("variant")), ("speakers", r.get("speaker"))):
            pl = (((P.get(sec) or {}).get(key) or {}) if key else {}).get("place") or {}
            if isinstance(pl.get(k), (int, float)):
                return float(pl[k])
        pl = P.get("place") or {}
        return float(pl[k]) if isinstance(pl.get(k), (int, float)) else None
    for r in rows:
        x = get(r, "x")
        if x is None:
            continue
        y = (r.get("place") or {}).get("y")
        y = y if isinstance(y, (int, float)) else get(r, "y")
        if y is None:      # 장면 자리 표식은 y 가 있어야 받아진다(scene_style 줄 자리 칸) — x 만 있는 팩은 그릴 수 없다
            raise StageError(f"자막팩 '{st['caption'].get('pack')}' place.x 만 있고 y 가 없다 — 팩에 place.y 를 같이 적는다")
        r["place"] = {**(r.get("place") or {}), "x": x, "y": y}
    return rows


def snapshot(st: dict) -> dict:
    """자막 스냅샷 — 팩 칸(captionPack·motionPack)의 주인 = pack_map.snapshot_fields(st)(판 packs, 지시서 11).
    모션그래픽팩(packs.motion.graphics)은 스냅샷 칸이 아니라 motion_graphics() 가 그린다 — snapshot_fields 의 'graphics≠off 거절'은
    render_bench 에 그리는 길이 없던 때의 막이라, 여기서는 graphics 를 뺀 판으로 팩 칸만 받는다(그리는 길 = motion_graphics, 02 2차)."""
    from shopping_shorts import scene_style
    from tools.calcopy.hybrid import pack_map as PM
    P = st.get("packs") or {}
    st2 = {**st, "packs": {**P, "motion": {**(P.get("motion") or {}), "graphics": "off"}}} if P else st
    fields = PM.snapshot_fields(st2)
    return scene_style.validate_snapshot({"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "body",
                                          "frameRule": "body_all", "text": {"channel": "", "hook1": "", "hook2": "", "bodyTitle": ""},
                                          "captionPack": fields["captionPack"], "motionPack": fields["motionPack"],
                                          "wordFx": {"style": "mark", "color": "", "grow": ""}})


def motion_graphics(st: dict, T: dict) -> dict | None:
    """모션그래픽팩(packs.motion.graphics — 전환 swipe·sparkle 겹·색감) 그리기 재료. 판단 주인은 고객 엔진과 같은 함수들:
    motion_packs.build_plan(팩 + 비트 시간표 → 레이어·색감) · motion_assets.resolve_layers(자산 실경로) · 그리기 = video_assemble._motion_layer_filters.
    비트 = 대본 줄(나레·원음·자막 줄 시작~끝 — mix_pipeline 의 비트와 같은 '말 덩어리'). off 면 None(옛 그림 그대로).
    자막 효과(caption.effect)·헤드카피 노출은 mix 의 drawtext 자막 칸이라 bench(자막팩)에는 해당 없음 → 로그 칸에 남긴다."""
    g = ((st.get("packs") or {}).get("motion") or {}).get("graphics", "off")
    if not g or g == "off":
        return None
    from shopping_shorts.motion_assets import resolve_layers
    from shopping_shorts.motion_packs import build_plan, load_packs
    pk = load_packs().get(g)
    if not pk:
        raise StageError(f"모션그래픽팩 '{g}' 없음 — shopping_shorts/assets/motion/packs.json")
    beats = [{"t0": a, "dur": round(b - a, 3)} for a, b in sorted(T["lines"].values())]
    plan = build_plan(pk, beats)
    layers = resolve_layers(plan["layers"])
    if len(layers) != len(plan["layers"]):        # resolve_layers 는 자산 없으면 조용히 건너뛴다 — 여기서는 멈춘다(조용한 빠짐 금지)
        raise StageError(f"모션그래픽팩 '{g}' 자산 {len(plan['layers']) - len(layers)}개 파일 없음 — assets/motion/manifest.json")
    return {"id": g, "layers": layers, "color_filter": plan["color_filter"],
            "not_drawn": {k: plan[k] for k in ("caption_effect", "headcopy_enable") if plan.get(k)}}


def draw_motion_layers(video: Path, MG: dict | None, R: Path) -> Path:
    """자막 입힌 영상 위에 모션그래픽 레이어(전환·스티커) — 고객 엔진과 같은 순서(자막 다음, video_assemble 의 has_motion 자리)·같은 함수."""
    if not MG or not MG["layers"]:
        return video
    from shopping_shorts.video_assemble import _motion_layer_filters
    m_in, m_fc, vcur, _ = _motion_layer_filters(MG["layers"], 1, "0:v")
    out = R / "captioned_mg.mp4"
    n = count_frames(video)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, *m_in, "-filter_complex", ";".join(m_fc) + f";[{vcur}]format=yuv420p[v]", "-map", "[v]",
         "-frames:v", n, "-r", FPS, *venc(16), out])
    got = count_frames(out)
    if got != n:
        raise StageError(f"모션그래픽 입힌 영상 프레임 {got} ≠ {n}")
    return out


def burn_captions(base: Path, rows: list[dict], st: dict, R: Path, end: float) -> Path:
    from shopping_shorts import scene_style
    from tools.caption_pack.check_bench_packs import rows_to_timeline
    tts = R / "silence.wav"
    if not tts.exists():
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", "1", tts])
    tl = rows_to_timeline(rows, tts, end)
    jsave(R / "caption_timeline.json", tl)
    out = R / "captioned.mp4"
    shutil.rmtree(R / "cw", ignore_errors=True)
    scene_style.compose(str(base), tl, snapshot(st), str(out), R / "cw", {"text": ""})
    return out


# ── 소리 ────────────────────────────────────────────────────────────────
def audio(S: dict, M: dict, st: dict, T: dict, sent: list[dict], placed: dict, R: Path) -> tuple[Path, dict]:
    src_dir = Path(M["cand_dir"])
    end = T["end"]
    pieces = []
    for s in sent:
        pieces.append((s["wav"], T["lines"][s["id"]][0], "narr"))
    for k, p in enumerate(T["opos"]):
        a, b = p["span"]
        w = R / f"o_{k}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src_dir / p["src"], "-vn", "-ac", "1", "-ar", SR,
             "-af", f"highpass=f=90,afade=t=in:d=0.015,afade=t=out:st={max(0, b - a - 0.02):.3f}:d=0.02", w])
        pieces.append((str(w), p["t0"], "orig"))

    def cat(kind):
        ps = [p for p in pieces if p[2] == kind]
        if not ps:
            return None, float("nan")
        o = R / f"cat_{kind}.wav"
        run(["ffmpeg", "-y", "-v", "error", *[x for p in ps for x in ("-i", p[0])], "-filter_complex",
             "".join(f"[{i}:a]" for i in range(len(ps))) + f"concat=n={len(ps)}:v=0:a=1[o]", "-map", "[o]", "-ar", SR, o])
        return o, lufs(o)[0]
    _, nI = cat("narr")
    _, oI = cat("orig")
    og = round(nI - oI, 2) if not math.isnan(oI) and not math.isnan(nI) else 0.0      # 원음 = 나레와 같은 크기
    voice = R / "voice.wav"
    if pieces:
        ins, fc = [], []
        for k, (p, t, kind) in enumerate(pieces):
            ins += ["-i", p]
            fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,volume={og if kind == 'orig' else 0}dB,adelay={int(round(t * 1000))}[p{k}]")
        fc.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{end:.3f}[n]")
        run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", SR, voice])
    else:          # 나레도 원음도 없는 편(자막 줄만) — 목소리 자리는 무음, 소리는 배경음·효과음뿐
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{end:.3f}", voice])
    B = st["bgm"]
    bgm = BGM_DIR / f"{S.get('bgm', {}).get('id') or B['id']}.mp3"
    bI = lufs(bgm)[0]
    # 배경음 크기 기준 = 나레 크기(옛 그대로). 나레 없는 편(관제 263 02 2차 ②)은 원음 크기, 원음도 없으면 판 목표 음량(마스터가 어차피 맞춘다)
    ref = nI if not math.isnan(nI) else (oI if not math.isnan(oI) else float(st["loudness"]["lufs"]))
    g = round((ref - B["db_below_voice"]) - bI, 2)
    k = 10 ** (float(B.get("duck_orig_db", 0.0)) / 20)
    duck = "+".join(f"between(t,{p['t0']:.3f},{p['t1']:.3f})" for p in T["opos"]) or "0"
    vol = f"if({duck},{k:.4f},1)"
    dn = float(B.get("duck_narr_db") or 0.0)          # 나레 덕킹(A4) — 말할 때 BGM 을 더 줄인다. 0 = 없음(식이 예전과 같다)
    narr_spans = [T["lines"][s["id"]] for s in sent]
    if dn:
        nduck = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in narr_spans) or "0"
        vol = f"if({duck},{k:.4f},if({nduck},{10 ** (dn / 20):.4f},1))"
    bed_chain = (f"aresample={SR},aformat=channel_layouts=mono,atrim=0:{end:.3f},asetpts=PTS-STARTPTS,volume={g}dB,"
                 f"volume='{vol}':eval=frame,afade=t=out:st={end - B.get('fade_out', 0.4):.3f}:d={B.get('fade_out', 0.4)}")
    bed = R / "bgm_bed.wav"       # BGM 만(나레·원음·효과음 없이) — 덕킹 실측·품질 관문이 읽는다
    run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", bgm, "-filter_complex", f"[0:a]{bed_chain}[b]", "-map", "[b]", "-ar", SR, bed])
    ins2 = ["-i", voice, "-stream_loop", "-1", "-i", bgm]
    fc2 = [f"[1:a]{bed_chain}[b]"]
    mix_in = "[0:a][b]"
    SF = st.get("sfx_files") or {}
    check_sfx(st, placed)
    for j, e in enumerate(placed.get("sfx") or []):
        f = SFX_DIR / SF[e["kind"]]
        ins2 += ["-i", f]
        fc2.append(f"[{j + 2}:a]aresample={SR},aformat=channel_layouts=mono,volume={SF.get('gain_db', -8)}dB,adelay={int(round(e['t'] * 1000))}[s{j}]")
        mix_in += f"[s{j}]"
    n_in = 2 + len(placed.get("sfx") or [])
    fc2.append(f"{mix_in}amix=inputs={n_in}:normalize=0:duration=first[o]")
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-v", "error", *ins2, "-filter_complex", ";".join(fc2), "-map", "[o]", "-ar", SR, raw])
    mix = R / "mix.wav"
    loud(raw, mix, st["loudness"])
    return mix, {"narr_lufs": nI, "orig_lufs": oI, "orig_gain": og, "bgm_gain": g, "bgm_ref": "narr" if not math.isnan(nI) else ("orig" if not math.isnan(oI) else "target"), "mix": lufs(mix),
                 "duck_narr_db": dn, "bed": bed_contrast(bed, narr_spans, [[p["t0"], p["t1"]] for p in T["opos"]], end)}


def check_sfx(st: dict, placed: dict):
    """배치가 고른 효과음 종류가 판 sfx_files(= packs.sfx, 지시서 11)에 다 있고 파일도 있나 — 없으면 멈춘다.
    옛 코드는 없는 종류를 '팩01/<종류>.wav' 로 조용히 대신 넣었다(판이 고른 팩이 아닌 소리가 나간다 — 0순위 조용한 되돌아가기)."""
    SF = st.get("sfx_files") or {}
    kinds = sorted({e["kind"] for e in placed.get("sfx") or []})
    miss = [k for k in kinds if k not in SF]
    if miss:
        raise StageError(f"효과음 종류 {miss} 가 판 sfx_files 에 없다(있는 것 {sorted(k for k in SF if k not in ('gain_db', 'why'))}) — "
                         f"packs.sfx 에 종류→파일을 적는다(pack_map, 지시서 11). 옛 '팩01/<종류>.wav' 대신 넣기는 없앴다")
    nofile = [k for k in kinds if not (SFX_DIR / SF[k]).exists()]
    if nofile:
        raise StageError(f"효과음 파일 없음: {[(k, SF[k]) for k in nofile]}")


def bed_contrast(bed: Path, narr: list, orig: list, end: float) -> dict:
    """BGM 만 뽑은 트랙의 구간별 크기(RMS dBFS) — 나레 구간 · 원음 구간 · 빈 구간(둘 다 아님). 끝 페이드 0.5초는 뺀다."""
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(bed), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    x = np.frombuffer(raw, np.float32)
    t = np.arange(len(x)) / 16000.0
    def mask(spans):
        m = np.zeros(len(x), bool)
        for a, b in spans:
            m |= (t >= a) & (t < b)
        return m
    mn, mo = mask(narr), mask(orig)
    live = t < end - 0.5
    def db(m):
        m = m & live
        return round(float(10 * np.log10(np.mean(x[m] ** 2) + 1e-12)), 2) if m.sum() > 1600 else None
    out = {"narr_db": db(mn), "orig_db": db(mo), "gap_db": db(~mn & ~mo)}
    out["narr_vs_gap"] = round(out["narr_db"] - out["gap_db"], 2) if out["narr_db"] is not None and out["gap_db"] is not None else None
    return out


def loud(src: Path, dst: Path, L: dict):
    """2단 loudnorm(측정 → 선형 맞춤) — 판 설정 loudness(−14 LUFS · TP).
    올릴 양만큼 최고점이 TP 를 넘으면 ffmpeg 가 선형을 버리고 동적으로 가 목표에 못 미친다(김나영 꿀템노트판 −21.6/−0.8 → −15.2).
    그때는 먼저 올리고 리미터로 최고점을 눌러 둔 뒤 선형 맞춤."""
    import json as _j
    I, TP = L["lufs"], L["tp"]
    pi, ptp = lufs(src)
    if ptp + (I - pi) > TP:
        pre = Path(dst).with_name(Path(dst).stem + "_lim.wav")
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af",
             f"volume={I - pi:.2f}dB,alimiter=limit={10 ** ((TP - 1.0) / 20):.4f}:attack=2:release=50:level=disabled", "-ar", SR, pre])
        src = pre
    m = run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm=I={I}:TP={TP}:LRA=11:print_format=json", "-f", "null", "-"], check=False).stderr
    j = _j.loads(m[m.rindex("{"):m.rindex("}") + 1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample={SR}")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", af, "-ar", SR, dst])


# ── 전체 ────────────────────────────────────────────────────────────────
def needs_locate(st: dict) -> bool:
    """판 배치 규칙에 검출 자리(target = face|object|caption_side)를 받는 스티커·짤이 있나 — 없으면 검출 영상을 안 만든다."""
    Rl = (st.get("placement") or {}).get("rules") or {}
    if any(isinstance(r, dict) and isinstance(r.get("target"), str) for r in (Rl.get("stickers") or {}).values()):
        return True
    Mm = Rl.get("meme")
    return bool(Mm and float(Mm.get("rate", 0)) > 0 and not isinstance(Mm.get("target"), dict))


def make_locate(S: dict, T: dict, st: dict, R: Path, win: Path, log=print):
    """placement.place(locate=…) 에 꽂을 자리 검출기(주인 = fx_target.locator/find). 검출 화면 = 틀+창(자막·전환 없이) detect_base.mp4.
    caption_side 는 판 칸 caption.band(y0,y1 — 자막 띠)가 있어야 한다. 크기 = 판 규칙 size([w,h]) · 없으면 스티커 160 · 짤 420."""
    if not needs_locate(st):
        return None
    from tools.calcopy.hybrid import fx_target as FX
    det = render_base(S, T, st, {}, R, win, [], name="detect_base.mp4")
    Rl = st["placement"].get("rules") or {}
    band = (st.get("caption") or {}).get("band")

    def size_of(s):
        rule = Rl.get("meme") if s.get("kind") == "meme" else (Rl.get("stickers") or {}).get(s.get("kind")) or {}
        return tuple((rule or {}).get("size") or ((420, 420) if s.get("kind") == "meme" else (160, 160)))
    loc = FX.locator(det, win=frame_window(st["frame"]), caption_band=tuple(band) if band else None, size_of=size_of)

    def locate(target, row, s):
        try:
            return loc(target, row, s)
        except ValueError as e:        # caption_side 인데 caption.band 없음·object 인데 무엇(what) 없음 → 안 붙인다(조용히 넘기지 않고 로그)
            log(f"[자리] {s.get('kind')} {target.get('kind')} 검출 못 함: {e}")
            return None
    return locate


def plan_rows(S: dict, T: dict, st: dict, locate=None) -> dict:
    """배치(placement.place) — 씨앗 = 편 slug(같은 편은 늘 같은 배치). locate = make_locate(스티커·짤 자리 검출, 없으면 자리는 pending)."""
    from tools.calcopy.hybrid import placement as PL
    placed = PL.place(T["rows"], st, S.get("slug") or "x", cuts=T["cuts"], locate=locate)      # 전환·효과음 자리 = 화면 컷 경계(03)
    for r, t in zip(placed["rows"], T["rows"]):
        r["show"] = t["show"]
    # 댓글 카드 = 배치가 고르고(벤치 편 비율) 대본에 원본 댓글이 있을 때만
    C = S.get("comment")
    rule = (st["placement"]["rules"].get("stickers") or {}).get("comment_card")
    cnt = (st["placement"].get("counted") or {}).get("stickers", {}).get("comment_card", {})
    share = cnt if isinstance(cnt, (int, float)) else cnt.get("videos", rule.get("share", 0.6) if isinstance(rule, dict) else 0.6)
    if C and rule and PL._chance(S.get("slug") or "x", "sticker:comment_card") < float(share):   # counted 는 비율 숫자로 올 때도 있다(꿀템노트판 10-23)
        t0 = T["lines"][C["from"]][0] if C.get("from") in T["lines"] else T["end"] / 2
        t1 = T["end"] if C.get("to", "end") == "end" else T["lines"][C["to"]][0]
        placed["comment"] = {**C, "t0": t0, "t1": t1}
        placed["log"].append(f"댓글 카드 {t0:.2f}~{t1:.2f}")
    return placed


# ── 나레 합성 줄 캐시(결정 ㉗ '바뀐 줄만 재합성') — 합성 주인은 그대로 engine/narr_align.synth_cached(돈 드는 곳 한 곳) ──────────────
TTS_LINE_GAP = 0.25        # 줄 합성본을 이어 붙일 때 줄 사이 무음(초) — 전체 한 번 합성의 문장 끝 쉼 자리. 뒤 make_sentences 가 줄 경계를 글자 시각으로 다시 자른다


def tts_by_line(S: dict, R: Path, log=print) -> tuple[Path, dict | None]:
    """나레 합성(narr_full.mp3 + 글자 시각)을 줄 캐시로. 반환은 RI.tts_once 와 같은 꼴(그 뒤 make_sentences 는 그대로).
      ① 전체 캐시(narr_full.mp3 사이드카 열쇠 = 전체 글·목소리·배속)가 맞으면 그대로 쓴다(옛 렌더와 같은 소리 — 회귀 0) + 줄 캐시로 쪼개 저장.
      ② 안 맞는데 줄 캐시가 하나도 없으면(새 대본) 옛처럼 전체 1회 합성(RI.tts_once) + 줄 캐시로 쪼개 저장.
      ③ 줄 캐시가 하나라도 있으면 바뀐 줄만 합성(synth_cached, 열쇠 = 목소리·줄 글·배속·모델)하고 줄들을 이어 narr_full 을 다시 만든다(사이드카 열쇠 = 새 전체 글).
    줄 캐시 = R/tts_lines/<열쇠>.mp3(+ .tts.json, align = 그 줄 글자 시각)."""
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid import render_itssum as RI
    voice, tempo = S["voice"]["voice_id"], S["voice"].get("tempo")
    full = R / "narr_full.mp3"
    LD = R / "tts_lines"
    lines = [l for l in S["lines"] if l["kind"] == "tts"]
    key_full = NA.cache_key(RI.tts_text(S), voice, tempo)
    meta = json.loads(NA.sidecar_of(full).read_text(encoding="utf-8")) if NA.sidecar_of(full).exists() else {}
    lkey = {l["id"]: NA.cache_key(l["tts"], voice, tempo) for l in lines}
    have = {i for i, k in lkey.items() if (LD / f"{k}.mp3").exists() and NA.sidecar_of(LD / f"{k}.mp3").exists()}
    if (full.exists() and meta.get("key") == key_full) or not have:
        full, align = RI.tts_once(S, R, log)                      # ①(캐시 적중) 또는 ②(새 대본 = 전체 1회)
        tts_split_lines(S, full, align, LD, log)
        return full, align
    # ③ 바뀐 줄만 합성
    LD.mkdir(parents=True, exist_ok=True)
    made = []
    for l in lines:
        f = LD / f"{lkey[l['id']]}.mp3"
        if l["id"] not in have:
            NA.synth_cached(l["tts"], voice, tempo, f, log=log)
            made.append(l["id"])
    log(f"[tts] 줄 캐시: 재사용 {len(lines) - len(made)}줄 · 새로 합성 {made}")
    import subprocess
    import numpy as np
    pcm, chars, st0, en0, t = [], [], [], [], 0.0
    gap = np.zeros(int(round(TTS_LINE_GAP * 44100)), np.float32)
    for k, l in enumerate(lines):
        f = LD / f"{lkey[l['id']]}.mp3"
        x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"], capture_output=True,
                                         stdin=subprocess.DEVNULL).stdout, np.float32)
        a = NA.load_align(f)
        if not a or len(a["characters"]) != len(l["tts"]):
            raise StageError(f"줄 캐시 {f.name} 글자 시각이 줄 글({len(l['tts'])}자)과 안 맞는다 — 줄 캐시를 지우고 다시")
        if k:
            pcm.append(gap); chars.append(" "); st0.append(round(t - TTS_LINE_GAP / 2, 3)); en0.append(round(t - TTS_LINE_GAP / 2, 3))
        chars += list(a["characters"])
        st0 += [round(t + v, 3) for v in a["character_start_times_seconds"]]
        en0 += [round(t + v, 3) for v in a["character_end_times_seconds"]]
        pcm.append(x)
        t += len(x) / 44100 + TTS_LINE_GAP
    wav = R / "narr_full_lines.wav"
    import wave
    y = np.concatenate(pcm)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    if full.exists():
        full.replace(full.with_name(f"narr_full_old_{str(meta.get('key', 'x'))[:8]}.mp3"))
    run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1", full])
    align = {"characters": chars, "character_start_times_seconds": st0, "character_end_times_seconds": en0}
    if "".join(chars) != RI.tts_text(S):
        raise StageError("줄 캐시로 이은 글자 시각이 전체 글과 다르다")
    NA.sidecar_of(full).write_text(json.dumps({"key": key_full, "text": RI.tts_text(S), "voice": voice, "tempo": tempo, "model": NA.TTS_MODEL,
                                               "align": align, "legacy": False, "from_lines": {l["id"]: lkey[l["id"]] for l in lines}, "made": made,
                                               "at": __import__("time").strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")
    return full, align


def tts_split_lines(S: dict, full: Path, align: dict | None, LD: Path, log=print) -> int:
    """전체 합성본을 줄 캐시로 쪼개 저장(글자 시각이 있을 때만 — 줄 경계 = RI.split_by_align 과 같은 자리). 이미 있는 줄은 건너뜀. 반환 = 새로 쓴 줄 수."""
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid import render_itssum as RI
    if not align:
        return 0
    voice, tempo = S["voice"]["voice_id"], S["voice"].get("tempo")
    lines = [l for l in S["lines"] if l["kind"] == "tts"]
    try:
        spans = RI.split_by_align(S, align)
    except StageError as e:
        log(f"[tts] 줄 캐시 쪼개기 건너뜀: {e}")
        return 0
    LD.mkdir(parents=True, exist_ok=True)
    pos, n = 0, 0
    for l, (a, b) in zip(lines, spans):
        i0, i1 = pos, pos + len(l["tts"])
        pos = i1 + 1
        f = LD / f"{NA.cache_key(l['tts'], voice, tempo)}.mp3"
        if f.exists() and NA.sidecar_of(f).exists():
            continue
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", full, "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1", f])
        la = {k: [round(v - a, 3) for v in align[k][i0:i1]] for k in ("character_start_times_seconds", "character_end_times_seconds")}
        la["characters"] = align["characters"][i0:i1]
        NA.sidecar_of(f).write_text(json.dumps({"key": NA.cache_key(l["tts"], voice, tempo), "text": l["tts"], "voice": voice, "tempo": tempo,
                                                "model": NA.TTS_MODEL, "align": la, "legacy": False, "split_from": full.name}, ensure_ascii=False), encoding="utf-8")
        n += 1
    return n


def devices(st: dict, trans: list[dict], A: dict | None = None, segs: list[dict] | None = None, T: dict | None = None,
            n_narr: int | None = None) -> dict:
    """render_info.devices 표식(지시서 02 → 04 품질 관문이 읽는다): 전환 종류별 개수 · 나레 덕킹 dB·실측 · 틀 종류 ·
    (2차) 구간 틀 · 자막 쌓기 · 컷 그림 칸 수 · 나레 줄 수(0 = 나레 없는 편). 2차 칸은 값이 있을 때만 붙는다(장치 안 켠 판 표식 그대로)."""
    from collections import Counter
    TR = (st.get("cuts") or {}).get("transition") or {}
    d = {"transition": {"kinds_set": TR.get("kinds") or {"cut": 1.0}, "drawn": dict(Counter(e["kind"] for e in trans)), "n": len(trans)},
         "duck_narr": {"db": float((st.get("bgm") or {}).get("duck_narr_db") or 0.0), "bed": (A or {}).get("bed")},
         "frame_kind": frame_kind(st["frame"])}
    if segs:
        d["segments"] = [{"t0": g["t0"], "t1": g["t1"], "kind": g["kind"], "window": g["window"], "captions": g["captions"]} for g in segs]
    if (st.get("caption") or {}).get("stack"):
        d["caption_stack"] = st["caption"]["stack"]
    if T and any(c.get("pic") for c in T["cuts"]):
        d["pic_cuts"] = sum(1 for c in T["cuts"] if c.get("pic"))
    if n_narr == 0:
        d["narration"] = 0
    return d


def render_marks(style_name: str, renderer_file: str | Path) -> dict:
    """render_info 표식 한 곳(0순위-C, 표준 §11 ⑤ — 04 품질 관문 marker_verdict 가 읽는다): render_bench·render_itssum·render_jaemi 가 같이 부른다.
    style_sha = 판 파일 바이트 sha256(관문이 지금 파일과 앞자리 대조) · style_sha_effective = _common·base 합친 설정 sha256 앞 12자리 ·
    renderer_sig = '<렌더러 파일 이름>@<그 파일 sha256 앞 12자리>'."""
    import hashlib
    from tools.calcopy.hybrid import styles as ST
    rf = Path(renderer_file)
    eff = json.dumps(ST.load(style_name), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {"style_sha": hashlib.sha256(ST.path_of(style_name).read_bytes()).hexdigest(),
            "style_sha_effective": hashlib.sha256(eff).hexdigest()[:12],
            "renderer_sig": f"{rf.stem}@{hashlib.sha256(rf.read_bytes()).hexdigest()[:12]}"}


def _voice_gate_text(S: dict) -> None:
    """렌더 전 관문 ② 앞 — tts 글에 영문이 있으면 TTS 돈 쓰기 전에 멈춘다(주인 engine/narr_verify.latin_lines)."""
    from tools.calcopy.engine import narr_verify as NV
    bad = NV.latin_lines(S)
    if bad:
        raise StageError(f"tts 글에 영문 {bad} — 타입캐스트가 건너뛴다(감사 'AI'·'LED' 7곳). 한글 읽기로 바꿔 보낸다(AI → 에이아이)")


def _voice_gate_audio(S: dict, sent: list, R: Path, log=print) -> None:
    """렌더 전 관문 ② — 합성 직후 줄별 받아쓰기 ↔ 그 줄 글(주인 engine/narr_verify.gate_sent). 확정 결함이면 영상 굽기 전에 멈춘다."""
    from tools.calcopy.engine import narr_verify as NV
    bad = NV.gate_sent(S, sent, R, log)
    if bad:
        raise StageError("나레 줄별 받아쓰기 확정 결함: " + " / ".join(bad) + " — 그 줄 문장을 바꿔 다시 합성(줄 캐시라 바뀐 줄만). 상세 render/narr_verify.json")


def render(style_name: str, doc: Path, work: Path, plan_only: bool = False, log=print, tts: bool = False) -> dict:
    from tools.calcopy.hybrid import render_itssum as RI
    from tools.calcopy.hybrid import styles as ST
    st = ST.load(style_name)
    doc, work = Path(doc), Path(work)
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    S.setdefault("voice", {k: st["voice"][k] for k in ("name", "voice_id") if k in st["voice"]})
    S.setdefault("cps_target", st.get("cps_target", 7.0))
    R = work / "render"; R.mkdir(parents=True, exist_ok=True)
    if plan_only:
        sm = align = None
        if tts and any(l["kind"] == "tts" for l in S["lines"]):      # 계획 때 진짜 목소리 길이로(10-22 선우용여: 어림으로 통과 → 렌더에서 '컷이 원본 샷보다 길다' 2번·완성본 길이 넘침으로 렌더 3번). 합성은 캐시 — 렌더가 그대로 쓴다
            tts_S = {**S, "lines": [l for l in S["lines"] if l["kind"] == "tts"]}
            _voice_gate_text(S)
            full, align = tts_by_line(tts_S, R, log)
            sent, _, _ = RI.make_sentences(tts_S, full, R, log, align=align, spread=RI.spread_of(st))
            _voice_gate_audio(S, sent, R, log)
            sm = {x["id"]: x for x in sent}
        T = timeline(S, M, st, sm, align)
        placed = plan_rows(S, T, st)
        placed["transitions_drawn"] = transitions_of(T, st, placed, log)
        jsave(doc / "plan/계획_시간표.json", {"timeline": T, "placement": placed})
        over = [c for c in T["cuts"] if c["over"] > 0]
        for c in T["cuts"]:
            log(f"  {c['line']:4s} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c.get('max')} {c['src']}@{c.get('ss')}")
        LD = st["length"]
        length = {"sec": round(T["end"], 2), "min": LD["min"], "max": LD["max"], "measured": bool(sm),
                  "ok": LD["min"] - 0.5 <= T["end"] <= LD["max"] + 0.5}      # 판정 = bench_check '길이'와 같은 범위(±0.5)
        log(f"{'목소리 실측' if sm else '어림'} 길이 {T['end']}초 · 배치 {placed['log']}")
        msg = ("계획에서 컷이 원본 샷보다 길다" + ("" if sm else "(어림)") + ": " + str([(c["line"], c["src"], c.get("ss"), c["dur"], c.get("max"), {"원본 남음": c["src_left"]} if "src_left" in c else None) for c in over])) if over else ""
        if over and not tts:
            raise StageError(msg)
        from tools.calcopy.hybrid import thumb_rule as TR
        card_bad = TR.card_text_gate(doc) + TR.card_face_gate(st, doc, T, M["cand_dir"]) + cut_boundary_gate(T, M, st)      # 렌더 전 관문 ⑥ — 계획 때 걸러 렌더를 안 돌린다
        if card_bad:
            raise StageError(" / ".join(card_bad))
        return {"timeline": T, "placement": placed, "length": length, "over": msg}
    tts_S = {**S, "lines": [l for l in S["lines"] if l["kind"] == "tts"]}
    if tts_S["lines"]:
        _voice_gate_text(S)
        full, align = tts_by_line(tts_S, R, log)
        sent, tempo, _ = RI.make_sentences(tts_S, full, R, log, align=align, spread=RI.spread_of(st))
        _voice_gate_audio(S, sent, R, log)   # 판 targets.speech 목표가 있으면 타입캐스트 줄별 ±8% 미세(미나 그대로, 지시서 15)
    else:           # 나레 없는 편(관제 263 02 2차 ②) — TTS 안 부른다(돈 0). 자막 줄(kind sub) 시간표 + 원음 + 배경음·효과음
        align, sent, tempo = None, [], None
        log("[나레 없음] tts 줄 0 — TTS 건너뜀, 자막 시간표(sub)·원음·배경음·효과음만")
    sm = {s["id"]: s for s in sent}
    T = timeline(S, M, st, sm, align)
    over = [c for c in T["cuts"] if c["over"] > 0]
    if over:
        raise StageError("컷이 원본 샷보다 길다: " + str([(c["line"], c["src"], c.get("ss"), c["dur"], c.get("max"), {"원본 남음": c["src_left"]} if "src_left" in c else None) for c in over]))
    from tools.calcopy.hybrid import thumb_rule as TR
    card_bad = TR.card_text_gate(doc) + TR.card_face_gate(st, doc, T, M["cand_dir"]) + cut_boundary_gate(T, M, st)          # 렌더 전 관문 ⑥(10-25): 연예인 판 카드 3안 얼굴 — 영상 굽기 전에 멈춘다
    if card_bad:
        raise StageError(" / ".join(card_bad))
    win0 = render_window(T, M, st, R)                          # 창(전환 없이) — 자리 검출 화면의 재료
    placed = plan_rows(S, T, st, make_locate(S, T, st, R, win0, log))
    from tools.calcopy.hybrid import placement as PL
    chk = PL.check_place(placed, st)
    check_sfx(st, placed)
    MG = motion_graphics(st, T)
    if MG and MG["not_drawn"]:
        log(f"[모션그래픽] {MG['id']} — bench 자막팩이라 안 그리는 칸: {MG['not_drawn']}")
    trans = transitions_of(T, st, placed, log)
    win = window_transitions(win0, T, st, R, trans)
    base = render_base(S, T, st, placed, R, win, trans, color=(MG or {}).get("color_filter"))
    T["end"] = round(sum(c["frames"] for c in T["cuts"]) / FPS, 4)
    segs = frame_segments(S, T, st)
    rows = caption_rows(placed, st, segs)
    cap = draw_motion_layers(burn_captions(base, rows, st, R, T["end"]), MG, R)
    mix, A = audio(S, M, st, T, sent, placed, R)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", cap, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{T['end']:.3f}", final])
    from tools.calcopy.engine import ad_mark
    ad_mark.apply_inplace(final, log=log)
    jsave(R / "timeline.json", T)      # 썸네일 카드가 이 시간표로 장면(줄·몇 번째 컷)을 찾는다 — 카드보다 먼저 저장(10-24 09: 옛 시간표로 찾아 실패)
    if (doc / "썸네일.json").exists():      # 맨 앞 2프레임 = 썸네일 카드(주인 thumb.card · 10-23 사장님 "맨 앞에 썸네일 아주 잠깐") — 카드에 '광고' 같이 찍힘
        from tools.calcopy.hybrid import thumb as TH
        tc = TH.cards(style_name, doc, work, log=log)
        TH.stamp_video(final, Path(tc["pick_jpg"]))
        log(f"썸네일 {tc['pick']} → 맨 앞 {TH.THUMB_FRAMES}프레임")      # 오른쪽 위 '광고' 표시 — 주인 = engine/ad_mark(사장님 10-22 모든 렌더)
    from tools.calcopy.engine import finalize
    finalize.seal(final, "render_bench", doc / "대본.json", log=log)      # final 을 고치는 마지막 단계(썸네일 카드) 뒤 — 납품은 이 봉인 그대로인 파일만(engine/deliver)
    jsave(R / "timeline.json", T)
    tab = {"_note": f"배치 결과 — placement.place(판 설정 {style_name}) · 시각은 final.mp4 기준 초", "pack": st["caption"]["pack"], "rows": rows,
           "sfx": placed["sfx"], "flashes": placed["flashes"], "transitions": trans, "memes": meme_overlays(placed), "comment": placed.get("comment"),
           **({"segments": [{k: g[k] for k in ("t0", "t1", "kind", "window", "captions", "body_text")} for g in segs]} if segs else {}),
           "log": placed["log"], "check": chk}
    jsave(R / "자막표.json", tab)
    jsave(doc / "자막표.json", tab)
    info = {"made_by": "tools/calcopy/hybrid/render_bench.py", "version": style_name, "tempo": tempo, "final": str(final), "final_dur": dur_of(final),
            "final_lufs": lufs(final), "audio": A, "placement_check": chk, "n_cuts": len(T["cuts"]),
            "devices": {**devices(st, trans, A, segs, T, len(sent)),
                        **({"motion_graphics": {"id": MG["id"], "layers": len(MG["layers"]), "color": MG["color_filter"], "not_drawn": MG["not_drawn"]}} if MG else {})},
            **render_marks(style_name, __file__), "line_cps": RI.line_cps(sent),
            "cuts_flat": [{k: c.get(k) for k in ("line", "src", "ss", "t0", "t1", "dur", "see")} for c in T["cuts"]]}
    jsave(R / "render_info.json", info)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_sheet_1s.jpg")
    log(f"final {final} {info['final_dur']:.2f}초 LUFS/TP {info['final_lufs']} · 배치 {placed['log']}")
    return info


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("style"); ap.add_argument("doc"); ap.add_argument("work"); ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    render(a.style, Path(a.doc), Path(a.work), plan_only=a.plan)
