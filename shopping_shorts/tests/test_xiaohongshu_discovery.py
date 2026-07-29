"""샤오홍슈 계정 발굴 집계 — 순수 함수 단위 테스트.
설계: docs/superpowers/specs/2026-07-29-샤오홍슈-계정발굴-design.md"""
from shopping_shorts import xiaohongshu_discovery as disc


def _note(uid, nick, likes=0, comments=0, collects=0, shares=0, url="u", thumb="t"):
    return {"channel_id": uid, "channel_title": nick, "likes": likes,
            "comments": comments, "collects": collects, "shares": shares,
            "url": url, "thumbnail": thumb}


_SEEDS = {"주방": {"cn": ["kw1"]}}


def test_aggregates_by_author_and_sums_engagement():
    notes = {
        "kw1": [
            _note("u1", "살림요정", likes=10, comments=5),   # eng 15
            _note("u1", "살림요정", collects=5, shares=5),    # eng 10 → u1 합 25, 노트2
            _note("u2", "청소왕", likes=100),                 # eng 100, 노트1
        ],
    }
    out = disc.discover_accounts(lambda kw: notes[kw], _SEEDS, min_notes=1)
    by_id = {a["userid"]: a for a in out}
    assert by_id["u1"]["engagement_sum"] == 25
    assert by_id["u1"]["note_count"] == 2
    assert by_id["u1"]["avg_engagement"] == 12.5
    assert by_id["u2"]["engagement_sum"] == 100


def test_min_notes_filters_flukes():
    notes = {"kw1": [_note("u1", "A", likes=1), _note("u1", "A", likes=1),
                     _note("u2", "B", likes=999)]}  # u2는 노트1 → min_notes=2에 걸러짐
    out = disc.discover_accounts(lambda kw: notes[kw], _SEEDS, min_notes=2)
    assert [a["userid"] for a in out] == ["u1"]


def test_blacklist_excluded():
    notes = {"kw1": [_note("u1", "A", likes=5), _note("u1", "A", likes=5),
                     _note("bad", "쓰레기", likes=5), _note("bad", "쓰레기", likes=5)]}
    out = disc.discover_accounts(lambda kw: notes[kw], _SEEDS, min_notes=2,
                                 blacklist={"bad"})
    assert [a["userid"] for a in out] == ["u1"]


def test_sorted_by_engagement_desc_and_profile_url():
    notes = {"kw1": [_note("low", "L", likes=1), _note("low", "L", likes=1),
                     _note("hi", "H", likes=50), _note("hi", "H", likes=50)]}
    out = disc.discover_accounts(lambda kw: notes[kw], _SEEDS, min_notes=2)
    assert [a["userid"] for a in out] == ["hi", "low"]
    assert out[0]["profile_url"] == "https://www.rednote.com/user/profile/hi"


def test_notes_without_userid_dropped():
    notes = {"kw1": [_note("", "익명", likes=9), _note("", "익명", likes=9)]}
    out = disc.discover_accounts(lambda kw: notes[kw], _SEEDS, min_notes=1)
    assert out == []


def test_representative_sample_is_best_note():
    notes = {"kw1": [_note("u1", "A", likes=1, url="weak", thumb="wt"),
                     _note("u1", "A", likes=99, url="strong", thumb="st")]}
    out = disc.discover_accounts(lambda kw: notes[kw], _SEEDS, min_notes=1)
    assert out[0]["sample_url"] == "strong"
    assert out[0]["sample_thumbnail"] == "st"
