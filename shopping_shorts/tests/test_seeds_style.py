"""유튜브 시드에 발굴 스타일·채널명을 붙인다(2026-08-21).

사장님 "신기템이 어디서 볼 수 있나" — 발굴이 축별로 채널을 모으는데 화면에서 읽는 곳이
한 군데도 없었다(channel_styles를 조회하는 API가 앱에 0건). 모아만 놓고 못 보면 없는 것과 같다.
"""
import sqlite3

from shopping_shorts.store import Store


def _store(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    with sqlite3.connect(st.db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS channel_styles ("
                  "channel_id TEXT PRIMARY KEY, title TEXT, style TEXT, set_at TEXT)")
        c.execute("INSERT INTO channel_styles VALUES(?,?,?,?)",
                  ("UCabc123", "꿀템 보물찾기", "신기템", ""))
    return st


def test_유튜브_시드에_스타일과_이름이_붙는다(tmp_path):
    st = _store(tmp_path)
    st.add_seed("youtube", "account", "https://www.youtube.com/channel/UCabc123")
    item = [s for s in st.list_seeds("youtube") if s["kind"] == "account"][0]
    assert item["style"] == "신기템"
    assert item["name"] == "꿀템 보물찾기"


def test_스타일_모르는_채널은_빈칸이다(tmp_path):
    """발굴에 안 잡힌 손등록 채널 — 빈칸이어야지 오류가 나면 목록 전체가 죽는다."""
    st = _store(tmp_path)
    st.add_seed("youtube", "account", "https://www.youtube.com/channel/UCzzz999")
    item = [s for s in st.list_seeds("youtube") if s["kind"] == "account"][0]
    assert item["style"] == "" and item["name"] == ""


def test_다른_플랫폼은_스타일을_안_붙인다(tmp_path):
    """인스타는 사람이 지정하는 카테고리를 쓴다 — 축이 다르다."""
    st = _store(tmp_path)
    st.add_seed("instagram", "account", "someone")
    assert "style" not in st.list_seeds("instagram")[0]


def test_스타일_테이블이_없어도_목록은_나온다(tmp_path):
    """발굴을 한 번도 안 돌린 환경 — 여기서 죽으면 관리페이지가 통째로 빈다."""
    st = Store(str(tmp_path / "n.db"))
    st.add_seed("youtube", "account", "https://www.youtube.com/channel/UCq1")
    assert len(st.list_seeds("youtube")) == 1


def test_유튜브_랭킹에_스타일이_붙는다(tmp_path):
    """2026-08-21 사장님 "신기템이 어디서 볼 수 있나".

    실측: 유튜브 수집분 9,499건 중 이미 신기템 채널 영상이 77건 있었다
    (연예인결합 1,034 · 썰쇼핑 626 · 레시피쇼핑 311). 데이터는 있고 이름표만 없었다.
    """
    from shopping_shorts.app import _attach_channel_style
    st = _store(tmp_path)
    items = [{"username": "UCabc123"}, {"username": "UCzzz999"}]
    _attach_channel_style(items, st, "youtube")
    assert items[0]["style"] == "신기템"
    assert items[1]["style"] == "", "발굴에 없는 채널은 빈칸이어야 한다"


def test_인스타는_스타일을_안_붙인다(tmp_path):
    """인스타 username은 핸들이라 이 표와 축이 다르다 — 붙이면 엉뚱한 채널에 이름표가 간다."""
    from shopping_shorts.app import _attach_channel_style
    st = _store(tmp_path)
    items = [{"username": "UCabc123"}]
    _attach_channel_style(items, st, "instagram")
    assert "style" not in items[0]


def test_스타일표가_없어도_랭킹은_산다(tmp_path):
    from shopping_shorts.app import _attach_channel_style
    st = Store(str(tmp_path / "n2.db"))
    items = [{"username": "UCq"}]
    _attach_channel_style(items, st, "youtube")
    assert items == [{"username": "UCq"}]


def test_신기템은_영상_제목도_본다(tmp_path):
    """채널 축만 믿으면 그 채널의 다른 장르가 딸려온다(2026-08-21 브라우저 실측).

    신기템 채널 15곳의 영상 77건에 포켓몬고·트로트가 섞여 있었다 — 채널 문턱을 넘겼을
    뿐 나머지 편수는 다른 장르인 채널들이다.
    """
    from shopping_shorts.app import _attach_channel_style
    st = _store(tmp_path)
    items = [
        {"username": "UCabc123", "caption": "나만 몰랐던 불편 해결 쿠팡 아이디어템 BEST3"},
        {"username": "UCabc123", "caption": "고인물만 알아보는 ㅈ된 상황 [포켓몬고]"},
        {"username": "UCabc123", "caption": "성공 확언 트로트 :울타리를 깨고"},
    ]
    _attach_channel_style(items, st, "youtube")
    assert items[0]["style"] == "신기템"
    assert items[1]["style"] == "", "같은 채널이라도 게임 영상은 축이 아니다"
    assert items[2]["style"] == "", "같은 채널이라도 트로트는 축이 아니다"


def test_영문_딴장르도_막는다(tmp_path):
    """2026-08-21 2차 실측 — 한글 차단어만 넣었더니 같은 트로트 채널의 영문 제목이 통과했다."""
    from shopping_shorts.app import _attach_channel_style
    st = _store(tmp_path)
    items = [{"username": "UCabc123", "caption": "Success Affirmation Trot: One Small Step"}]
    _attach_channel_style(items, st, "youtube")
    assert items[0]["style"] == ""


def test_레시피는_영상이_요리일_때만(tmp_path):
    """2026-08-21 사장님 "레시피에 들어간건 매칭이 많이 안돼".

    실측: 레시피 축 311건 중 실제 레시피 87건(28%)뿐. 범인은 '만들기'였다 —
    슬라임·캔디백 공예가 전부 "만들기"라 통째로 들어왔다(키포kipo 채널).
    """
    import sqlite3
    from shopping_shorts.app import _attach_channel_style
    st = Store(str(tmp_path / "r.db"))
    with sqlite3.connect(st.db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS channel_styles ("
                  "channel_id TEXT PRIMARY KEY, title TEXT, style TEXT, set_at TEXT)")
        c.execute("INSERT INTO channel_styles VALUES(?,?,?,?)",
                  ("UCfood", "키포kipo", "레시피쇼핑", ""))
    items = [
        {"username": "UCfood", "caption": "에어프라이어 반찬 만들기 초간단 #추천"},
        {"username": "UCfood", "caption": "다이소 재료로 구슬 파삭 캔디백 만들기 #슬라임"},
        {"username": "UCfood", "caption": "ASMR 다이소재료로 식빵 크런치 스퀴시"},
    ]
    _attach_channel_style(items, st, "youtube")
    assert items[0]["style"] == "레시피쇼핑"
    assert items[1]["style"] == "", "공예 '만들기'는 요리가 아니다"
    assert items[2]["style"] == "", "ASMR 스퀴시는 요리가 아니다"
