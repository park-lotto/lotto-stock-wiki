"""채널별 터진 영상(2026-10-06, 관제 137) — 유튜브 '역대 히트작' 자리.

사장님: "채널 대비해서 눈에 띄게 높은 것만 / 한 채널에 2~3개 / 탭 누르면 썰이랑 홈템 구분되게".
무엇이 터진 것인가 = ranking.pick_channel_hits, 누가 나오나 = 채널 고정표(썰쇼핑·홈템).
"""
import pathlib

from shopping_shorts import ranking
from shopping_shorts.store import Store

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def _vids(views):
    return [{"id": "v%d" % i, "ch": "채널", "title": "제목%d" % i, "at": "2026-05-01T00:00:00Z", "secs": 30,
             "views": v, "likes": 0, "comments": 0} for i, v in enumerate(views)]


def test_평소의_5배_넘고_1만_넘는_상위_3편만():
    med, picks = ranking.pick_channel_hits(_vids([1000] * 9 + [900000, 500000, 300000, 200000, 4000]))
    assert med == 1000
    assert [p["views"] for p in picks] == [900000, 500000, 300000]     # 4번째(20만)는 채널당 3편에 걸려 빠진다
    assert picks[0]["hit_ratio"] == 900.0


def test_평소가_높은_채널은_배수가_모자라면_안_뽑는다():
    med, picks = ranking.pick_channel_hits(_vids([100000] * 10 + [400000, 600000]))
    assert med == 100000
    assert [p["views"] for p in picks] == [600000]      # 6배만 통과, 4배는 탈락


def test_조회수_바닥과_영상_수_바닥():
    assert ranking.pick_channel_hits(_vids([100] * 10 + [9000]))[1] == []          # 90배여도 1만 미만
    assert ranking.pick_channel_hits(_vids([1000, 1000, 500000])) == (0, [])       # 3편짜리 채널은 평소를 못 믿는다


