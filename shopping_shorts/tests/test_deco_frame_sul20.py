"""썰쇼핑 상위 20채널 벤치마킹 틀 + 헤드카피 한 세트 (2026-08-20).

사장님 지시: "유튜브 썰체널들 엄청많이 모여있으니 20개체널 디자인을 그대로 가져와서 /
똑같이 하면안되고 살짝씩 비틀어서 / 해드카피도 이 템플릿들과 맞춰서 폰트크기 색상
종류 배치등을 한세트로"

★여기서 잠그는 계약(전부 실제로 밟은 함정이다):
  1. 20종이 **서로 다른 띠 높이**를 갖는다 — 같아지면 벤치마킹한 의미가 사라진다
  2. 틀마다 헤드카피 세트가 붙어 있고, 값이 화면 입력칸의 **허용 범위 안**이다
     (실측: outline_w=14를 줬더니 슬라이더 상한 12에 조용히 잘렸다)
  3. 옛 4종은 살아 있고 기본 190px 그대로다(저장된 작업이 계속 돈다)
"""
import pathlib

from shopping_shorts import deco_frame as df

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")

NEW = {k: v for k, v in df.PRESETS.items() if v.get("headcopy")}
LEGACY = ("news_coral", "news_lime", "news_gray", "news_navy")


def test_twenty_benchmarked_presets():
    assert len(NEW) == 20, f"썰쇼핑 벤치마킹 틀은 20종이어야 한다(현재 {len(NEW)})"


def test_each_preset_names_its_reference_channel():
    """어느 채널을 보고 만들었는지 남긴다 — 나중에 '왜 이 색인지'를 되짚을 수 있어야 한다."""
    for k, v in NEW.items():
        assert v.get("ref"), f"{k}: 벤치마킹 원본 채널(ref)이 비어 있다"


def test_bar_heights_are_varied():
    """★20종이 같은 높이면 원본 비율을 실측한 의미가 없다.

    실측값이라 딱 떨어지지 않는다(겹치는 채널이 있다) — '충분히 다양한가'만 본다.
    0은 띠가 없는 풀블리드 채널(실측 4곳)이라 정상이다.
    """
    hs = [v["bar_h"] for v in NEW.values()]
    assert len(set(hs)) >= 10, f"띠 높이가 너무 겹친다: {sorted(set(hs))}"
    assert all(0 <= h <= 400 for h in hs), "띠 높이는 normalize 상한(400) 안이어야 한다"


def test_full_bleed_presets_keep_zero_bar():
    """★띠 없는 채널이 190px 띠를 뒤집어쓰면 안 된다.
    `p.get("bar_h")`로 검사하면 0이 falsy라 통째로 무시된다 — 실제로 밟은 버그."""
    zero = [k for k, v in NEW.items() if v["bar_h"] == 0]
    assert zero, "풀블리드 채널이 하나도 없다면 실측이 뒤집힌 것"
    for k in zero:
        assert df.normalize({"preset": k})["bar_h"] == 0, f"{k}: 없던 띠가 생겼다"


def test_preset_bar_height_wins_over_default():
    """★프리셋이 자기 높이를 갖고 있으면 그게 기본 — 아니면 전부 190px이 된다."""
    for k, v in NEW.items():
        assert df.normalize({"preset": k})["bar_h"] == v["bar_h"], k


def test_manual_bar_height_is_respected():
    """사장님이 화면에서 민 값은 프리셋 기본값을 이긴다."""
    assert df.normalize({"preset": "sul_salrim", "bar_h": 100})["bar_h"] == 100


def test_headcopy_set_is_complete_and_in_ui_range():
    """★한 세트 = 폰트·크기·색·배치가 다 있어야 하고, 화면 슬라이더 범위 안이어야 한다.
    범위를 벗어나면 화면이 조용히 잘라 '설정한 값과 다르게' 나온다."""
    for k, v in NEW.items():
        hc = v["headcopy"]
        for field in ("font", "size", "color", "color2", "y", "weight", "outline_w"):
            assert field in hc, f"{k}: 헤드카피 세트에 {field}가 없다"
        assert 28 <= hc["size"] <= 120, f"{k}: 크기 슬라이더 범위(28~120) 밖 — {hc['size']}"
        assert 0 <= hc["y"] <= 100, f"{k}: 세로위치 범위 밖 — {hc['y']}"
        assert 0 <= hc["outline_w"] <= 12, f"{k}: 외곽선 슬라이더 상한 12 초과 — {hc['outline_w']}"
        assert hc["color"].startswith("#") and hc["color2"].startswith("#"), k


def test_headcopy_y_clears_the_bar():
    """★글자가 '딱 들어가야' 한다 — 띠 아래에서 시작해야 띠에 안 먹힌다."""
    for k, v in NEW.items():
        if v["bar_h"] == 0:
            continue          # 띠가 없으면 먹힐 것도 없다(풀블리드)
        bar_pct = v["bar_h"] / df.H * 100
        assert v["headcopy"]["y"] >= bar_pct - 1, (
            f"{k}: 헤드카피 y={v['headcopy']['y']}%가 띠({bar_pct:.1f}%)에 먹힌다")


def test_fonts_exist_on_disk():
    """없는 폰트를 가리키면 렌더가 조용히 기본 고딕으로 떨어진다."""
    for k, v in NEW.items():
        f = df._FONT_DIR / v["headcopy"]["font"]
        assert f.exists(), f"{k}: 폰트 파일 없음 — {f.name}"


