"""제미니가 **실제 영상**에서 읽은 디자인 스펙 → deco_frame.PRESETS 코드 생성.

★왜 손으로 안 쓰나 (2026-08-20 사장님 지적):
  썸네일만 보고 손으로 색을 찍었더니 살림킹왕짱이 '분홍 바탕+흰 글씨'로 들어갔다.
  실제 영상은 **흰 바탕+분홍 글씨**(#FFFFFF / #DE5D6D)였다 — 색이 통째로 뒤집혔다.
  그래서 값은 사람이 만지지 않고 **읽은 그대로** 여기서 코드로 찍어낸다.

입력: docs/reference/썰쇼핑_영상디자인_실측.json (채널 20 × 영상 3편의 합의값)
출력: 붙여넣을 PRESETS 블록(표준출력)

  python tools/build_sul_presets.py > /tmp/presets.py
"""
import json
import pathlib
import sys

H = 1920
_REF = pathlib.Path(__file__).resolve().parents[1] / "docs" / "reference"
SRC = _REF / "썰쇼핑_영상디자인_실측.json"
# 글꼴 원장(선택). 없으면 전부 기본 글꼴로 떨어진다.
# ★'무슨 폰트냐'고 물으면 모델이 없는 이름을 지어낸다 — 우리 글꼴 견본 시트를 보여주고
#   **번호로 고르게** 했다(비교는 잘한다). 채널당 3편의 최빈값.
FONT_SRC = _REF / "썰쇼핑_헤드라인글꼴.json"
DEFAULT_FONT = "BMDOHYEON.ttf"


def _fonts():
    if not FONT_SRC.exists():
        return {}
    rows = json.loads(FONT_SRC.read_text(encoding="utf-8"))
    return {r["channel"]: r["font"] for r in rows if r.get("font")}

# 채널명 → 프리셋 id. 한글 id는 못 쓰므로 고정 표(순서가 바뀌어도 id가 안 흔들린다).
SLUG = {
    "활용정점.": "sul_hwaryong", "살림킹왕짱": "sul_salrim", "썰칩12": "sul_sulchip",
    "방구석꿀템": "sul_bangkkul", "럭키박스": "sul_lucky", "쇼핑 치트키": "sul_cheat",
    "공가미": "sul_gongami", "코어장바구니": "sul_core", "살림장착": "sul_jangchak",
    "쇼핑천재": "sul_chunjae", "이븐쇼핑": "sul_even", "이거였네": "sul_igeo",
    "달래샵": "sul_dalrae", "꿀팁꿀템": "sul_kkultip", "다있슈": "sul_daissue",
    "인생갓템": "sul_insaeng", "나만또모르고있었지": "sul_namanto", "요새난리": "sul_yosae",
    "무슨템": "sul_museun", "집돌이": "sul_jipdori",
}

# 제미니가 준 아이콘 이름 → 그리기 코드가 아는 값.
# ★같은 뜻을 한국어·영어·이모지 셋으로 돌려준다(실측: '햄버거'·'hamburger'·'☰'가 다 나왔다).
#   스키마에 enum을 안 걸어서 그렇다 — 여기서 전부 한 값으로 모은다.
ICON = {
    "햄버거": "hamburger", "hamburger": "hamburger", "☰": "hamburger", "메뉴": "hamburger",
    "돋보기": "search", "search": "search", "🔍": "search", "검색": "search",
    "점3개": "dots", "dots": "dots", "⋮": "dots", "점 3개": "dots",
    "뒤로": "back", "back": "back", "←": "back",
    "북마크": "bookmark", "bookmark": "bookmark", "🔖": "bookmark", "저장": "bookmark",
    "없음": "none", "none": "none", "": "none", None: "none",
}
# ★두께는 슬라이더 값이 아니라 **글자 크기 대비 비율**로 봐야 한다.
#   실측 사고(2026-08-20): 두꺼움=12를 90px 글자에 주니 13%라 획 사이가 메워졌다.
#   실제 채널은 5~8% 선이다 — 기존에 잘 돌던 프리셋(HC_PRESETS)도 그 범위.
THICK = {"얇음": 3, "보통": 5, "두꺼움": 7}


def _hex(v, fallback):
    v = (v or "").strip()
    return v.upper() if (v.startswith("#") and len(v) == 7) else fallback


def _lum(hexv):
    """상대 밝기(0~1). 대비 검사용."""
    h = (hexv or "#000000").lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _readable(bar, text):
    """★띠색과 글자색이 같으면 글자가 사라진다.

    실측 사고: 살림킹왕짱이 흰 띠 + 흰 글자로 나왔다(3편에서 채널명 색을 다르게 읽어
    최빈값이 흰색으로 몰렸다). 대비가 없으면 밝기로 검정/흰색을 고른다 —
    '읽은 값 그대로'가 원칙이지만 **안 보이는 값은 값이 아니다**.
    """
    if abs(_lum(bar) - _lum(text)) >= 0.25:
        return text
    return "#111111" if _lum(bar) > 0.5 else "#FFFFFF"


