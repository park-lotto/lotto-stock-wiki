"""🔎 장면 강조(원형 돋보기 / 스포트라이트) — 2026-08-30 사장님
"장면꾸미기에서 강조하고싶은것들 수동하게".

지켜야 하는 것:
  ① 해석은 scene_hl_of **한 곳**에서만 — 화면과 렌더가 같은 뜻을 봐야 한다(0순위-B)
  ② 강조가 없으면 필터가 **한 글자도** 안 붙는다(기존 렌더 완전 무변경)
  ③ 등장 성장은 비트의 **첫 컷에서만** — 컷마다 튀면 여러 번 나오는 것처럼 보인다
"""
import re
import pytest

from shopping_shorts import video_assemble as V


# ── ① 해석(scene_hl_of) ────────────────────────────────────────────────
def test_no_highlight_by_default():
    assert V.scene_hl_of({}) is None
    assert V.scene_hl_of({"scene_hl": {"on": False}}) is None
    assert V.scene_hl_of(None) is None
    assert V.scene_hl_of("문자열") is None            # 타입 확인 전 .get() 금지


def test_defaults_and_clamps():
    hl = V.scene_hl_of({"scene_hl": {"on": True}})
    assert hl["mode"] == "zoom" and hl["cx"] == 0.5 and hl["cy"] == 0.5

    # 범위 밖 값은 가둔다 — 화면이 이상한 값을 보내도 렌더가 깨지면 안 된다
    hl = V.scene_hl_of({"scene_hl": {"on": True, "cx": 9, "cy": -3, "r": 0.001, "zoom": 99}})
    assert (hl["cx"], hl["cy"]) == (1.0, 0.0)
    assert hl["r"] == 0.06                            # 점으로 보이는 크기는 막는다
    assert hl["zoom"] == 4.0

    # 숫자가 아니면 기본값 — 예외로 렌더를 죽이지 않는다
    hl = V.scene_hl_of({"scene_hl": {"on": True, "cx": "왼쪽", "r": None}})
    assert hl["cx"] == 0.5 and hl["r"] == 0.28


def test_mode_is_only_zoom_or_spot():
    assert V.scene_hl_of({"scene_hl": {"on": True, "mode": "spot"}})["mode"] == "spot"
    assert V.scene_hl_of({"scene_hl": {"on": True, "mode": "이상한값"}})["mode"] == "zoom"


# ── ② 필터 생성(highlight_fc) ──────────────────────────────────────────
BASE = "scale=100:200,crop=10:20"


def test_no_highlight_means_no_filter():
    """★강조를 안 쓰면 None — 호출부가 종전 -vf 경로를 그대로 탄다(회귀 0)."""
    assert V.highlight_fc({}, BASE) is None


def test_zoom_mode_chain_shape():
    beat = {"scene_hl": {"on": True, "mode": "zoom", "cx": 0.5, "cy": 0.5, "r": 0.25, "zoom": 2.0}}
    fc = V.highlight_fc(beat, BASE)
    assert fc.startswith(f"[0:v]{BASE}[base];")       # 기존 크롭이 먼저, 강조는 그 위
    assert fc.endswith("[out]")                       # 호출부가 -map "[out]"으로 받는다
    assert "alphamerge" in fc and "split" in fc
    # ★마스크는 한 장만 만들고 loop로 돌린다 — 프레임마다 geq를 돌리면 4.3배 느려진다(실측)
    assert fc.count("loop=loop=-1:size=1") == 2       # 원 마스크 + 테두리
    assert "eval=frame" in fc                         # 성장은 scale로(마스크 재계산 아님)


def test_spot_mode_darkens_outside_and_has_no_magnifier():
    beat = {"scene_hl": {"on": True, "mode": "spot", "r": 0.25}}
    fc = V.highlight_fc(beat, BASE)
    assert "[dark]" in fc and "fade=t=in" in fc
    assert "alphamerge" not in fc                     # 확대를 안 하므로 패치도 없다
    assert f"s={V._OUT_W}x{V._OUT_H}" in fc           # 전면 어둡기 레이어


