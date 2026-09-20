"""자막 줄을 바꾸면 장면 편집(실험실) 화면도 새 구절로 컷을 다시 그린다 (2026-09-11 고객 제보).

실측(cid 357, job 6534d20ee935 '대형수납함바퀴'):
  14:46 실험실 열림(자막 2덩어리 → 컷 2개로 보임)
  15:40 제작소 자막 단계에서 줄을 4개로 쪼갬(caplines 9회)
  16:15 완성본 — 서버는 지금 자막(4줄) 기준으로 컷 4개, 조각 2개를 1,2,1,2로 순환
  → 고객: "편집 땐 1번인데 완성본은 같은 장면이 두 번(앞 것은 0.57초라 살짝 스침)"

뿌리: 실험실은 열 때 한 번만 자막을 받아왔다(scene_lab.html 첫 로드). 제작소 caplines 저장은
자막 칸만 갱신하고 실험실엔 아무 신호도 안 보냈다 → 화면 컷 2개 / 완성본 컷 4개.
규칙(컷 수 = 구절 수, 조각 부족 시 순환 1,2,1,2)은 사장님 결정(09-02 · 09-11 "1212 기존으로")이라
그대로 두고, **보는 것 = 나오는 것**만 맞춘다.
"""
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[1] / "static"
_PRODUCE = (_STATIC / "produce.html").read_text(encoding="utf-8")
_LAB = (_STATIC / "scene_lab.html").read_text(encoding="utf-8")
_PLAY = (_STATIC / "scene_play.js").read_text(encoding="utf-8")


def test_제작소가_줄저장_뒤_실험실을_깨운다():
    """저장·되돌리기 두 경로 모두 — 한쪽만 깨우면 '자동으로'로 되돌린 뒤 또 어긋난다."""
    assert "function _labRefreshCaptions(beatIdx)" in _PRODUCE
    assert _PRODUCE.count("_labRefreshCaptions(_beatNo(b));") == 2, "저장·되돌리기 두 곳에서 불러야 한다"
    # 저장 성공 뒤(실패면 부르지 않는다)에 온다
    i_save = _PRODUCE.index("_capMsg('저장했어요'")
    assert _PRODUCE.index("_labRefreshCaptions(_beatNo(b));", i_save) - i_save < 300


def test_실험실에_refreshCaptions가_있고_서버자막을_다시받는다():
    assert "window.refreshCaptions = async function(i)" in _LAB
    body = _LAB[_LAB.index("window.refreshCaptions"):][:2000]
    assert "cache:'no-store'" in body, "캐시본을 받으면 옛 자막 그대로다"
    assert "DATA.captions = d.data.captions" in body
    assert "repaint()" in body, "다시 그리지 않으면 받아와도 화면은 옛 컷이다"
    # 조각·트림은 건드리지 않는다 — lists를 덮어쓰면 사람이 담은 것이 날아간다
    assert "lists = " not in body and "lists[i] =" not in body


def test_조각보다_줄이_많아도_장면수는_그대로라고_알린다():
    """행동을 요구하지 않는다(사장님 "굳이 믹스로 가서 또 2장을 넣어야 하잖아")."""
    body = _LAB[_LAB.index("window.refreshCaptions"):][:2000]
    assert "장면은 ${m}개 그대로" in body
    assert "더 담" not in body, "조각을 더 담으라는 안내는 넣지 않는다"


def test_이어붙임_규칙이_서버와_화면에_같이_있다():
    """구절 > 조각이면 1,1,2,2 (09-11 사장님). 한쪽만 바꾸면 미리보기와 결과물이 어긋난다(0순위-B)."""
    assert "Math.floor(k * segments.length / nPhrase)" in _PLAY
    assert "const idx = k % segments.length;" not in _PLAY, "순환(1,2,1,2)이 화면에 남아 있다"
    va = (Path(__file__).resolve().parents[1] / "video_assemble.py").read_text(encoding="utf-8")
    assert "(k * n_seg) // len(durs)" in va
    assert "idx = k % len(segs)" not in va, "순환(1,2,1,2)이 서버에 남아 있다"
