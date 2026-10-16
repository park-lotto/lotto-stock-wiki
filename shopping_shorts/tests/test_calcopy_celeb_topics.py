# -*- coding: utf-8 -*-
"""얜샷템 소재 순위(tools/calcopy/celeb_topics.py) — 진짜 RSS 2개(안나픽·만템, 2026-10-17 저장)로 파싱·속도·배수·묶음·증가량.
정답은 픽스처 XML 에서 사람이 읽은 값: 안나픽 nt6WIGFmILE = 2026-10-16T02:00:05Z 업로드, 조회 169,197 / 박세리 면세점은
안나픽(0DRKN0415Qo)·만템(BzEO7-_uXkQ) 두 채널에 같이 떴고 장윤정은 두 채널에 있지만 제품이 달라(수건 / 소파) 묶이면 안 된다.
사보타주: speed()에서 MIN_HOURS 를 빼거나, _share()를 '인물만 같으면 묶음'으로 바꾸면 빨강이어야 한다."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import celeb_topics as ct  # noqa: E402

FX = ROOT / "channel" / "yanshottem" / "fixtures"
NAMES = {"박세리", "장윤정", "이영자", "최은경"}
NOW = datetime(2026, 10, 16, 18, 0, 5, tzinfo=timezone.utc)   # 안나픽 최신 영상 업로드 + 정확히 16시간


def _vids():
    out = []
    for fn, cid in (("annapick", "A"), ("mantem", "M")):
        g = ct.parse_feed((FX / f"{fn}.xml").read_text(encoding="utf-8"))
        out += [dict(v, cid=cid, cname=g["name"]) for v in g["videos"]]
    return out


CH = {"A": {"조회중앙": 28500, "연예인템비율": 0.98}, "M": {"조회중앙": 23000, "연예인템비율": 0.78}}


def test_parse_feed_real():
    g = ct.parse_feed((FX / "annapick.xml").read_text(encoding="utf-8"))
    assert g["name"] == "안나픽" and len(g["videos"]) == 15
    v = g["videos"][0]
    assert v["id"] == "nt6WIGFmILE" and v["views"] == 169197 and v["published"].startswith("2026-10-16T02:00:05")
    assert v["url"] == "https://www.youtube.com/shorts/nt6WIGFmILE" and "이영자" in v["title"]


def test_speed_and_multiple():
    v = ct.parse_feed((FX / "annapick.xml").read_text(encoding="utf-8"))["videos"][0]
    h = ct.hours_since(v["published"], NOW)
    assert abs(h - 16.0) < 1e-6
    assert abs(ct.speed(v["views"], h) - 169197 / 16) < 1e-6        # 10,574.8 /h
    assert ct.speed(1000, 0.1) == 500.0                              # 갓 올린 영상은 2시간으로 눌러 계산
    assert ct.multiple(169197, 28500) == 5.94 and ct.multiple(10, 0) is None


def test_bundle_same_person_same_product_only():
    rows = ct.rank(_vids(), CH, NAMES, NOW)
    by = {(r["인물"], r["제품"]): r for r in rows}
    se = [r for r in rows if r["인물"] == "박세리"]
    assert len(se) == 1 and se[0]["채널수"] == 2 and "면세점" in se[0]["제품"]       # 안나픽 + 만템 묶음
    yj = [r for r in rows if r["인물"] == "장윤정"]
    assert len(yj) >= 3 and all(r["채널수"] == 1 for r in yj)                      # 수건 / 소파 / 아버지는 서로 다른 소재
    assert rows[0]["순위"] == 1 and all(rows[i]["점수"] >= rows[i + 1]["점수"] for i in range(len(rows) - 1))
    assert by  # 비어 있지 않음


def test_bundle_outranks_single_of_same_speed():
    # 같은 영상이라도 두 채널에 뜬 묶음은 점수가 더 크다
    rows = ct.rank(_vids(), CH, NAMES, NOW)
    se = next(r for r in rows if r["인물"] == "박세리")
    solo = max(m["speed"] for m in se["묶음"])
    assert se["점수"] > solo * 0.78 * 1.0 and len(se["묶음"]) == 2


def test_growth_from_previous_run():
    vids = _vids()
    prev = {"nt6WIGFmILE": (NOW.timestamp() - 2 * 3600, 169197 - 2000)}   # 2시간 전엔 2,000 적었다 → 1,000/h
    rows = ct.rank(vids, CH, NAMES, NOW, prev)
    top = next(r for r in rows if r["대표"]["id"] == "nt6WIGFmILE")
    assert top["대표"]["growth"] == 1000.0
    assert all(r["대표"]["growth"] is None for r in rows if r["대표"]["id"] != "nt6WIGFmILE")


def test_person_is_earliest_name_and_stable():
    assert ct.find_person("박세리가 장윤정 수건 쟁여", NAMES) == "박세리"
    assert ct.find_person("수건 쟁여 장윤정이 박세리와", NAMES) == "장윤정"
    assert ct.find_person("주박세리 아님", NAMES) is None             # 앞 글자가 한글이면 다른 낱말


def test_name_dict_needs_three_hits_and_surname():
    titles = ["김나영이 쓰는 크림", "김나영의 립밤", "김나영도 반한 샴푸", "최고의 선택", "최고의 템", "최고의 쿠션", "오늘이 좋다"] * 1
    nd = ct.build_name_dict(titles)
    assert "김나영" in nd and "최고의" not in nd and "오늘이" not in nd
    nd2 = ct.build_name_dict(["짠순이가 쓰는", "짠순이는 안 사는", "짠순이도 반한"])   # 성씨 아닌 글자로 시작 → 인물 아님
    assert "짠순이" not in nd2


def test_longer_name_wins_when_same_position():
    assert ct.find_person("제니퍼 로페즈 립밤", {"제니", "제니퍼"}) == "제니퍼"


def test_source_text():
    assert ct.source_text("요약\n※ 영상 출처: 빅마마 이혜정\n#태그") == "※ 영상 출처: 빅마마 이혜정"
    assert ct.source_text("요약만") == ""
