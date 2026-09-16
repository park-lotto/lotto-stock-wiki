# -*- coding: utf-8 -*-
"""영상 밖의 신기한 정보(wow_facts) — 대본에 "볼 이유"를 넣는 단계 (2026-09-09).

■ 왜 생겼나 — 사장님이 유튜브 21~26분 구간을 짚으며: "이렇게 간단하게 노가다로만
  해도 이런데 우리는 뭔가?"

  그 노가다의 가운데 단계가 우리에게 **없었다**. 대본 경로 전체에 웹검색 grounding이
  한 줄도 없었다(실측 grep 0건). 그래서 대본은 화면에 이미 보이는 것만 다시 말했고,
  사장님 말로 "사람들이 보게 해야 할 이유가 없어"가 됐다.

■ 여기서 못박는 계약
  · 근거 없는 훅은 **버린다** — 근거가 없으면 그건 지어낸 것이고, 대본에 박히면 거짓말이다
  · 못 찾으면 [] — 대본은 종전대로 나온다(fail-open · 회귀 0)
  · 프롬프트 블록이 비면 '' — 호출부는 그대로 두면 회귀 0
  · 429가 나면 키를 돌려 재시도한다(실측: 4개 연속 429 후 5번째 성공)
"""
from shopping_shorts import wow_facts
from types import SimpleNamespace as NS


def _response(text, hook, *, url="https://example.com/evidence", linked=True):
    """hook byte 구간을 URL chunk에 연결한 최소 SDK 모양."""
    at = text.index(hook)
    start = len(text[:at].encode("utf-8"))
    end = start + len(hook.encode("utf-8"))
    support = NS(
        segment=NS(part_index=0, start_index=start, end_index=end),
        grounding_chunk_indices=[0],
    )
    metadata = NS(
        grounding_chunks=[NS(web=NS(title="근거 문서", uri=url))],
        grounding_supports=[support] if linked else [],
    )
    return NS(text=text, candidates=[NS(
        content=NS(parts=[NS(text=text)]), grounding_metadata=metadata)])


def _cached(hook, why=""):
    source = {"title": "문서", "url": "https://example.com/evidence"}
    size = len(hook.encode("utf-8"))
    item = {"hook": hook, "why": why, "sources": [source], "grounding": {
        "grounded_text": hook,
        "supports": [{"start": 0, "end": size, "text": hook,
                      "segment_text": hook, "sources": [source]}],
        "sources": [source],
    }}
    return item


def test_근거_없는_훅은_버린다():
    """★대본에 박히면 거짓말이 된다 — 이게 이 파일의 존재 이유다."""
    hook = "귀를 막지 않는데 옆 사람한테는 안 들린다"
    text = '[{"hook": "%s", "why": "지향성 음향이라 귓구멍으로만 쏜다"}]' % hook
    out = wow_facts.find("오픈형 이어폰", _call=lambda p: _response(text, hook, linked=False))
    assert out == [], "AI가 why를 썼거나 검색을 켰다는 이유만으로 사실이 되면 안 된다"


def test_해당_주장과_URL이_연결돼야_통과한다():
    hook = "귀를 막지 않는데 옆 사람한테는 안 들린다"
    text = '[{"hook": "%s", "why": "지향성 음향의 한 사례"}]' % hook
    out = wow_facts.find("오픈형 이어폰", _call=lambda p: _response(text, hook))
    assert len(out) == 1
    assert out[0]["hook"].startswith("귀를 막지")
    assert out[0]["sources"][0]["url"] == "https://example.com/evidence"
    assert out[0]["grounding"]["supports"][0]["text"] == hook
    assert out[0]["why"] == "", "why가 별도 지원되지 않았는데 근거 설명으로 승격됐다"
    assert "지향성 음향의 한 사례" not in wow_facts.wow_prompt_block(out)


def test_why도_전체가_별도지원된_경우에만_설명으로_남는다():
    hook, why = "액체를 굳힌다", "흡수성 물질이 물을 붙잡기 때문이다"
    text = '[{"hook": "%s", "why": "%s"}]' % (hook, why)
    response = _response(text, hook)
    at = text.index(why)
    start = len(text[:at].encode("utf-8"))
    response.candidates[0].grounding_metadata.grounding_supports.append(NS(
        segment=NS(part_index=0, start_index=start,
                   end_index=start + len(why.encode("utf-8"))),
        grounding_chunk_indices=[0]))
    out = wow_facts.find("응고제", _call=lambda p: response)
    assert out[0]["why"] == why
    assert "설명: " + why in wow_facts.wow_prompt_block(out)


