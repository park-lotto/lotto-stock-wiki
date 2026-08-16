# -*- coding: utf-8 -*-
"""[바꾸기] 한 칸 재생성 (2026-08-17, 사장님 B안).

## 이 기능이 고치는 것

[바꾸기]가 문장틀을 **원문 그대로** 칸에 꽂아 `이것 때문에 {가족}한테 욕 바가지로…`처럼
중괄호가 화면에 박혔다. 설계는 원래 "빈칸은 AI가 이 대본 소재로 채운다"였는데 그 단계가
미구현이었다(handoff/대본UI2단계.md ⏭ 4번). 빈칸만 치환하지 않고 칸을 통째로 다시 쓰는
이유는 슬롯 한 단어만 바뀌면 **바꿔도 바뀐 느낌이 안 나기** 때문이다(실측: 미끼 틀 4개 중
2개가 슬롯만 다른 같은 문장).

## 여기서 못 박는 것 — 전부 **조용히** 깨지는 실패들이다

1. 중괄호가 프롬프트까지 **살아서** 가는가 (`_sanitize`가 `{가족}`→`(가족)`으로 소독하면
   AI가 채울 자리를 잃는다 — 소독해도 200이 나오고 문장도 나오므로 아무도 모른다)
2. 중괄호가 남은 응답을 **걸러내는가** (성공인 척하면 이 기능을 만든 이유가 사라진다)
3. 원래 문장을 **그대로 돌려주는** 것을 실패로 치는가 (화면상 '먹통'과 구별이 안 된다)
4. 재료(대본·쿠팡·장면·말버릇)와 앞뒤 문맥이 실리는가
"""
import pytest

from shopping_shorts import script_generate as sg
from shopping_shorts import script_gate


STYLE = {
    "id": 52, "name": "가족갈등 반전형",
    "beat_roles": ["hook", "before", "reveal", "after", "cta"],
    "beat_chain": ["미끼", "찔림", "반전", "증거", "약속"],
    "chars_per_30s": 300,
    "templates": {"hook": ["이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요",
                           "{장소} 갔다가 진짜 충격 받았어요"]},
    "voice": {"onomatopoeia": ["퐁신퐁신"], "endings": ["~더라고요"],
              "tone_note": "수다 떨듯"},
}
BEATS = [
    {"role": "hook", "text": "아침마다 빵 먹는다고 엄마한테 욕 바가지로 먹을 뻔했어요!"},
    {"role": "before", "text": "저희 엄마가 밀가루만 먹으면 속이 더부룩하다며 잔소리하시는데요."},
    {"role": "reveal", "text": "알고 보니 요거트로 만드는 빵 레시피가 있더라고요."},
]
SRC = [{"name": "요거트빵", "structure": {"hook": "가족 갈등", "tone": "수다체"},
        "full_text": "요거트와 식이섬유로 빵을 만들면 속이 편하다."}]


@pytest.fixture
def spy(monkeypatch):
    """Gemini를 부르지 않고 프롬프트를 가로챈다 — 키·비용 0."""
    box = {"prompts": [], "replies": []}

    def fake(prompt, schema):
        box["prompts"].append(prompt)
        i = len(box["prompts"]) - 1
        rep = box["replies"]
        return rep[i] if i < len(rep) else rep[-1] if rep else {}

    monkeypatch.setattr(sg, "_call_json", fake)
    return box


class TestPrompt:
    def test_빈칸_중괄호가_소독되지_않는다(self, spy):
        """★`bank_assemble._sanitize`는 `{가족}`을 `(가족)`으로 바꾼다. 이 프롬프트에서는
        중괄호가 곧 '여기가 빈칸'이라는 신호라, 소독되면 AI가 채울 자리를 잃는다.
        소독돼도 문장은 나오므로 **조용히** 품질만 떨어진다."""
        spy["replies"] = [{"text": "엄마한테 욕 바가지로 먹을 뻔했거든요"}]
        sg.regen_one_beat(SRC, STYLE, "hook", BEATS,
                          template="이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요")
        p = spy["prompts"][0]
        assert "{가족}" in p
        assert "(가족)" not in p

    def test_앞뒤_문맥과_다시쓸_칸_표시가_들어간다(self, spy):
        spy["replies"] = [{"text": "새 문장이에요"}]
        sg.regen_one_beat(SRC, STYLE, "before", BEATS)
        p = spy["prompts"][0]
        assert "[현재 대본]" in p
        assert "★지금 다시 쓸 칸" in p
        assert "알고 보니 요거트로" in p          # 다른 칸이 문맥으로 들어간다

    def test_말버릇과_재료가_실린다(self, spy):
        spy["replies"] = [{"text": "새 문장이에요"}]
        sg.regen_one_beat(SRC, STYLE, "before", BEATS, facts_block="[제품] 요거트 300g")
        p = spy["prompts"][0]
        assert "퐁신퐁신" in p                    # 표현 사전
        assert "요거트 300g" in p                 # 쿠팡 재료
        assert "식이섬유로 빵을" in p              # 소스 대본

    def test_분량은_그_칸_길이에_맞춘다(self, spy):
        """★칸 평균(밀도÷칸수)을 주면 한 문장짜리 훅이 2~3문장으로 부푼다(실측).
        한 칸만 다시 쓸 때 기준은 **지금 그 칸의 길이**다."""
        spy["replies"] = [{"text": "새 문장이에요"}]
        sg.regen_one_beat(SRC, STYLE, "hook", BEATS)
        assert ("%d자 안팎" % len(BEATS[0]["text"])) in spy["prompts"][0]

    def test_틀을_하나_고르면_갈아끼우라고_못박는다(self, spy):
        """느슨하게 주면 모델이 지금 칸의 다른 틀을 유지하고 고른 틀을 무시한다(실측 2/4)."""
        spy["replies"] = [{"text": "다이소 갔다가 진짜 충격 받았어요"}]
        sg.regen_one_beat(SRC, STYLE, "hook", BEATS, template="{장소} 갔다가 진짜 충격 받았어요")
        assert "갈아끼우는 것" in spy["prompts"][0]

    def test_고른_틀이_그_칸_것이_아니면_무시한다(self, spy):
        """클라이언트 값을 믿지 않는다(work_id 사고와 같은 유형)."""
        spy["replies"] = [{"text": "새 문장이에요"}]
        sg.regen_one_beat(SRC, STYLE, "hook", BEATS, template="남의 스타일 틀입니다")
        assert "남의 스타일 틀입니다" not in spy["prompts"][0]


