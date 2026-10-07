# -*- coding: utf-8 -*-
"""관제 143 후속(10-07 사장님 제보 "⭐ 우선이 안 먹는다") — 라이브 d2ed614194c1 보드 '65':
충격_입막 줄 = 343(⭐ 아님, meme_auto 없음) → '직접 고름'으로 굳어 ⭐(189·826·605…)가 안 먹었다.
규칙(주인 storyboard.pick_is_manual): 서랍에서 직접 고른 것(meme_manual/sfx_manual)만 고정, 나머지는 자동 → ⭐ 바뀌면 다시 고른다.
⭐는 그 감정(분류) 것만. 효과음 ⭐도 같은 함수(fav_or_all·fav_ok)."""
from shopping_shorts import storyboard as sb

POOL = {"충격_입막": [{"asset_id": i, "duration": 2.0} for i in (188, 189, 341, 343, 605, 608, 826)],
        "의심_황당": [{"asset_id": i, "duration": 2.0} for i in (1089, 1090, 1091)]}
FAV = {"충격_입막": [189, 826, 605, 608, 188, 341], "감탄_박수": [224, 228]}


def _live_board_65():
    # 라이브 보드 65 모양 그대로(18:38 ⭐ 저장 전부터 있던 보드)
    return [{"slot": "title", "line": "a"},
            {"slot": "benefit", "line": "b", "meme_emotion": "의심_황당", "meme_pick": 826},
            {"slot": "twist", "line": "c", "meme_emotion": "충격_입막", "meme_pick": 343}]


def test_표식없는_옛_고름은_자동_별로_다시_고른다():
    s = _live_board_65()
    sb.meme_preview(s, POOL, FAV, key="w-d2ed614194c1")
    assert s[2]["meme_pick"] in FAV["충격_입막"] and s[2]["meme_auto"] == 1
    # 의심_황당 줄엔 다른 감정(충격_입막) ⭐가 섞이지 않는다
    assert s[1]["meme_pick"] in (1089, 1090, 1091) and s[1]["meme_auto"] == 1


def test_별를_바꾸면_자동_고름이_바뀌고_사람_고름은_그대로():
    s = [{"slot": "x", "line": "c", "meme_emotion": "충격_입막"},
         {"slot": "y", "line": "d", "meme_emotion": "충격_입막", "meme_pick": 343, "meme_manual": 1}]
    sb.meme_preview(s, POOL, {"충격_입막": [188]}, key="w")
    assert s[0]["meme_pick"] == 188
    sb.meme_preview(s, POOL, {"충격_입막": [605]}, key="w")       # ⭐ 바뀜 → 화면이 /picks 로 다시 부름
    assert s[0]["meme_pick"] == 605 and s[0]["meme_auto"] == 1
    assert s[1]["meme_pick"] == 343 and s[1]["meme_manual"] == 1 and "meme_auto" not in s[1]


def test_3단계도_같은_규칙_자동짤이_별밖이면_다시_사람짤은_그대로():
    words = [{"word": "근데", "start": 0.0, "end": 1.1}]
    beats = [{"beat_idx": 0, "narration": "근데 a", "sig_rank": 3, "signal": "근데", "meme_pick": 343, "meme_auto": 1},
             {"beat_idx": 1, "narration": "근데 b", "sig_rank": 3, "signal": "근데", "meme_pick": 341, "meme_manual": 1}]
    plan = {"beats": beats}
    sb.meme_slots(plan, lambda b: (words, 4.0), POOL, key="j", prefs={"충격_입막": [605, 608]})
    assert plan["beats"][0]["cutaway"]["asset_id"] in (605, 608)
    assert plan["beats"][1]["cutaway"]["asset_id"] == 341
    # carry_picks 가 사람 표식을 3단계로 넘긴다
    assert sb.carry_picks({"meme_pick": 9, "meme_manual": 1, "sfx_pick": 5, "sfx_manual": 1}) == \
        {"meme_pick": 9, "meme_manual": 1, "sfx_pick": 5, "sfx_manual": 1}


BANK = {"긴장": [{"asset_id": i} for i in (1450, 1451, 1452, 1453)]}


def test_효과음_별_우선_2단계_3단계_같은_소리_사람고름_유지():
    pref = {"긴장": [1453]}
    for n in range(10):
        assert sb.sfx_choose("긴장", BANK, "k%d" % n, prefs=pref)["asset_id"] == 1453
    s = [{"slot": "t", "line": "c", "meme_emotion": "충격_입막", "sfx_pick": 1450}]      # 표식 없는 옛 효과음 = 자동
    sb.sfx_preview(s, BANK, key="w", prefs=pref)
    assert s[0]["sfx_pick"] == 1453 and s[0]["sfx_auto"] == 1
    beats = [dict({"beat_idx": 0, "narration": "c", "cutaway": sb.meme_cut({"asset_id": 605}, 1.2, "충격_입막")}, **sb.carry_picks(s[0]))]
    sb.sfx_slots({"beats": beats}, BANK, key="job-other", prefs=pref)
    assert beats[0]["sfx"]["asset_id"] == 1453
    m = [{"slot": "t", "line": "c", "meme_emotion": "충격_입막", "sfx_pick": 1451, "sfx_manual": 1}]
    sb.sfx_preview(m, BANK, key="w", prefs=pref)
    assert m[0]["sfx_pick"] == 1451 and "sfx_auto" not in m[0]


def test_효과음_별_묶음_정리():
    assert sb.sfx_prefs_by_cat([{"asset_id": 2, "cat": "긴장", "rank": 2}, {"asset_id": 1, "cat": "긴장", "rank": 1}]) == {"긴장": [1, 2]}
