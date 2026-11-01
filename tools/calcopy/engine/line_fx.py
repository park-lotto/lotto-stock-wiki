"""(판단 주인) 칼카피 한 편 제작기의 강조어 자막·모션 효과 — 대본.json 줄의 emph·fx → 숏템 장면 비트 자료(관제 097, 10-24 사장님
"길을 넣어야지, 고객 거나 내 거나 같은 방법인데").

그리는 쪽은 새로 만들지 않는다. 숏템 렌더(shopping_shorts.scene_style.scene_marks → out/precision20-ui.js)가 이미 고객 편집기·렌더·캡컷에서
비트의 emph(핵심 낱말 색칠)·stickers(효과 스티커)를 그린다. 여기는 대본 칸을 그 자료 꼴로 옮기는 한 곳뿐이다.

대본.json 줄 칸:
  "emph": ["김홍도", {"word": "2500여 명", "color": "#FF4FA3"}]   강조 낱말. 문자열이면 색은 줄 안 순서대로 노랑·분홍 번갈아, 크기 pop.
  "fx":   [{"word": "일시품절", "kind": "stamp"}, {"word": "2분", "kind": "pop"}]
          kind = stamp(빨강 도장 글자, 낱말 그대로) · pop(만화 번쩍) · flash(번쩍 b) · shake(낱말 옆 반짝 선) · circle/arrow(빨간 원+화살표, x·y 화면 %)
          선택: x·y(화면 %)·r(기울기)·size·text(도장 글을 낱말과 다르게).
재료.json 컷 칸 "move": sway/bounce/punch/shake → tools/calcopy/narr_video.move_vf(그림·영상 컷 같은 주인).
칸이 없으면 비트에 아무것도 안 붙는다 — 예전 편은 글자 하나 다르지 않다(tools/calcopy/engine/check_fx.py --same 로 증명)."""
from __future__ import annotations

YELLOW, PINK = "#FFE600", "#FF4FA3"
FX_KINDS = {"stamp": "sound_word", "pop": "comic_burst", "flash": "comic_burst", "shake": "spark_lines",
            "circle": "circle_arrow", "arrow": "circle_arrow"}


def _emph_items(line: dict) -> list[dict]:
    out = []
    for k, it in enumerate(line.get("emph") or []):
        it = {"word": it} if isinstance(it, str) else dict(it)
        it.setdefault("color", (YELLOW, PINK)[k % 2])
        it.setdefault("grow", "pop")
        it.setdefault("part", True)   # 어절 앞부분만('완판됐다고' → '완판') — scene_marks part
        out.append(it)
    return out


def _has(caption: str, word: str) -> bool:
    from shopping_shorts.scene_style import _word_key
    toks = [_word_key(t) for t in (caption or "").split()]
    want = [_word_key(p) for p in word.split() if _word_key(p)]
    return bool(want) and any(all(w in toks[i + j] for j, w in enumerate(want)) for i in range(len(toks) - len(want) + 1))


def _sticker(fx: dict) -> dict:
    kind = fx.get("kind")
    if kind not in FX_KINDS:
        raise ValueError(f"fx 종류 모름: {kind} (가능: {'·'.join(FX_KINDS)})")
    st = {"kind": FX_KINDS[kind], "word": fx["word"]}
    if kind == "stamp":
        st.update({"text": fx.get("text") or fx["word"], "x": fx.get("x", 50), "y": fx.get("y", 34), "r": fx.get("r", -8), "size": fx.get("size", 190)})
    elif kind == "flash":
        st["variant"] = "b"
    elif kind in ("circle", "arrow"):
        st.update({"x": fx.get("x", 50), "y": fx.get("y", 40)})
    for k in ("x", "y", "r", "size"):
        if k in fx and kind != "stamp":
            st[k] = fx[k]
    return st


def apply(beats: list[dict], beat_lines: list[int], raw_lines: list[dict]) -> list[dict]:
    """비트마다 그 줄의 emph(낱말이 그 비트 자막에 있을 때만 scene_marks 가 칠한다)·fx(낱말이 든 첫 비트 하나에만) 를 싣는다.
    돌려주는 값 = 실린 효과 목록(시각표·검사용). 칸이 하나도 없으면 비트는 그대로."""
    placed, used = [], set()
    for b, li in zip(beats, beat_lines):
        line = raw_lines[li] if 0 <= li < len(raw_lines) else {}
        cap = (b.get("caption_lines") or [""])[0]
        em = [it for it in _emph_items(line) if _has(cap, it["word"])]
        if em:
            b["emph"] = em
            placed += [{"t": b["t0"], "kind": "emph", "word": it["word"], "color": it["color"]} for it in em]
        sts = []
        for k, fx in enumerate(line.get("fx") or []):
            if (li, k) in used or not _has(cap, fx["word"]):
                continue
            used.add((li, k))
            sts.append(_sticker(fx))
            placed.append({"t": b["t0"], "kind": fx["kind"], "word": fx["word"]})
        if sts:
            b["stickers"] = sts
    return placed


def snapshot_patch(snap: dict, placed: list[dict]) -> dict:
    """강조 낱말이 하나라도 실렸으면 스냅샷 단어 강조 방식을 '핵심 단어 색칠'(mark — 계약 static/caption-motions.js fixed)로.
    안 켜면 렌더러(precision20-ui.js applyWordFx)가 장면 emph 를 읽지 않는다(10-24 첫 렌더 실측: 색 0픽셀). 프리셋이 이미 정했으면 그대로."""
    if any(p["kind"] == "emph" for p in placed) and not (snap.get("wordFx") or {}).get("style"):
        snap = {**snap, "wordFx": {"style": "mark", "color": "", "grow": ""}}
    return snap