def test_legacy_presets_untouched():
    """옛 작업이 이 id를 가리키고 있다 — 삭제·기본값 변경 금지."""
    for k in LEGACY:
        assert k in df.PRESETS, f"옛 프리셋 {k}가 사라졌다"
        assert df.normalize({"preset": k})["bar_h"] == 190, f"{k}: 옛 기본 높이가 바뀌었다"


def test_every_preset_renders():
    """20종이 실제로 그려지는지 — 색·폰트 오타는 여기서 걸린다."""
    for k in NEW:
        im = df.render({"preset": k, "channel": "내채널", "title": "테스트 제목",
                        "views": "264만", "comments": "587"})
        assert im.size == (df.W, df.H), k
        assert im.getpixel((df.W // 2, df.H - 5))[3] == 0, f"{k}: 아래쪽이 불투명하면 영상을 가린다"


# ── 화면 배선(실제로 밟은 버그 2개를 잠근다) ──────────────────────────────
def test_ui_uses_preset_bar_height_not_190():
    """★화면이 190을 우기면 어떤 틀을 골라도 같은 비율이 된다."""
    seg = HTML[HTML.index("function frPick"):]
    seg = seg[:seg.index("function frUpdate")]
    assert "meta.bar_h" in seg, "틀이 갖고 온 bar_h를 써야 한다"
    assert "samePreset" in seg, (
        "다른 틀로 갈아탈 땐 새 높이를 써야 한다 — 앞 틀 값을 물고 가면 전부 같아진다")


def test_ui_applies_matched_headcopy_set():
    seg = HTML[HTML.index("function frPick"):HTML.index("function frUpdate")]
    assert "applyHeadcopySet" in seg, "틀을 고르면 헤드카피 세트도 같이 입혀야 한다"


def test_apply_set_fills_font_options_first():
    """★<select>는 옵션이 비어 있으면 .value 대입이 조용히 무시된다.
    (실측: 틀을 먼저 고르면 폰트만 안 바뀌었다)"""
    seg = HTML[HTML.index("function applyHeadcopySet"):]
    seg = seg[:seg.index("function alignHC")]
    assert "renderFontSelect" in seg, "폰트 목록을 채운 뒤에 값을 넣어야 한다"
    assert "hcText" not in seg.split("color2")[0], "틀을 바꿨다고 사장님 문구를 건드리면 안 된다"


def test_highlight_rule_field_name_matches():
    """★규칙 필드명이 addHighlightRule과 다르면 조용히 무시된다(keyword)."""
    seg = HTML[HTML.index("function applyHeadcopySet"):HTML.index("function alignHC")]
    assert "keyword:" in seg, "강조 규칙 필드는 keyword여야 한다"


# ── 실제 영상 실측으로 다시 만든 뒤 추가된 계약 (2026-08-20) ─────────────
def test_values_came_from_real_videos_not_thumbnails():
    """★사장님 지적("실제 영상들 안봤지?")의 재발 방지.

    처음엔 썸네일만 보고 손으로 색을 찍어 살림킹왕짱이 통째로 뒤집혀 있었다.
    지금 값은 영상 실측 원장에서 나온다 — 원장이 없어지면 출처를 잃는다.
    """
    ledger = pathlib.Path(__file__).resolve().parents[2] / "docs" / "reference" / "썰쇼핑_영상디자인_실측.json"
    assert ledger.exists(), "영상 실측 원장이 없다 — 값의 출처가 사라졌다"
    import json
    rows = json.loads(ledger.read_text(encoding="utf-8"))
    assert len(rows) == 20, f"원장이 20채널이어야 한다(현재 {len(rows)})"
    assert all(r.get("n", 0) >= 1 for r in rows), "채널마다 최소 1편은 실제로 읽어야 한다"


def test_bar_text_is_readable_on_bar():
    """★띠색과 글자색이 같으면 채널명이 사라진다(실측: 흰 띠+흰 글씨가 나왔다)."""
    def lum(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    for k, v in NEW.items():
        if v["bar_h"] == 0:
            continue
        assert abs(lum(v["bar"]) - lum(v["on_bar"])) >= 0.2, (
            f"{k}: 띠({v['bar']})와 글자({v['on_bar']})가 구분이 안 된다")


def test_icons_are_known_names():
    """★아이콘 이름이 그리기 표에 없으면 조용히 안 그려진다.
    (제미니는 '햄버거'·'hamburger'·'☰'를 섞어 준다 — 생성기가 한 값으로 모은다)"""
    for k, v in NEW.items():
        for side in ("left_icon", "right_icon"):
            name = v.get(side, "none")
            assert name in df._ICONS or name == "none", f"{k}: 모르는 아이콘 {name}"


def test_design_variety_is_real():
    """★20종이 실제로 달라야 한다 — 손으로 찍으면 비슷해지고, 실측이면 갈린다."""
    assert len({v["bar"] for v in NEW.values()}) >= 14, "띠 색이 너무 비슷하다"
    assert len({v["headcopy"]["color2"] for v in NEW.values()}) >= 14, "헤드라인 색이 너무 비슷하다"
    assert len({(v.get("left_icon"), v.get("right_icon")) for v in NEW.values()}) >= 4, "아이콘 조합이 단조롭다"