class TestGuards:
    def test_중괄호가_남으면_다시_쓰게_한다(self, spy):
        spy["replies"] = [{"text": "{가족}한테 욕 바가지로 먹을 뻔했어요"},
                          {"text": "엄마한테 욕 바가지로 먹을 뻔했거든요"}]
        out = sg.regen_one_beat(SRC, STYLE, "hook", BEATS,
                                template="이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요")
        assert len(spy["prompts"]) == 2            # 재시도가 실제로 걸렸다
        assert out and "{" not in out["text"]

    def test_끝까지_중괄호가_남으면_None(self, spy):
        """★성공인 척하지 않는다 — 화면이 '다시 시도'를 말할 수 있어야 한다."""
        spy["replies"] = [{"text": "{가족}한테 혼났어요"}]
        assert sg.regen_one_beat(SRC, STYLE, "hook", BEATS) is None

    def test_원래_문장을_그대로_주면_실패다(self, spy):
        """사장님이 [바꾸기]를 눌렀는데 한 글자도 안 바뀌면 화면상 '먹통'이다."""
        spy["replies"] = [{"text": BEATS[0]["text"]}]
        assert sg.regen_one_beat(SRC, STYLE, "hook", BEATS) is None

    def test_재작성_지시에_지켜야_할_어구를_콕_집어준다(self, spy):
        """'틀을 살려라'만으로는 계속 실패했다(실측) — 어느 어구를 빠뜨렸는지 알려줘야 고친다."""
        spy["replies"] = [{"text": "전혀 다른 문장입니다"},
                          {"text": "엄마한테 욕 바가지로 먹을 뻔했거든요"}]
        sg.regen_one_beat(SRC, STYLE, "hook", BEATS,
                          template="이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요")
        assert "욕 바가지로 먹을 뻔했어요" in spy["prompts"][1]

    def test_없는_칸이면_None(self, spy):
        assert sg.regen_one_beat(SRC, STYLE, "없는칸", BEATS) is None

    def test_응답이_비면_None(self, spy):
        spy["replies"] = [{}]
        assert sg.regen_one_beat(SRC, STYLE, "hook", BEATS) is None


class TestTemplateMatch:
    """게이트를 넓힌 두 곳 — **정상 문장은 살고, 남의 틀은 계속 막혀야** 한다.
    느슨해지기만 하면 게이트가 게이트가 아니게 된다."""

    T_YOK = "이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요"
    T_GA = "{가족} 때문에 진짜 충격 받았어요"
    T_JANG = "{장소} 갔다가 진짜 충격 받았어요"

    def test_어미가_달라도_같은_틀이다(self):
        """★`~거든요`는 이 스타일 **말버릇 사전에 든 어미**다. 어미까지 강제하면
        스타일을 지킨 문장이 그 스타일 검사에서 떨어지는 모순이 난다."""
        assert script_gate.template_matches(
            "이 빵 때문에 엄마한테 진짜 욕 바가지로 먹을 뻔했거든요", [self.T_YOK])

    def test_서명어구가_한군데_끊겨도_같은_틀이다(self):
        """모델이 어구 중간에 살을 붙인다: '식습관 때문에 **엄마한테** 진짜 충격 받았어요'."""
        assert script_gate.template_matches(
            "밀가루 빵을 찾는 제 식습관 때문에 엄마한테 진짜 충격 받았어요", [self.T_GA])

    def test_남의_틀은_계속_막힌다(self):
        assert not script_gate.template_matches(
            "다이소 갔다가 진짜 충격 받았어요", [self.T_YOK])
        assert not script_gate.template_matches(
            "다이소 갔다가 진짜 충격 받았어요", [self.T_GA])

    def test_무관한_문장은_계속_막힌다(self):
        for txt in ("이거 진짜 맛있어서 매일 먹고 있어요",
                    "엄마가 잔소리를 하셨어요",
                    "충격 받았어요",
                    "이것 때문에 고생을 했어요"):
            assert not script_gate.template_matches(txt, [self.T_YOK, self.T_GA])

    def test_너무_멀리_갈라지면_막힌다(self):
        """끼워 넣은 말이 길면 그건 그 틀이 아니다(max_gap)."""
        assert not script_gate.template_matches(
            "때문에 저는 진짜 오래 고민하다가 결국 포기하고 충격 받았어요", [self.T_GA])

    def test_꼬리어미를_떼도_어구가_너무_짧아지면_안_뗀다(self):
        """★남는 게 3자 미만이면 떼지 않는다 — 짧은 조각은 아무 문장에나 걸려 판정이
        무의미해진다(`_chunks`가 2자 이하를 버리는 것과 같은 이유)."""
        assert script_gate._strip_tail_emi("먹을뻔했어요") == "먹을뻔했"   # 3자 이상 남음 → 뗀다
        assert script_gate._strip_tail_emi("충격받았어요") == "충격받"     # '았어요'가 통째로 떨어진다
        assert script_gate._strip_tail_emi("했어요") == "했어요"          # 떼면 1자 → 안 뗀다
