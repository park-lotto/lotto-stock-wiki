"""유튜브 구독자 대비 지표 + 플랫폼별 지표 이름 (2026-08-24 사장님 지시).

## 사장님 지시

*"이름고치고 유뷰트대로 구독자대비로 해줘"*

두 가지다:
1. **이름** — 탭·카드 글자가 플랫폼마다 달라야 한다. 유튜브에서 `speed`는 실제로
   **조회수÷시간**인데 화면엔 "시간당댓글"이라 적혀 거짓말을 하고 있었다
   (툴팁만 `TAB_TIP`으로 갈려 있었고 글자는 한 벌).
2. **구독자 대비** — 유튜브는 `followers`가 통째로 None이라 🙌 탭이 항상 0이었다.
   수집이 `videos.list`만 불러 subscriberCount를 아예 안 가져왔기 때문.

## 이 파일이 지키는 것

- `build_youtube_items`가 subs를 받으면 followers·fan_density를 채운다
- subs가 없으면 **조용히 0이 되지 않는다**(None으로 남아 카드가 그 줄을 안 그린다)
  ★이게 인스타에서 이미 밟은 함정이다 — 값이 없는데 0으로 채우면 "반응 0%"라는
  거짓 정보가 되고 정규화(apply_grades)에서 구조적으로 최하위가 된다.
- 라벨 표는 플랫폼×지표 모두를 덮는다(빠뜨리면 그 조합만 옛 이름으로 샌다)
"""
import datetime
import json
import pathlib
import re

import pytest

from shopping_shorts import ranking

HTML = pathlib.Path(__file__).resolve().parents[1].joinpath(
    "static", "index.html").read_text(encoding="utf-8")

NOW = datetime.datetime(2026, 8, 24, 12, 0, tzinfo=datetime.timezone.utc)


def _raw(**kw):
    base = {"video_id": "v1", "channel_id": "UC1", "channel_title": "살림킹왕짱",
            "title": "테스트", "thumbnail": "",
            "published_at": (NOW - datetime.timedelta(hours=10)).isoformat(),
            "views": 50000, "likes": 900, "comments": 100}
    base.update(kw)
    return base


def _build(raw_list, subs=None):
    return ranking.build_youtube_items(
        raw_list, lambda s: None, lambda s: None,
        now=NOW, window_hours=48, subs=subs)


# ── ① 구독자 대비 지표 ────────────────────────────────────────────────
def test_speed_is_views_per_hour_not_comments():
    """유튜브 speed는 조회수÷시간이다(이름 고치기의 근거 — 회귀 방지)."""
    it = _build([_raw()])[0]
    assert it["speed"] == pytest.approx(50000 / 10)


def test_subscribers_fill_followers_and_fan_density():
    """구독자를 넘기면 followers·fan_density가 채워진다."""
    it = _build([_raw()], subs={"UC1": 200000})[0]
    assert it["followers"] == 200000
    # 구독자 대비 = 조회수 ÷ 구독자 (유튜브는 조회수 기반 축이다)
    assert it["fan_density"] == pytest.approx(50000 / 200000)


def test_missing_subscribers_stay_none_not_zero():
    """★구독자를 모르면 None으로 남는다 — 0으로 채우면 '반응 0%' 거짓말이 되고
    정규화에서 구조적 최하위가 된다(인스타 density가 실제로 밟은 함정)."""
    it = _build([_raw()])[0]
    assert it["followers"] is None
    assert it["fan_density"] is None


def test_zero_subscriber_channel_does_not_divide_by_zero():
    """구독자 0(비공개 채널)은 나눗셈이 터지면 안 되고 None으로 떨어진다."""
    it = _build([_raw()], subs={"UC1": 0})[0]
    assert it["fan_density"] is None


def test_subs_for_other_channels_do_not_leak():
    """다른 채널의 구독자가 잘못 붙으면 안 된다(채널ID로만 짝짓는다)."""
    it = _build([_raw()], subs={"UC_OTHER": 999999})[0]
    assert it["followers"] is None


def test_small_channel_outranks_big_one_on_fan_density():
    """작은 채널의 대박을 잡는 눈 — 이 지표를 넣는 이유 자체를 검사한다."""
    big = _raw(video_id="big", channel_id="UCbig", views=100000)
    small = _raw(video_id="small", channel_id="UCsmall", views=50000)
    items = _build([big, small], subs={"UCbig": 5000000, "UCsmall": 10000})
    ranked = sorted(items, key=lambda i: i.get("fan_density") or 0, reverse=True)
    assert ranked[0]["shortcode"] == "small", "구독자 대비로는 작은 채널이 위여야 한다"


def test_apply_grades_still_works_with_none_fan_density():
    """fan_density가 None인 항목이 섞여도 등급 계산이 안 터진다."""
    items = _build([_raw(), _raw(video_id="v2", channel_id="UC2")], subs={"UC1": 100000})
    ranking.apply_grades(items)
    assert all("grade" in i for i in items)