def _store(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.save_channel_survey("UCsul", _vids([1000] * 10 + [50000]))
    st.save_channel_survey("UChome", _vids([2000] * 10 + [80000, 70000]))
    st.save_channel_survey("UCother", _vids([1000] * 10 + [90000]))
    st.set_channel_force("UCsul", "제품정체형")
    st.set_channel_force("UChome", "홈템")
    st.set_channel_force("UCother", "연예인")       # 조사는 했지만 사장님이 다른 탭으로 옮긴 채널
    return st


def test_고른_채널만_나오고_카테고리로_갈린다(tmp_path):
    items = _store(tmp_path).channel_hit_items()
    got = {(i["username"], i["category"], i["views"]) for i in items}
    assert got == {("UCsul", "제품정체형", 50000), ("UChome", "홈템", 80000), ("UChome", "홈템", 70000)}
    one = next(i for i in items if i["username"] == "UCsul")
    assert one["hit_ratio"] == 50.0 and one["channel_median"] == 1000 and one["platform"] == "youtube"
    assert one["thumbnail"].endswith("/v10/oardefault.jpg") and one["age_hours"] > 0


def test_채널을_탭에서_빼면_여기서도_빠진다(tmp_path):
    st = _store(tmp_path)
    st.set_channel_force("UCsul", "기타")
    assert {i["username"] for i in st.channel_hit_items()} == {"UChome"}


def test_다시_조사하면_통째로_갈아_끼운다(tmp_path):
    st = _store(tmp_path)
    st.save_channel_survey("UCsul", _vids([1000] * 10))      # 터진 영상이 지워졌다
    assert not [i for i in st.channel_hit_items() if i["username"] == "UCsul"]


def test_유튜브_역대_자리는_채널별_터진_영상을_준다(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    _store(tmp_path)
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    r = app_mod.api_reference(platform="youtube", archive=1)
    assert len(r["items"]) == 3 and all(i.get("hit_ratio") for i in r["items"])
    assert all("speed" in i for i in r["items"])              # 화면이 무조건 읽는 지표가 채워져 있어야 카드가 그려진다
    assert app_mod.api_reference(platform="tiktok", archive=1)["items"] == []


def test_화면_탭_이름과_유형_버튼_순서():
    assert "💥 채널별 터진 영상" in HTML and "function isChannelHitsTab()" in HTML
    order = [HTML.index('{key:"%s"' % k) for k in ("전체", "썰쇼핑", "홈템", "장비템", "차량템")]
    assert order == sorted(order), "유형 버튼 순서: 전체 · 썰쇼핑 · 홈템 · 장비 · 차량"
    # 선언 전 접근 방지 — 이 탭 판정은 SPAN_DAYS 변수가 아니라 화면의 눌린 탭에서 읽는다
    body = HTML[HTML.index("function isChannelHitsTab()"):HTML.index("function isChannelHitsTab()") + 120]
    assert "SPAN_DAYS" not in body


# ── 주 1회 다시 조사(2026-10-06 사장님 "주1회") ─────────────────────────────
def test_조사_대상은_고른_채널이고_원래_ID를_되찾는다(tmp_path):
    st = _store(tmp_path)
    st.set_channel_force("UCnoid", "홈템")           # 고정표엔 있지만(소문자) 원래 ID 를 아는 곳이 없다
    st.set_channel_force("UCseedOnly1", "홈템")      # 수집 시드 주소에서만 ID 를 알 수 있는 채널
    st.add_seed("youtube", "account", "https://www.youtube.com/channel/UCseedOnly1")
    ids, unknown = st.hit_channel_ids()
    assert set(ids) == {"UCsul", "UChome", "UCseedOnly1"} and unknown == ["ucnoid"]


def test_주간_조사는_온전히_받은_채널만_갈아_끼운다(tmp_path):
    from shopping_shorts import channel_survey as cs
    st = _store(tmp_path)
    fresh = {"UCsul": _vids([1000] * 10 + [300000]), "UChome": None}       # 홈템 채널은 쿼터로 못 받음
    r = cs.run(st, fetch=lambda cid: fresh[cid])
    assert (r["ok"], r["fail"]) == (1, ["UChome"])
    got = {(i["username"], i["views"]) for i in st.channel_hit_items()}
    assert got == {("UCsul", 300000), ("UChome", 80000), ("UChome", 70000)}   # 못 받은 채널은 지난 조사분 그대로
    assert '"ok": 1' in st.get_setting("channel_survey::last_run")


def test_한_채널_조사는_다음_장까지_넘기고_60초_넘는_것은_버린다(monkeypatch):
    from shopping_shorts import channel_survey as cs
    pages = {None: {"items": [{"contentDetails": {"videoId": "a"}}], "nextPageToken": "T"},
             "T": {"items": [{"contentDetails": {"videoId": "b"}}]}}

    def fake(url, params):
        if "playlistItems" in url:
            assert params["playlistId"] == "UUSHxyz"
            return pages[params.get("pageToken")], False
        return {"items": [{"id": "a", "snippet": {"title": "짧다", "publishedAt": "2026-01-01T00:00:00Z", "channelTitle": "채널"},
                           "contentDetails": {"duration": "PT45S"}, "statistics": {"viewCount": "123"}},
                          {"id": "b", "snippet": {"title": "길다"}, "contentDetails": {"duration": "PT2M"}, "statistics": {}}]}, False
    monkeypatch.setattr(cs, "_first_ok", fake)
    assert [(v["id"], v["views"]) for v in cs.survey_channel("UCxyz")] == [("a", 123)]
    monkeypatch.setattr(cs, "_first_ok", lambda url, params: (None, True))      # 쿼터 소진
    assert cs.survey_channel("UCxyz") is None


def test_이_탭의_기본_정렬은_조회수순():
    assert "function applyHitsDefaultSort()" in HTML and "STATE.tab = 'views'" in HTML
