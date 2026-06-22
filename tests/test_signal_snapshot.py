from pipeline import build_signal_snapshot as b


def test_score_stock_vacancy_required():
    # 빈집 없으면 다른 플래그 다 있어도 0점 (후순위)
    s = {"flags": {"빈집": 0, "수출": 1, "컨센신고가": 1, "어닝서프": 1,
                   "판가": 1, "미국커플링": 1, "정책": 1, "D30": 1}}
    assert b.score_stock(s) == 0


def test_score_stock_sum():
    s = {"flags": {"빈집": 2, "수출": 1, "컨센신고가": 1, "어닝서프": 0,
                   "판가": 0, "미국커플링": 0, "정책": 0, "D30": 0}}
    assert b.score_stock(s) == 4


def test_score_stock_max():
    s = {"flags": {k: (2 if k == "빈집" else 1)
                   for k in ["빈집", "수출", "컨센신고가", "어닝서프",
                             "판가", "미국커플링", "정책", "D30"]}}
    assert b.score_stock(s) == 9


def test_build_snapshot_shape():
    snap = b.build_snapshot(
        macro={"verdict": "GO", "reasons": [{"label": "미장", "ok": True, "detail": "+0.8%"}]},
        lead_sectors=["반도체"],
        stocks=[{"name": "테스트", "code": "0", "sector": "반도체", "vacancy": "A",
                 "rs": 1.0, "flags": {"빈집": 2}, "score": 2}],
    )
    assert snap["stage1"]["verdict"] == "GO"
    assert snap["stage2"]["sectors"][0]["name"] == "반도체"
    assert snap["stage3"]["stocks"][0]["name"] == "테스트"
    assert "date" in snap and "generated_at" in snap