def test_subs_is_optional_backwards_compatible():
    """기존 호출부(subs 없이)가 그대로 돌아야 한다."""
    items = ranking.build_youtube_items(
        [_raw()], lambda s: None, lambda s: None, now=NOW, window_hours=48)
    assert items and items[0]["followers"] is None


# ── ② 플랫폼별 지표 이름 ──────────────────────────────────────────────
def _metric_labels():
    """index.html의 METRIC_LABELS 표를 꺼내 JSON으로 읽는다."""
    m = re.search(r"const METRIC_LABELS\s*=\s*(\{.*?\n\});", HTML, re.S)
    assert m, "METRIC_LABELS 표를 못 찾았다"
    txt = m.group(1)
    txt = re.sub(r"//[^\n]*", "", txt)                  # 주석 제거
    txt = re.sub(r"(\w+)\s*:", r'"\1":', txt)           # 키에 따옴표
    txt = txt.replace("'", '"')
    txt = re.sub(r",(\s*[}\]])", r"\1", txt)            # 트레일링 콤마
    return json.loads(txt)


def test_metric_labels_cover_every_platform():
    """플랫폼을 빠뜨리면 그 탭만 옛 이름으로 샌다."""
    labels = _metric_labels()
    for p in ("instagram", "youtube", "threads", "tiktok", "xiaohongshu"):
        assert p in labels, f"{p} 라벨이 없다"


def test_youtube_speed_label_says_views_not_comments():
    """★본 건 — 유튜브에서 '시간당댓글'이라고 쓰면 거짓말이다."""
    yt = _metric_labels()["youtube"]
    assert "조회" in yt["speed"], f"유튜브 speed 라벨이 조회 기반이 아니다: {yt['speed']}"
    assert "댓글" not in yt["speed"], f"유튜브 speed에 '댓글'이 남아 있다: {yt['speed']}"


def test_instagram_labels_unchanged():
    """인스타는 댓글 기반 그대로다(회귀 방지)."""
    ig = _metric_labels()["instagram"]
    assert ig["speed"] == "시간당댓글"
    assert ig["density"] == "조회수당댓글"
    assert ig["fan_density"] == "팔로워당댓글"


def test_youtube_fan_density_label_says_subscribers():
    """유튜브는 '팔로워'가 아니라 '구독자'다."""
    yt = _metric_labels()["youtube"]
    assert "구독" in yt["fan_density"], f"유튜브 fan_density 라벨: {yt['fan_density']}"


def test_labels_are_applied_to_tabs_and_cards():
    """표만 있고 안 쓰면 화면은 그대로다 — 두 곳 다 표를 읽어야 한다."""
    assert "applyMetricLabels" in HTML, "라벨을 탭에 입히는 함수가 없다"
    # 카드도 하드코딩된 옛 이름이 아니라 표를 읽어야 한다
    card_seg = HTML[HTML.index("function cardHtml") if "function cardHtml" in HTML else 0:]
    assert "_mlabel(" in HTML, "카드가 라벨 표를 안 읽는다"


def test_no_hardcoded_old_label_left_in_card_markup():
    """카드 마크업에 '시간당댓글'을 그대로 박아두면 유튜브에서 또 거짓말한다."""
    # <b>${...}</b> 형태의 카드 stat 줄에 옛 이름이 리터럴로 남아있지 않아야 한다
    for lit in ("<span>시간당댓글</span>", "<span>조회수당댓글</span>",
                "<span>팔로워당댓글</span>"):
        assert lit not in HTML, f"카드에 옛 라벨이 하드코딩돼 있다: {lit}"


# ── ③ 구독자 수집(youtube_client.fetch_subscribers) ──────────────────
class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._p = payload or {}

    def json(self):
        return self._p


def _chan_payload(mapping):
    return {"items": [{"id": k, "statistics": {"subscriberCount": str(v)}}
                      for k, v in mapping.items()]}


def test_fetch_subscribers_returns_map(monkeypatch):
    from shopping_shorts import youtube_client as yc
    monkeypatch.setattr(yc.requests, "get",
                        lambda *a, **k: _Resp(200, _chan_payload({"UC1": 12345})))
    assert yc.fetch_subscribers(["UC1"], tokens=["k1"]) == {"UC1": 12345}


def test_fetch_subscribers_dedupes_and_batches(monkeypatch):
    """★비용 절감 — 영상 60개가 같은 채널이면 호출은 1건이어야 한다."""
    from shopping_shorts import youtube_client as yc
    calls = []

    def fake(url, params=None, timeout=None):
        calls.append(params["id"].split(","))
        return _Resp(200, _chan_payload({c: 100 for c in params["id"].split(",")}))

    monkeypatch.setattr(yc.requests, "get", fake)
    yc.fetch_subscribers(["UC1"] * 60, tokens=["k1"])
    assert len(calls) == 1 and calls[0] == ["UC1"], f"중복제거가 안 됐다: {calls}"