def _pct_to_px(p, fallback_px):
    try:
        return max(0, min(400, round(float(p) / 100 * H)))
    except (TypeError, ValueError):
        return fallback_px


def _font_for(size_pct):
    """글자 높이가 가로폭의 몇 %인가 → 우리 슬라이더(28~120) 값.

    ★상한을 90으로 둔다. 미리보기는 720폭 기준이라 90을 넘으면 한 줄이 화면 밖으로
      나간다(실측: 108px짜리 썰칩12가 좌우로 잘렸다). 원본이 더 컸더라도 우리 문구는
      길이가 다르므로 그대로 쓰면 안 된다 — 넘치면 어차피 렌더가 줄인다.
    """
    try:
        px = float(size_pct) / 100 * 1080
    except (TypeError, ValueError):
        px = 90
    return int(max(28, min(90, round(px))))


def _visible(color, outline, has_box):
    """★어두운 글자 + 어두운 외곽선 + 박스 없음 = 영상 위에서 안 보인다.

    실측: 활용정점이 검은 글씨(#000000)에 검은 외곽선이라 어두운 장면에서 사라졌다.
    원본은 흰 박스를 깔아서 살아 있는데, 박스가 없는 조합이면 외곽선을 흰색으로 뒤집는다.
    """
    # ★박스가 있어도 **글자색과 외곽선색이 같으면** 두꺼운 외곽선이 글자를 먹는다
    #   (실측: 활용정점 검은 글씨 + 검은 외곽선 → 흰 박스 위에서 글자가 뭉개졌다).
    #   글자와 외곽선은 반드시 갈려야 한다.
    if abs(_lum(color) - _lum(outline)) < 0.2:
        return "#FFFFFF" if _lum(color) < 0.5 else "#000000"
    if has_box:
        return outline                      # 그 외엔 박스가 배경을 깔아주니 그대로 둔다
    if _lum(color) < 0.35 and _lum(outline) < 0.35:
        return "#FFFFFF"
    if _lum(color) > 0.75 and _lum(outline) > 0.75:
        return "#000000"
    return outline


