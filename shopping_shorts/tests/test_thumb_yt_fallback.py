"""유튜브 썸네일 404 → 다른 규격으로 폴백 (2026-08-19).

사장님 제보: 랭킹 카드 일부가 **검은 배경에 재생버튼만** 뜬다.

## 실측 진단
- last_run 8,797건 **전부** `oardefault.jpg` 한 규격만 쓴다(100%).
- 무작위 120건 원본 조회 → **9건(7.5%)이 404**.
- 즉 카드·영상은 멀쩡하고 **썸네일 이미지만** 못 불러온다.
- `oardefault`(original aspect ratio)는 영상마다 **있을 수도 없을 수도 있는** 변형이다.
  (형식 자체는 정상 — 25건 표본에서 0% 실패였다. 일부 영상에만 없는 것.)

## 왜 프록시에서 고치나
수집 시점에 고치면 이미 쌓인 8,797건을 백필해야 한다. `/api/thumb`는 이미
만료 자가복구(`_thumb_via_oembed`)를 하는 자리라, 여기에 얹으면 **옛 데이터까지 전부** 산다.

유튜브는 같은 영상에 여러 규격을 준다:
    oardefault.jpg  ← 지금 쓰는 것(없을 수 있음)
    hqdefault.jpg   ← 거의 항상 있음
    mqdefault.jpg   ← 항상 있음
"""
from shopping_shorts.app import _yt_thumb_alternates


def test_oardefault면_대체규격을_만든다():
    alts = _yt_thumb_alternates("https://i.ytimg.com/vi/abc123/oardefault.jpg")
    assert alts, "대체 후보가 없다"
    assert any("hqdefault.jpg" in a for a in alts)
    assert any("mqdefault.jpg" in a for a in alts)


def test_영상ID를_보존한다():
    """★ID가 바뀌면 **다른 영상 썸네일**이 뜬다 — 카드↔영상 불일치가 난다."""
    for a in _yt_thumb_alternates("https://i.ytimg.com/vi/eeCsz02MuMo/oardefault.jpg"):
        assert "/vi/eeCsz02MuMo/" in a


def test_원래규격은_후보에_안_넣는다():
    """이미 404난 주소를 또 때리면 왕복만 낭비다."""
    src = "https://i.ytimg.com/vi/abc123/oardefault.jpg"
    assert src not in _yt_thumb_alternates(src)


def test_유튜브가_아니면_빈목록():
    """★인스타·틱톡 경로를 건드리면 안 된다(회귀 0)."""
    assert _yt_thumb_alternates("https://scontent.cdninstagram.com/v/x.jpg") == []
    assert _yt_thumb_alternates("https://p16.tiktokcdn.com/x.jpeg") == []
    assert _yt_thumb_alternates("") == []
    assert _yt_thumb_alternates(None) == []


def test_이미_hqdefault면_다른것을_준다():
    """hq가 404인 경우도 있다 — mq/sd로 이어간다."""
    alts = _yt_thumb_alternates("https://i.ytimg.com/vi/abc123/hqdefault.jpg")
    assert alts
    assert all("hqdefault.jpg" not in a for a in alts)


def test_쿼리스트링이_있어도_동작한다():
    alts = _yt_thumb_alternates("https://i.ytimg.com/vi/abc123/oardefault.jpg?sqp=xyz")
    assert any("hqdefault.jpg" in a for a in alts)