def test_fetch_subscribers_splits_over_fifty(monkeypatch):
    """API 상한 50 — 51개면 2번 부른다."""
    from shopping_shorts import youtube_client as yc
    calls = []

    def fake(url, params=None, timeout=None):
        ids = params["id"].split(",")
        calls.append(len(ids))
        return _Resp(200, _chan_payload({c: 100 for c in ids}))

    monkeypatch.setattr(yc.requests, "get", fake)
    yc.fetch_subscribers([f"UC{i}" for i in range(51)], tokens=["k1"])
    assert calls == [50, 1], f"청크가 잘못됐다: {calls}"


def test_fetch_subscribers_rotates_keys_on_403(monkeypatch):
    """★키 소진(403)이면 다음 키로 넘어간다 — 로테이션 안 하면 1번 키만 때린다."""
    from shopping_shorts import youtube_client as yc
    used = []

    def fake(url, params=None, timeout=None):
        used.append(params["key"])
        if params["key"] == "dead":
            return _Resp(403)
        return _Resp(200, _chan_payload({"UC1": 777}))

    monkeypatch.setattr(yc.requests, "get", fake)
    out = yc.fetch_subscribers(["UC1"], tokens=["dead", "live"])
    assert out == {"UC1": 777}
    assert used == ["dead", "live"], f"로테이션이 안 됐다: {used}"


def test_fetch_subscribers_omits_zero_and_failures(monkeypatch):
    """구독자 비공개(0)·실패는 **키를 안 만든다**(0으로 채우면 거짓 0%)."""
    from shopping_shorts import youtube_client as yc
    monkeypatch.setattr(yc.requests, "get",
                        lambda *a, **k: _Resp(200, _chan_payload({"UC1": 0})))
    assert yc.fetch_subscribers(["UC1"], tokens=["k1"]) == {}

    monkeypatch.setattr(yc.requests, "get", lambda *a, **k: _Resp(500))
    assert yc.fetch_subscribers(["UC1"], tokens=["k1"]) == {}


def test_fetch_subscribers_survives_network_error(monkeypatch):
    """네트워크 예외로 수집이 통째로 죽으면 안 된다 — 랭킹이 우선이다."""
    from shopping_shorts import youtube_client as yc

    def boom(*a, **k):
        raise yc.requests.exceptions.RequestException("down")

    monkeypatch.setattr(yc.requests, "get", boom)
    assert yc.fetch_subscribers(["UC1"], tokens=["k1"]) == {}


def test_fetch_subscribers_no_keys_is_quiet(monkeypatch):
    from shopping_shorts import youtube_client as yc
    assert yc.fetch_subscribers(["UC1"], tokens=[]) == {}


# ── ④ 수집 경로가 실제로 구독자를 싣는가(배선) ────────────────────────
def test_service_passes_subs_into_builder():
    """★표는 있는데 안 부르면 화면은 그대로다 — service가 fetch_subscribers를 쓴다."""
    src = pathlib.Path(__file__).resolve().parents[1].joinpath(
        "service.py").read_text(encoding="utf-8")
    seg = src[src.index("def _collect_youtube"):]
    seg = seg[:seg.index("\ndef ")]
    assert "fetch_subscribers" in seg, "수집이 구독자를 안 가져온다"
    assert "subs=" in seg, "build_youtube_items에 subs를 안 넘긴다"


def test_every_metric_tooltip_switches_per_platform():
    """★실브라우저에서 잡힌 버그 — fan_density 툴팁만 인스타 문구로 굳어 있었다.
    updatePlatformCopy가 세 지표를 전부 돌아야 한다(하나만 빠뜨려도 그 탭이 샌다)."""
    seg = HTML[HTML.index("function updatePlatformCopy"):]
    seg = seg[:seg.index("\nfunction ")]
    for m in ("speed", "density", "fan_density"):
        assert m in seg, f"{m} 툴팁을 안 바꾼다"


def test_youtube_has_fan_density_tooltip():
    """유튜브 fan_density 툴팁이 있어야 카드·탭이 빈 설명을 안 보인다."""
    m = re.search(r"const TAB_TIP\s*=\s*\{(.*?)\n\};", HTML, re.S)
    assert m, "TAB_TIP을 못 찾았다"
    yt = re.search(r"youtube:\s*\{(.*?)\}", m.group(1), re.S)
    assert yt and "fan_density" in yt.group(1), "유튜브 fan_density 툴팁이 없다"
    assert "구독자" in yt.group(1), "유튜브 툴팁이 구독자 기준이 아니다"
