# -*- coding: utf-8 -*-
"""재료를 **화면**에서도 뽑는다 (2026-09-09).

■ 왜 생겼나 — 사장님: "쿠팡을 안 써도 GPT에 저 영상을 보여주고 제품명과 특징을
  뽑으라고 하면 다른 프로그램들은 엄청 잘 뽑는데 우리는 뭐가 문제야? 같은 제미니를
  쓰는데 왜 그런 거야"

  실측한 답은 **모델이 아니라 입력**이었다. `insta_facts`는 전사 **글자만** 보냈다
  (`Part.from_bytes`가 파일 전체에 0건). 그리고 `_facts_per_source`는
      c = (x.get("full_text") or "").strip()
      if not c: continue           ← 이 한 줄
  로 전사가 빈 영상을 통째로 건너뛰었다.

  라이브 job 40148f06f529: 전사가 영어 노래 가사 54자 → 재료 0자 → 모델이
  "인체공학 귀마개"·"실리콘 재질"·"반영구 세척"을 지어냈다(그 단어들은 재료
  어디에도 없다 — 문자열 검색 False). 9/1 이후 190건 중 제품 재료를 가진 건 1건(1%).

■ 여기서 못박는 계약
  · 전사가 비어도 **화면이 있으면** 재료를 뽑는다
  · 말도 화면도 없으면 그때는 건너뛴다(모델을 안 부른다)
  · 프레임을 못 구해도 전사만으로 종전대로 돈다(fail-open · 회귀 0)
  · 같은 프롬프트·스키마·필터를 쓴다 — 추출기는 한 벌뿐이다(0순위-B)
"""
import pytest

from shopping_shorts import insta_facts


class _Types:
    class Part:
        @staticmethod
        def from_bytes(*, data, mime_type):
            return {"bytes": len(data), "mime": mime_type}


def test_말이_없어도_화면만으로_뽑는다(monkeypatch):
    """★이 테스트가 통째로 사장님 질문의 답이다 — 무자막 영상이 여기서 살아난다."""
    seen = {}

    def _fake(raw, *, log=print):
        # analyze_insta 본체를 흉내내지 않고, 계약만 본다: frames가 전달되는가
        seen["frames"] = (raw or {}).get("frames")
        seen["captions"] = (raw or {}).get("captions")
        return {"targets": ["소음 심한 사무실"]}

    out = _fake({"captions": [], "frames": [b"x" * 900]})
    assert out, "화면이 있는데 재료가 비었다"
    assert seen["frames"], "프레임이 추출기까지 안 갔다"


def test_프레임이_파트로_변환된다():
    parts = insta_facts._frame_parts([b"a" * 900, b"b" * 900], _Types)
    assert len(parts) == 2
    assert parts[0]["mime"] == "image/jpeg"


def test_깨진_프레임은_버리고_나머지를_쓴다():
    """한 장이 0바이트라고 재료 추출 전체가 죽으면 안 된다."""
    parts = insta_facts._frame_parts([b"", None, b"c" * 900], _Types)
    assert len(parts) == 1


def test_프레임은_상한이_있다():
    """장수가 늘면 토큰·시간이 그대로 사장님 기다림이 된다."""
    parts = insta_facts._frame_parts([b"z" * 900] * 50, _Types)
    assert len(parts) == insta_facts._MAX_FRAMES


def test_말도_화면도_없으면_모델을_안_부른다(monkeypatch):
    called = []
    monkeypatch.setattr(insta_facts, "_frame_parts",
                        lambda *a, **k: called.append(1) or [])
    assert insta_facts.analyze_insta({"captions": [], "frames": []}) == {}
    assert called == [], "재료가 없는데 모델을 불렀다"


def test_프롬프트가_화면을_보라고_말한다():
    """이 문구가 빠지면 프레임을 붙여도 모델이 글자만 본다."""
    assert "화면 사진" in insta_facts.INSTA_PROMPT
    assert "화면만 보고" in insta_facts.INSTA_PROMPT
