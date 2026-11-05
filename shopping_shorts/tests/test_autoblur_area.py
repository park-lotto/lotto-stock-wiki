"""#4808·#4835(11-04 이정민): 자동 흐림이 우리 제품 포장 글자를 남의 글자로 잡아 창의 48~65% 흐림 칸을 넣고, 면적 반려를 waive 하자
완성본 15초가 회색 블록으로 나갔다. 흐림 넣기(autoblur)와 면적 상한(blur_cut_gate)이 따로였다 — 면적 계산 주인 = render_bench.blur_share,
자동 흐림은 넣은 뒤 상한(BLUR_AREA_MAX)을 넘으면 넣지 않는다(blur_fits)."""
from tools.calcopy.hybrid import render_bench as RB


def test_면적_계산은_한_곳():
    crop = [0, 0, 1000, 1000]
    assert abs(RB.blur_share([[0, 0, 500, 500, 0, 10]], crop, 1.0, 2.0) - 0.25) < 1e-6
    assert RB.blur_share([[0, 0, 500, 500, 5, 10]], crop, 1.0, 2.0) == 0          # 컷 구간 밖 칸은 안 센다


def test_화면을_덮는_자동_흐림은_넣지_않는다():
    M = {"blur": {"a.mp4": []}}
    crop = [0, 0, 1000, 1000]
    assert RB.blur_fits(M, "a.mp4", [0, 800, 1000, 100, 0.0, 3.0], crop, 0.0, 3.0)        # 자막 띠 10% = 넣는다
    assert not RB.blur_fits(M, "a.mp4", [100, 100, 700, 700, 0.0, 3.0], crop, 0.0, 3.0)   # 49% = 장면 속 큰 글자 → 넣지 않는다
    M["blur"]["a.mp4"].append([0, 800, 1000, 100, 0.0, 3.0])
    assert not RB.blur_fits(M, "a.mp4", [0, 0, 1000, 100, 0.0, 3.0], crop, 0.0, 3.0)      # 이미 있는 칸과 합쳐 20% > 15%
