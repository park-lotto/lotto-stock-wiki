"""자막 실측 원장 → 자막 완성 스타일 프리셋(JSON).

★값은 사람이 만지지 않는다 — 원장에서 다시 찍어낸다(build_sul_presets.py와 같은 규약).
  2026-08-20 사고: 썸네일만 보고 손으로 색을 찍었더니 살림킹왕짱이 통째로 뒤집혔다.

★채널당 3편의 **최빈값**으로 정한다. 3편이 다 다르면 'agree: 동점'으로 남긴다 —
  숨기지 않는다(헤드라인 글꼴 원장이 그렇게 했고, 그게 정직했다).

    py tools/build_caption_presets.py /tmp/cap_ig.json /tmp/cap_yt.json > docs/reference/자막스타일_실측.json
"""
import collections
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parents[1]
FONT_DIR = BASE / "shopping_shorts" / "static" / "fonts"
# 견본 시트 번호 → 글꼴 파일명. ★시트를 만든 것과 **같은 정렬**이어야 번호가 맞는다.
FONTS = sorted(p.name for p in FONT_DIR.glob("*.[ot]tf"))


def _mode(vals, default=None):
    """최빈값 + 합의 정도. 값이 없으면 (default, '없음')."""
    vals = [v for v in vals if v not in (None, "", "없음")]
    if not vals:
        return default, "없음"
    c = collections.Counter(map(str, vals)).most_common()
    top, n = c[0]
    agree = "확실" if n >= 3 else ("보통" if n == 2 else "동점")
    # 원래 타입으로 되돌린다(문자로 셌으므로)
    for v in vals:
        if str(v) == top:
            return v, agree
    return top, agree


def _hex(v, default=None):
    v = str(v or "").strip()
    if v.startswith("#") and len(v) == 7:
        return v.upper()
    return default


def build(paths):
    rows = []
    for p in paths:
        rows += json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    # 파일 → 채널 되찾기(목록 원장에서)
    owner = {}
    for name, key in (("yt60.json", "video_id"), ("ig60.json", "shortcode")):
        f = pathlib.Path("C:/tmp") / name
        if not f.exists():
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            owner[r[key]] = r.get("channel") or r.get("username")

    by_ch = collections.defaultdict(list)
    for r in rows:
        stem = pathlib.Path(r["file"]).stem
        ch = owner.get(stem)
        if not ch:                       # 인스타는 파일명이 해시라 목록으로 못 잇는 게 있다
            ch = f"{r['platform']}:{stem[:8]}"
        by_ch[(r["platform"], ch)].append(r)

    out = []
    for (platform, ch), rs in sorted(by_ch.items()):
        rs = [r for r in rs if r.get("cap_exists")]
        if not rs:
            continue
        font_no, font_agree = _mode([r.get("cap_font_no") for r in rs])
        try:
            font = FONTS[int(font_no) - 1] if font_no else None
        except (ValueError, IndexError, TypeError):
            font = None
        color, _ = _mode([_hex(r.get("cap_color")) for r in rs], "#FFFFFF")
        out.append({
            "platform": platform, "channel": ch, "n": len(rs),
            "font": font, "font_no": font_no, "font_agree": font_agree,
            "size_pct": _mode([r.get("cap_size_pct") for r in rs], 3.5)[0],
            "y": _mode([r.get("cap_y") for r in rs], 60)[0],
            "align": _mode([r.get("cap_align") for r in rs], "가운데")[0],
            "color": color,
            "outline": _mode([r.get("cap_outline") for r in rs], False)[0],
            "outline_color": _mode([_hex(r.get("cap_outline_color")) for r in rs])[0],
            "outline_pct": _mode([r.get("cap_outline_pct") for r in rs], 0)[0],
            "shadow": _mode([r.get("cap_shadow") for r in rs], False)[0],
            "box": _mode([r.get("cap_box") for r in rs], False)[0],
            # ★박스 색을 **실측에서** 가져온다 — 예전엔 코드가 검정으로 지어냈다(2026-08-25 결함)
            "box_color": _mode([_hex(r.get("cap_box_color")) for r in rs])[0],
            "box_shape": _mode([r.get("cap_box_shape") for r in rs], "없음")[0],
            "box_opacity": _mode([r.get("cap_box_opacity") for r in rs], 100)[0],
            "emph": _mode([r.get("cap_emph") for r in rs], False)[0],
            "emph_kind": _mode([r.get("cap_emph_kind") for r in rs])[0],
            "emph_color": _mode([_hex(r.get("cap_emph_color")) for r in rs])[0],
            "emph_bg": _mode([_hex(r.get("cap_emph_bg")) for r in rs])[0],
            "notes": (rs[0].get("notes") or "")[:300],
        })
    return out


def main():
    out = build(sys.argv[1:])
    print(json.dumps(out, ensure_ascii=False, indent=1))
    n_emph = sum(1 for r in out if r["emph"])
    agree = collections.Counter(r["font_agree"] for r in out)
    print(f"\n채널 {len(out)} / 강조 쓰는 채널 {n_emph} / 글꼴 합의 {dict(agree)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
