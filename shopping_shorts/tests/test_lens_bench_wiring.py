"""렌즈→유튜브 벤치등록 프론트 배선 가드(정적)."""
import pathlib

SRC = (pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_bulk_and_percard_bench_buttons_wired():
    # 대량 버튼 + 카드별 버튼 + 핸들러 + 엔드포인트 호출이 모두 있어야 함
    assert "lensBenchAllYoutube(" in SRC
    assert "lensBenchOne(" in SRC
    assert "async function lensBenchAllYoutube" in SRC
    assert "async function lensBenchOne" in SRC
    assert "/api/seeds/from_youtube_videos" in SRC
    # 카드별 버튼은 유튜브 항목에서만 노출
    assert "i.platform==='youtube'?" in SRC