def test_grow_only_on_first_cut():
    """★같은 비트가 컷 여러 개로 쪼개져도 원은 **한 번만** 톡 커진다."""
    beat = {"scene_hl": {"on": True, "mode": "zoom"}}
    first = V.highlight_fc(beat, BASE, grow=True)
    later = V.highlight_fc(beat, BASE, grow=False)
    assert f"t/{V._HL_GROW}" in first
    assert f"t/{V._HL_GROW}" not in later             # 둘째 컷부터는 처음부터 완성 크기
    assert "fade=t=in" not in V.highlight_fc(
        {"scene_hl": {"on": True, "mode": "spot"}}, BASE, grow=False)


def test_center_is_pixel_of_output_frame():
    """비율 → 픽셀 변환이 출력 해상도 기준인지(화면에서 누른 자리와 같은 자리)."""
    hl = V.scene_hl_of({"scene_hl": {"on": True, "cx": 0.25, "cy": 0.75, "r": 0.1}})
    cx, cy, r = V._hl_px(hl)
    assert cx == round(0.25 * V._OUT_W)
    assert cy == round(0.75 * V._OUT_H)
    assert r == round(0.1 * V._OUT_W)                 # 반지름은 **폭** 기준(원이 원이 되게)


def test_highlight_is_independent_of_scene_zoom():
    """확대와 강조는 따로 논다 — 같이 걸어도 서로를 지우지 않는다."""
    beat = {"scene_zoom": 2.0, "scene_pan_x": 0.1,
            "scene_hl": {"on": True, "mode": "spot"}}
    z, px, _ = V.scene_zoom_of(beat)
    assert z == 2.0 and abs(px - 0.1) < 1e-9
    assert V.scene_hl_of(beat)["mode"] == "spot"
    base = V._base_zoom_vf(beat)
    fc = V.highlight_fc(beat, base)
    assert fc.startswith(f"[0:v]{base}[base];")       # 확대 구도 위에 강조가 얹힌다


@pytest.mark.parametrize("mode", ["zoom", "spot"])
def test_filtergraph_labels_are_balanced(mode):
    """라벨을 만든 만큼 쓰는지 — 하나라도 안 맞으면 ffmpeg가 통째로 죽는다."""
    fc = V.highlight_fc({"scene_hl": {"on": True, "mode": mode}}, BASE)
    made = re.findall(r"\[(\w+)\](?=;|$)", fc)                 # 체인 끝에서 만든 라벨
    for label in made:
        if label == "out":
            continue
        assert fc.count(f"[{label}]") >= 2, f"{label} 라벨을 만들고 안 썼다"


# ── 모양(2026-08-30 사장님 "돋보기 기능은 모양 변경가능하게") ────────────────
def test_shape_default_and_values():
    assert V.scene_hl_of({"scene_hl": {"on": True}})["shape"] == "circle"
    assert V.scene_hl_of({"scene_hl": {"on": True, "shape": "round"}})["shape"] == "round"
    # 모르는 모양은 원으로 — 렌더가 빈 마스크를 그리는 일이 없게
    assert V.scene_hl_of({"scene_hl": {"on": True, "shape": "별"}})["shape"] == "circle"


def test_shape_changes_the_exponent_everywhere():
    """★마스크·테두리·어둡기가 **같은 거리식**을 쓴다 — 하나만 바뀌면 모양이 어긋난다."""
    circle = V.highlight_fc({"scene_hl": {"on": True, "shape": "circle", "mode": "spot"}}, BASE)
    round_ = V.highlight_fc({"scene_hl": {"on": True, "shape": "round", "mode": "spot"}}, BASE)
    assert ",2)" in circle and ",4)" in round_          # 지수 2 = 원 / 4 = 둥근네모
    assert circle != round_
    # 둥근네모에는 원 지수가 한 번도 안 남아 있어야 한다(섞이면 테두리만 원이 된다)
    assert "pow(abs(X-" in round_ and ",2)" not in round_


def test_shape_reaches_both_layers_in_zoom_mode():
    fc = V.highlight_fc({"scene_hl": {"on": True, "shape": "round", "mode": "zoom"}}, BASE)
    assert fc.count("pow(abs(X-") == 2                  # 마스크 1 + 테두리 1
