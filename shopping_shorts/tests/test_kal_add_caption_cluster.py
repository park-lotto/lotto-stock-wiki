"""자막 군집 폭·안전 폭·폭 역산 크기(표 #112·#174, Jev 해결 0.73·위험 0.47 · 11-06).

자막 칸 폭은 상수(W−80)가 아니라 벤치 자막 줄 폭 군집에서 잰다(n≥10 이면 p99, 아니면 최대 — 대역 금지).
잰 폭을 못 믿으면(caption_width_ref 와 같은 조건) 옛 상수 그대로 + 사유. UI 안전 폭(0.86W) 넘음·폭 역산 크기는 기록.
"""
from tools.calcopy.engine import to_frame as TF


def _items(ws, txt="가나다라마바사아자차카타파하"):
    return [{"lines": 1, "widths": [w], "text": [txt[:8]], "top_y": 1263} for w in ws]      # 글 길이 같은데 잰 폭이 들쭉날쭉


def test_cluster_uses_bench_widths():
    f = TF._pil_font("BMJUA", 62)
    items = []
    for n in (8, 9, 10, 11, 12, 13):
        t = "가나다라마바사아자차카타파하"[:n]
        items.append({"lines": 1, "widths": [round(f.getlength(t) * 1.08)], "text": [t], "top_y": 1263})
    notes = []
    c = TF.caption_cluster("BMJUA", 62, items, 1080, notes)
    assert c["trusted"] and c["n"] == 6 and c["stat"] == "max"           # n<10 → 최대(대역 금지)
    assert c["w"] == max(i["widths"][0] for i in items)
    assert c["size_from_w"] and abs(c["size_from_w"] - 62 * 1.08) < 2      # 폭 역산 크기
    assert "over_safe" in c


def test_cluster_untrusted_falls_back_with_reason():
    items = _items([900, 500, 950, 420, 980, 600])                            # 잰 폭이 글 길이를 안 따른다
    notes = []
    c = TF.caption_cluster("BMJUA", 62, items, 1080, notes)
    assert not c["trusted"] and c["w"] == 1080 - 2 * TF.SIDE_PAD and c["why"]


def test_p99_when_n_ge_10():
    f = TF._pil_font("BMJUA", 62)
    items = []
    for k in range(12):
        t = "가나다라마바사아자차카타파하"[: 8 + k % 6]
        items.append({"lines": 1, "widths": [round(f.getlength(t))], "text": [t], "top_y": 1})
    c = TF.caption_cluster("BMJUA", 62, items, 1080, [])
    assert c["stat"] == "p99" and c["n"] == 12


def test_size_pick_by_overlap():
    """결과물 겹침: 벤치 채움을 크기 66 으로 그려 두면 후보 중 66 을 고른다(높이 역산 39 를 고르지 않는다)."""
    import numpy as np
    from PIL import Image, ImageDraw
    txt = "한 친구의 의자만 감쪽같이"
    f = TF._pil_font("BMJUA", 66)
    l, t, r, b = f.getbbox(txt)
    im = Image.new("L", (int(r - l) + 40, int(b - t) + 40), 0)
    ImageDraw.Draw(im).text((20 - l, 20 - t), txt, font=f, fill=255)
    a = np.array(im) > 127
    ys, xs = np.where(a)
    ref = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    pk = TF.caption_size_pick("BMJUA", {"높이 역산": 39.2, "군집 폭 역산": 66.0, "없음": None}, [(ref, txt)])
    assert pk["pick"] == "군집 폭 역산" and pk["scores"]["군집 폭 역산"] > 0.9 > pk["scores"]["높이 역산"]


def test_fill_mask_ignores_far_from_outline():
    import numpy as np
    img = np.zeros((60, 200, 3), np.uint8) + 40           # 어두운 바탕
    img[10:50, 10:90] = 255                               # 외곽선 옆 흰 글(바탕이 어두워 '반대 밝기 옆')
    m = TF.caption_fill_mask(img, [255, 255, 255], None)
    assert m is not None and m.shape == (40, 80)
