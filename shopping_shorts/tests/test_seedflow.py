# -*- coding: utf-8 -*-
"""씨앗 흐름 — 분석·포인트·쓰기 단계가 지어낸 것·베낀 것·없는 장면을 걸러내는지(가짜 호출기)."""
import json

from shopping_shorts import seedflow as sf

SEED = ("역발상으로 돈방석 앉은 육아천재의 발명품 겉보기엔 흔해 빠진 가방처럼 보이는 이것이 레전드 육아템에 등극했는데 사실 이게 침대임 "
        "그러나 이 꿀팁의 문제점은 내려놓는 순간 리셋된다는 거 한 천재가 이 문제를 간단히 해결했다는데 바로 처음부터 침대를 가방 모양으로 만든 거임 "
        "살살 움직여 주면 곤히 잠드는데 따로 옮겨심을 필요 없이 완벽하다고 함")
SCENES = [{"id": "a-1", "role": "시연", "desc": "아기를 눕힌 채 손잡이를 들어 올린다", "use": "", "feats": ["통째로 이동"]},
          {"id": "a-2", "role": "디테일", "desc": "안쪽 메쉬 원단 클로즈업", "use": "", "feats": ["통기 메쉬"]},
          {"id": "b-1", "role": "시연", "desc": "커버를 벗겨 세탁기에 넣는다", "use": "", "feats": ["통째 세탁"]}]
AN = {"product": "이동식 아기 침대", "tone": "반말", "voice": "전해 듣는 썰", "endings": ["~는데", "~거임", "~다고 함"], "openers": [],
      "beats": [{"name": "훅", "does": "누가 무엇으로 성공했나", "text": "역발상으로 돈방석 앉은 육아천재의 발명품"},
                {"name": "미끼", "does": "정체를 숨기고 화제를 말한다", "text": "겉보기엔 흔해 빠진 가방처럼 보이는 이것이"},
                {"name": "문제", "does": "고충", "text": "내려놓는 순간 리셋된다는 거"},
                {"name": "해결", "does": "어떻게 풀었나", "text": "처음부터 침대를 가방 모양으로 만든 거임"},
                {"name": "마무리", "does": "결과", "text": "따로 옮겨심을 필요 없이 완벽하다고 함"}],
      "hooked": [{"why": "'내려놓는 순간 리셋'으로 육아인의 고충을 먼저 건드렸다", "quote": "내려놓는 순간 리셋된다는 거"}],
      "title_shape": "OO로 돈방석 앉은 OO의 발명품", "said_points": ["가방처럼 생긴 침대", "눕힌 채 옮긴다", "옮겨 심을 필요 없다"]}
PTS = [{"id": 1, "kind": "팔릴 포인트", "text": "눕힌 채 옮긴다", "hook": "눕힌 채로 통째로", "origin": "씨앗", "cuts": ["a-1"], "in_seed": True},
       {"id": 2, "kind": "팔릴 포인트", "text": "통기 메쉬라 등에 땀이 안 찬다", "hook": "여름에도 뽀송", "origin": "영상", "cuts": ["a-2"], "in_seed": False},
       {"id": 3, "kind": "팔릴 포인트", "text": "커버를 통째로 세탁기에 돌린다", "hook": "통째로 세탁기행", "origin": "영상", "cuts": ["b-1"], "in_seed": False}]


def _script(**over):
    s = {"title": "귀찮음 하나로 대박 난 육아천재의 발명품",
         "lines": [{"beat": "미끼", "text": "딱 봐선 그냥 큰 가방 같은 이게 요즘 육아맘들 사이에 퍼지고 있다는데", "points": [], "cuts": ["a-1"]},
                   {"beat": "문제", "text": "겨우 재워서 눕히자마자 눈을 번쩍 떠 버리는 그 순간이 문제였는데", "points": [1], "cuts": ["a-1"]},
                   {"beat": "해결", "text": "안쪽이 통기 메쉬라 한여름에도 등이 축축해지질 않고", "points": [2], "cuts": ["a-2"]},
                   {"beat": "해결", "text": "커버는 통째로 벗겨 세탁기에 돌려 버리면 끝이라는 거", "points": [3], "cuts": ["b-1"]},
                   {"beat": "마무리", "text": "짐이란 짐은 이거 하나로 다 줄였다고 함", "points": [], "cuts": []}]}
    s.update(over)
    return s