def test_다른_문장에_붙은_출처는_이_주장의_근거가_아니다():
    hook = "방광 건강에 최악이다"
    other = "차 안에서 쓸 수 있다"
    text = '[{"hook": "%s", "why": "모델 설명"}, {"hook": "%s", "why": "설명"}]' % (hook, other)
    out = wow_facts.find("차량용 간이 변기", _call=lambda p: _response(text, other))
    assert [x["hook"] for x in out] == [other]


def test_훅_끝_한단어만_걸친_support는_주장_근거가_아니다():
    hook = "휴게소까지 참는 게 오히려 방광 건강에는 최악이다"
    text = '[{"hook": "%s", "why": "모델 설명"}]' % hook
    response = _response(text, hook)
    segment = response.candidates[0].grounding_metadata.grounding_supports[0].segment
    segment.start_index = segment.end_index - len("최악이다".encode("utf-8"))
    assert wow_facts.find("차량용 간이 변기", _call=lambda p: response) == []


def test_여러_support의_합집합이_훅_전체를_덮으면_통과한다():
    hook = "화학 반응으로 액체가 고체처럼 굳는다"
    text = '[{"hook": "%s", "why": ""}]' % hook
    response = _response(text, hook)
    support = response.candidates[0].grounding_metadata.grounding_supports[0]
    start, end = support.segment.start_index, support.segment.end_index
    mid = start + len(hook[:len(hook) // 2].encode("utf-8"))
    support.segment.end_index = mid
    second = NS(segment=NS(part_index=0, start_index=mid, end_index=end),
                grounding_chunk_indices=[0])
    response.candidates[0].grounding_metadata.grounding_supports.append(second)
    assert wow_facts.find("응고제", _call=lambda p: response)[0]["hook"] == hook


def test_JSON_escape된_훅도_원문범위와_캐시검증이_유지된다():
    hook = '따옴표 "효과"는 확인됐다'
    text = '[{"hook": "따옴표 \\"효과\\"는 확인됐다", "why": ""}]'
    raw_hook = '따옴표 \\"효과\\"는 확인됐다'
    response = _response(text, raw_hook)
    out = wow_facts.find("제품", _call=lambda p: response)
    assert out[0]["hook"] == hook
    assert wow_facts.verified_items(out)[0]["grounding"]["grounded_text"] == raw_hook


def test_음수_chunk_index는_마지막_출처로_우회하지_못한다():
    hook = "웹에서 확인했다"
    text = '[{"hook": "%s", "why": ""}]' % hook
    response = _response(text, hook)
    response.candidates[0].grounding_metadata.grounding_supports[0].grounding_chunk_indices = [-1]
    assert wow_facts.find("제품", _call=lambda p: response) == []


def test_다른_후보의_support로_첫_후보를_검증하지_않는다():
    hook = "첫 후보가 지어낸 주장"
    text = '[{"hook": "%s", "why": ""}]' % hook
    first = _response(text, hook, linked=False)
    second = _response(text, hook)
    first.candidates.append(second.candidates[0])
    assert wow_facts.find("제품", _call=lambda p: first) == []


def test_코드펜스와_앞뒤_설명이_붙어와도_건져낸다():
    """웹검색을 켜면 response_schema를 못 쓴다(제미니 제약) — 그래서 직접 판다."""
    hook = "속옷만 따로 빠는 나라가 있다"
    text = (
        '알겠습니다! 정리해 드릴게요.\n```json\n'
        '[{"hook": "%s", "why": "위생 기준이 달라서"}]\n```\n도움이 되셨나요?' % hook)
    out = wow_facts.find("미니 세탁기", _call=lambda p: _response(text, hook))
    assert len(out) == 1 and out[0]["hook"]


def test_못_찾으면_빈_목록이고_대본은_그대로():
    assert wow_facts.find("아무거나", _call=lambda p: NS(text="죄송합니다 찾지 못했습니다", candidates=[])) == []
    assert wow_facts.find("", _call=lambda p: NS(text="[]", candidates=[])) == []


def test_호출이_죽어도_대본을_막지_않는다():
    def _boom(p):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
    assert wow_facts.find("이어폰", _call=_boom) == []


def test_블록이_비면_빈_문자열():
    """호출부가 그대로면 회귀 0이어야 한다(다른 재료 모듈과 같은 규약)."""
    assert wow_facts.wow_prompt_block([]) == ""
    assert wow_facts.wow_prompt_block(None) == ""


def test_블록은_하나만_고르라고_말한다():
    """★세 개를 다 넣으면 대본이 지식 나열이 된다 — 그건 또 다른 실패다."""
    b = wow_facts.wow_prompt_block([_cached("가"), _cached("다")])
    assert "하나만" in b and "나열하지 마라" in b
    assert "가" in b and "다" in b
    assert "https://example.com/e" in b
    assert wow_facts.WOW_END in b


def test_구형_캐시와_가짜_URL은_프롬프트에_못_들어간다():
    assert wow_facts.wow_prompt_block([{"hook": "방광에 최악", "why": "AI 설명"}]) == ""
    assert wow_facts.wow_prompt_block([{
        "hook": "냄새 분자를 차단", "why": "AI 설명",
        "sources": [{"title": "문서", "url": "not-a-url"}],
    }]) == ""
    tampered = _cached("검증 사실")
    tampered["grounding"]["supports"][0]["text"] = "다른 텍스트"
    assert wow_facts.verified_items([tampered]) == []


def test_유효한_출처와_섞인_가짜_URL도_출력에서_제거한다():
    item = _cached("검증 사실")
    item["grounding"]["supports"][0]["sources"].insert(
        0, {"title": "가짜", "url": "javascript:alert(1)"})
    items = [item]
    block = wow_facts.wow_prompt_block(items)
    assert "https://example.com/evidence" in block
    assert "javascript:" not in block


def test_상한을_넘겨_받아도_잘라낸다():
    hook = "근거가 연결된 하나"
    text = '[{"hook":"%s","why":"w"}]' % hook
    assert len(wow_facts.find("x", _call=lambda p: _response(text, hook))) == 1


def test_프롬프트가_스펙나열을_금지한다():
    """이 문구가 빠지면 모델이 배터리 용량·색상 같은 화면에 보이는 걸 준다."""
    p = wow_facts.WOW_PROMPT.format(subject="이어폰", n=3)
    assert "스펙 나열은 쓸모없다" in p
    assert "영상에 안 나온 지식" in p
    assert "특정 제품의" in p and "효능" in p


def test_키를_넉넉히_돌린다(monkeypatch):
    """사장님: "키배치를 여유있게 하는 걸로 해" (2026-09-09).

    실측에서 4개 연속 429였고 5번째에 성공했다. 6회로 묶으면 키가 붐비는 시간엔
    그대로 빈손이 된다 — 살아있는 키 수만큼 돈다(상한 _MAX_TRIES).
    """
    assert wow_facts._MAX_TRIES >= 20
    src = wow_facts.find.__doc__ or ""
    import inspect
    body = inspect.getsource(wow_facts.find)
    assert "_live_key_indices" in body, "키 수를 안 보고 고정 횟수만 돈다"
    assert "_MAX_TRIES" in body


def test_API성공인데_grounding없으면_다른키로_20번_반복하지_않는다(monkeypatch):
    from shopping_shorts import comment_gen, video_analysis

    calls = []
    response = NS(text='[{"hook":"검증 안 됨","why":"모델 설명"}]',
                  candidates=[NS(content=NS(parts=[NS(text="검증 안 됨")]),
                                 grounding_metadata=None)])

    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return response

    monkeypatch.setattr(comment_gen, "_live_key_indices", lambda: list(range(20)))
    monkeypatch.setattr(comment_gen, "_next_live_key_and_idx", lambda: ("key", 0))
    monkeypatch.setattr(video_analysis, "_client_for_key", lambda key: NS(models=Models()))

    assert wow_facts.find("자료 부족 제품", log=lambda msg: None) == []
    assert len(calls) == 1
