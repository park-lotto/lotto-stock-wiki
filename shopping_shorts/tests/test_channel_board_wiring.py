"""채널 리더보드 UI + account 목록 숨김 배선 가드(정적)."""
import pathlib

SRC = (pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_board_wired_and_accounts_hidden():
    # account 시드는 유튜브에서 칩으로 안 뿌림(요약으로 접음)
    assert "s.kind!=='account'" in SRC
    assert "채널 지표·관리 열기" in SRC
    # 리더보드 함수 + 엔드포인트 + 정렬키 4종
    assert "async function openChannelBoard" in SRC
    assert "async function renderChannelBoard" in SRC
    assert "/api/youtube/channels?sort=" in SRC
    for k in ["views", "speed", "density", "accel"]:
        assert f"'{k}'" in SRC