def test_good_script_has_no_problems():
    assert sf.problems(_script(), SEED, AN, PTS, SCENES) == []


def test_copy_ghost_cut_tone_and_new_points_are_caught():
    s = _script(); s["lines"][1]["text"] = "그러나 이 꿀팁의 문제점은 내려놓는 순간 리셋된다는 거"
    assert any("옮겼다" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))
    s = _script(); s["lines"][2]["cuts"] = ["zz-9"]
    assert any("없는 장면" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))
    s = _script(); s["lines"][4]["text"] = "짐이 정말 많이 줄었어요"
    assert any("존댓말" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))
    s = _script(); s["lines"][2]["points"] = [1]; s["lines"][3]["points"] = [1]
    assert any("씨앗에 없던 포인트" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))


def test_analyze_drops_hooked_without_real_quote():
    out = dict(AN, hooked=AN["hooked"] + [{"why": "해외 직구 1위라는 말이 먹혔다", "quote": "해외 직구 사이트에서 판매 1위를 찍었다는데"}])
    an = sf.analyze_seed(SEED, lambda p: json.dumps(out, ensure_ascii=False))
    assert [h["why"] for h in an["hooked"]] == [AN["hooked"][0]["why"]]


def test_mine_points_cleans_cuts_and_marks_seed_points():
    raw = {"points": [{"kind": "팔릴 포인트", "text": "눕힌 채 옮긴다", "hook": "", "origin": "영상", "cuts": ["a-1", "없는번호"], "in_seed": False},
                      {"kind": "흥미로운 사실", "text": "통기 메쉬라 땀이 안 찬다", "hook": "", "origin": "어딘가", "cuts": ["a-2"], "in_seed": False}]}
    pts = sf.mine_points("이동식 아기 침대", AN, SCENES, lambda p: json.dumps(raw, ensure_ascii=False))
    assert pts[0]["cuts"] == ["a-1"] and pts[0]["in_seed"] is True          # 모델은 새것이라 했지만 씨앗이 이미 말했다
    assert pts[1]["in_seed"] is False and pts[1]["origin"] == "영상" and [p["id"] for p in pts] == [1, 2]


def test_write_rewrites_once_with_the_reason():
    bad = _script(); bad["lines"][1]["text"] = "그러나 이 꿀팁의 문제점은 내려놓는 순간 리셋된다는 거"
    answers, seen = [json.dumps(bad, ensure_ascii=False), json.dumps(_script(), ensure_ascii=False)], []

    def call(p):
        seen.append(p); return answers[len(seen) - 1]
    s, probs, n = sf.write("이동식 아기 침대", SEED, AN, PTS, SCENES, call, log=lambda *_: None)
    assert n == 2 and probs == [] and "다시 써라" in seen[1] and "옮겼다" in seen[1]


def test_hook_word_swap_invented_number_and_buried_copy_are_caught():
    s = _script(title="역발상으로 돈방석 앉은 시골청년의 발명품")
    assert any("첫 줄" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))
    s = _script(); s["lines"][3]["text"] = "커버는 0.1초 만에 벗겨 세탁기에 돌려 버리면 끝이라는 거"
    assert any("없는 숫자" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))
    s = _script(); s["lines"][2]["text"] = "안쪽이 통기 메쉬라 한여름에도 등이 축축해지질 않음 그러나 이 꿀팁의 문제점은 내려놓는 순간 리셋된다는 거 그래서 다들 놀랐다고 함"
    assert any("옮겼다" in b for b in sf.problems(s, SEED, AN, PTS, SCENES))
