"""음성 듣기 엔진 — 읽기 비교가 표기 차이는 넘기고 소리 차이만 잡는지(관제 254)."""
from shopping_shorts.voice_listen import compare_reading


def test_kanji_vs_kana_is_not_error():
    assert compare_reading("お手頃価格なのに使える", "おてごろかかくなのにつかえる")["match"] == 1.0


def test_misread_is_caught_with_context():
    r = compare_reading("ダイソーに行ったら", "内装に行ったら")
    assert r["match"] < 1.0 and any("だいそ" in d["where"] for d in r["diffs"])
