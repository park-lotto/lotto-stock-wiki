"""아카이브 크롤이 채널 표시명(한글 이름)도 같이 저장한다(2026-08-06).

사장님 제보: "채널명 안 바뀐 것도 많다."
확인해 보니 이름이 **빈** 게 아니라 그 채널이 `reel_history`에 **아예 없었다**
(실측: homedukddak·on_the_home_·salim_station·kkul_sooni 전부 0행).
아카이브 채널 518개 중 434개만 수집 이력에 있고, 이름은 그중 433개에 있다
→ 이름을 못 얻는 84개는 참조할 데이터 자체가 없는 것이다.

뿌리: 아카이브 크롤러(channel_archive)는 릴스만 긁고 **채널 표시명을 안 가져왔다**.
그런데 인스타 응답 노드엔 `user.full_name`이 들어 있다(instagram_parse.parse_search_item·
instagram_playwright가 이미 같은 필드를 읽는다) — 우리가 안 읽었을 뿐이다.

★그래서 추가 요청이 0건이다. 이미 받아서 버리던 값을 주워 담는 것뿐이라
  429·계정 플래그 위험이 늘지 않는다(이 경로는 계정이 이미 차단돼 세션을 돌려쓰는 중이라
  요청을 한 건도 더 늘리면 안 된다).
"""
import pytest

from shopping_shorts.instagram_parse import parse_reel_node
from shopping_shorts.store import Store


# ── 파서: 노드에서 표시명을 꺼낸다 ────────────────────────────────
def test_parse_reel_node_extracts_owner_full_name():
    node = {"code": "ABC123", "user": {"username": "homedukddak", "full_name": "홈덕닥"}}
    it = parse_reel_node(node, "homedukddak")
    assert it["ownerFullName"] == "홈덕닥"


def test_parse_reel_node_survives_missing_user():
    """user가 없거나 이름이 비어도 죽지 않는다 — 크롤 전체가 이 한 필드로 깨지면 안 된다."""
    assert parse_reel_node({"code": "A1"}, "u")["ownerFullName"] == ""
    assert parse_reel_node({"code": "A2", "user": {}}, "u")["ownerFullName"] == ""
    assert parse_reel_node({"code": "A3", "user": {"full_name": None}}, "u")["ownerFullName"] == ""


def test_parse_reel_node_keeps_existing_keys():
    """기존 키를 하나도 잃지 않는다(회귀 방지)."""
    it = parse_reel_node({"code": "A", "like_count": 5, "play_count": 9,
                          "user": {"full_name": "이름"}}, "u")
    for k in ("shortcode", "url", "timestamp", "caption", "commentsCount",
              "likesCount", "videoViewCount", "displayUrl", "videoUrl", "ownerUsername"):
        assert k in it, f"{k} 키가 사라졌다"


# ── 저장: 표시명을 채널 이름 소스에 남긴다 ───────────────────────
def test_archive_upsert_records_display_name(tmp_path):
    """크롤이 얻은 이름이 channel_name_map()에 잡혀야 카드가 한글로 뜬다."""
    st = Store(tmp_path / "t.db")
    st.archive_upsert_many("homedukddak", [
        {"shortcode": "S1", "url": "u", "thumbnail": "t", "views": 1, "likes": 1,
         "comments": 1, "name": "홈덕닥"},
    ], "2026-08-06T00:00:00+00:00")
    assert st.channel_name_map().get("homedukddak") == "홈덕닥"


def test_archive_upsert_without_name_is_harmless(tmp_path):
    """이름을 못 얻은 채널도 릴스는 정상 저장된다(이름만 비어 있을 뿐)."""
    st = Store(tmp_path / "t.db")
    st.archive_upsert_many("noname", [
        {"shortcode": "S2", "url": "u", "thumbnail": "t", "views": 1, "likes": 1,
         "comments": 1},
    ], "2026-08-06T00:00:00+00:00")
    with st._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM channel_archive WHERE username='noname'"
                         ).fetchone()[0] == 1
    assert not st.channel_name_map().get("noname")


def test_display_name_does_not_overwrite_with_blank(tmp_path):
    """한 번 얻은 이름을 다음 크롤이 빈 값으로 덮으면 안 된다 —
    응답에 user가 없는 노드도 섞여 들어온다(위 파서 테스트 참고)."""
    st = Store(tmp_path / "t.db")
    st.archive_upsert_many("ch", [{"shortcode": "S1", "url": "u", "thumbnail": "t",
                                   "views": 1, "likes": 1, "comments": 1, "name": "좋은이름"}],
                           "2026-08-06T00:00:00+00:00")
    st.archive_upsert_many("ch", [{"shortcode": "S1", "url": "u", "thumbnail": "t",
                                   "views": 2, "likes": 1, "comments": 1, "name": ""}],
                           "2026-08-06T01:00:00+00:00")
    assert st.channel_name_map().get("ch") == "좋은이름", "빈 이름이 기존 이름을 덮었다"


# ── 크롤러 배선(요청을 안 늘렸는지) ──────────────────────────────
def test_crawler_passes_name_through_without_extra_request():
    """★핵심 안전장치: 이름을 얻으려고 **추가 조회를 하지 않는다**.
    이미 후킹해 받는 graphql 응답의 user.full_name을 주워 담을 뿐이다.
    (이 경로는 계정이 이미 차단돼 세션을 돌려쓰는 중 — 요청이 늘면 안 된다.)"""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "channel_archive.py"
           ).read_text(encoding="utf-8")
    assert "ownerFullName" in src, "크롤러가 표시명을 items에 안 싣는다"
    # 릴 상세·프로필 조회 같은 '추가 왕복'을 새로 들이지 않았는지
    for banned in ("_fetch_reel_detail", "/api/v1/users/", "web_profile_info"):
        assert banned not in src, f"추가 요청 경로가 들어왔다: {banned}"