def build(rows):
    fonts = _fonts()
    out = []
    for r in rows:
        slug = SLUG.get(r["channel"])
        if not slug:
            print(f"# ⚠️ id 없음: {r['channel']}", file=sys.stderr)
            continue
        bar_h = _pct_to_px(r.get("bar_h_pct"), 190)
        hl_y = r.get("hl_y")
        try:
            hl_y = int(round(float(hl_y)))
        except (TypeError, ValueError):
            hl_y = int(bar_h / H * 100) + 6
        # ★글자가 **틀 전체** 아래로 내려와야 한다 — 띠만 피하면 안 된다.
        #   실측 사고(2026-08-20): 띠(182px)만 피해 y=16%로 뒀더니, 띠 아래 붙는
        #   **흰 제목블록**(제목 2줄+조회수+밑줄 ≈ 300px)에 헤드라인이 통째로 가려져
        #   글자 아랫부분만 삐져나왔다. 제목블록 높이까지 더해서 그 아래로 민다.
        # ★흰 제목블록은 **제목이 있으면 무조건 그려진다**(render()는 title/views/comments
        #   중 하나만 있어도 그린다). has_head가 False인 채널도 화면에서 제목을 채우면
        #   블록이 생기므로, 자리 계산은 **항상 블록이 있다고 보고** 해야 한다.
        #   (실측 사고: has_head=False인 3곳만 첫 줄이 계속 잘렸다)
        # 흰 블록 = 위여백36 + 제목 2줄(78×2) + 메타52 + 아래여백24 ≈ 246px
        # (render()의 block_h 계산과 같은 근거 — 여기서만 어림하면 어긋난다)
        head_px = 36 + 78 * 2 + 52 + 24
        floor_px = bar_h + head_px
        # ★y는 글자 블록의 **한가운데**다(미리보기가 translate(-50%,-50%)로 앉힌다).
        #   틀 바닥에 y를 맞추면 위쪽 절반이 가려진다 — 블록 높이의 **절반만큼 더** 내린다.
        #   ★크기(hc_size)는 720폭 기준이므로 1920 화면으로 환산해야 한다.
        #     이 환산을 빠뜨려 처음엔 20종이 전부 첫 줄이 잘렸다(실측으로 잡음).
        size_1920 = _font_for(r.get("hl_size")) * (H / 720)
        half_block = size_1920 * 1.18            # 2줄 블록의 절반 = 1줄 높이
        hl_y = max(hl_y, round((floor_px + half_block) / H * 100) + 1)
        hl_y = max(0, min(88, hl_y))              # 너무 내려가면 화면 밖
        c1 = _hex(r.get("hl_c1"), "#FFFFFF")
        c2 = _hex(r.get("hl_c2"), c1)
        # ★2줄이 1줄과 같은 색이면 '흰색+형광' 대비가 사라진다. 실측에서 같은 색이
        #   나온 채널(살림킹왕짱·이거였네 등)은 원래 형광을 안 쓰는 곳이므로 그대로 둔다
        #   — 억지로 형광을 넣으면 그 채널 질감이 아니게 된다.
        out.append({
            "id": slug, "name": r["channel"], "n": r.get("n", 0),
            "bar": _hex(r.get("bar_color"), "#F08080"),
            "on_bar": _readable(_hex(r.get("bar_color"), "#F08080"),
                                _hex(r.get("bar_text"), "#FFFFFF")),
            "bar_h": bar_h,
            "left_icon": ICON.get(r.get("left_icon"), "none"),
            "right_icon": ICON.get(r.get("right_icon"), "none"),
            "center_kind": r.get("center_kind") or "채널명",
            "sub_bg": _hex(r.get("sub_bg"), "#FFFFFF"),
            "sub_text": _hex(r.get("sub_text"), "#8E8E8E"),
            "sub_h": _pct_to_px(r.get("sub_h_pct"), 0) if r.get("sub_exists") else 0,
            "hc_size": _font_for(r.get("hl_size")),
            "hc_c1": c1, "hc_c2": c2,
            "hc_out": _visible(c1, _hex(r.get("hl_outline"), "#000000"),
                               bool(r.get("hl_box"))),
            # ★두께는 글자 크기에 비례해야 한다 — 작은 글자에 고정 두께를 주면
            #   비율이 커져 획이 메워진다(실측: 63px 글자에 8이면 12.7%).
            #   상한 9%로 자른다.
            "hc_out_w": min(THICK.get(r.get("hl_thick"), 5),
                            max(2, round(_font_for(r.get("hl_size")) * 0.09))),
            "hc_y": hl_y,
            "hc_box": bool(r.get("hl_box")),
            "hc_box_color": _hex(r.get("hl_box_color"), "#FFFFFF"),
            "font": fonts.get(r["channel"], DEFAULT_FONT),
            # 흰 제목블록을 쓰는 채널인가(실측 17/20) + 그 채널다운 샘플 수치
            "has_head": bool(r.get("sub_exists")),
            "demo_views": "264만", "demo_comments": "587",
            "notes": (r.get("notes") or [""])[0][:70],
        })
    return out


def emit(rows):
    print("# ── 썰쇼핑 20채널 · 실제 영상 실측(제미니가 읽은 값 그대로) ──────────────")
    print("#   원장: docs/reference/썰쇼핑_영상디자인_실측.json")
    print("#   ★손으로 고치지 마라 — tools/build_sul_presets.py로 다시 찍어낸다.")
    for r in rows:
        print(f'    "{r["id"]}": {{')
        print(f'        "name": "{r["name"]}", "ref": "{r["name"]}(영상 {r["n"]}편 실측)",')
        print(f'        "bar": "{r["bar"]}", "on_bar": "{r["on_bar"]}", "bar_h": {r["bar_h"]},')
        print(f'        "left_icon": "{r["left_icon"]}", "right_icon": "{r["right_icon"]}",')
        print(f'        "center_kind": "{r["center_kind"]}",')
        print(f'        "sub_bg": "{r["sub_bg"]}", "sub_text": "{r["sub_text"]}", "sub_h": {r["sub_h"]},')
        # ★고르면 바로 "완성된 그림"이 나오게 기본 문구까지 싣는다(2026-08-20 사장님:
        #   "체널영상속 프리셋이랑 세팅을 미리 해주고 거기서 수정하게").
        #   빈 채로 두면 흰 제목블록이 아예 안 그려져 위만 띠 하나 있고 아래가 텅 빈다.
        print(f'        "has_head": {r["has_head"]}, "demo_views": "{r["demo_views"]}",')
        print(f'        "demo_comments": "{r["demo_comments"]}",')
        print(f'        "headcopy": _hc("{r["font"]}", {r["hc_size"]}, "{r["hc_c1"]}", '
              f'"{r["hc_c2"]}", {r["hc_y"]}, {r["hc_out_w"]}, "{r["hc_out"]}", '
              f'{r["hc_box"]}, "{r["hc_box_color"]}"),')
        if r["notes"]:
            print(f'        # {r["notes"]}')
        print("    },")


if __name__ == "__main__":
    emit(build(json.loads(SRC.read_text(encoding="utf-8"))))
