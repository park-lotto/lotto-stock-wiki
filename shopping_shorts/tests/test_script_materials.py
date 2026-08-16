# -*- coding: utf-8 -*-
"""대본 재료 4종이 실제로 프롬프트까지 가는가 (2026-08-17).

사장님 지시로 '씨앗 1편 지정'을 폐지하고 담긴 것을 전부 재료로 쓰게 바꿨다.
그 배선이 **조용히 끊기는 것**이 이 기능의 유일한 실패 방식이라(코드는 있는데 값이
안 와서 빈 재료로 대본이 나온다) 여기서 못을 박는다.
"""
from shopping_shorts import bank_assemble
from shopping_shorts.app import _scene_points_block, _sources_for_generate


def _job(extract):
    return {"extract": extract}


class TestSourcesForGenerate:
    def test_job_없으면_항목_하나(self):
        it = {"category": "홈템", "full_text": "본문", "structure": {"a": 1}}
        out = _sources_for_generate(it, None)
        assert len(out) == 1 and out[0]["full_text"] == "본문"

    def test_담긴_영상_전부가_들어간다(self):
        """★핵심 회귀 — 예전엔 그릇이 3편인데 1편만 넣고 있었다."""
        it = {"category": "홈템", "full_text": "씨앗", "structure": {}}
        job = _job({"v1": {"full_text": "둘째"}, "v2": {"full_text": "셋째"}})
        out = _sources_for_generate(it, job)
        assert [s["full_text"] for s in out] == ["씨앗", "둘째", "셋째"]

    def test_같은_대본은_한_번만(self):
        it = {"category": "", "full_text": "같은글", "structure": {}}
        job = _job({"v1": {"full_text": "같은글"}})
        assert len(_sources_for_generate(it, job)) == 1

    def test_segments만_있어도_본문을_만든다(self):
        it = {"category": "", "full_text": "", "structure": {}}
        job = _job({"v1": {"segments": [{"text": "가"}, {"text": "나"}]}})
        out = _sources_for_generate(it, job)
        assert out and out[0]["full_text"] == "가 나"

    def test_상한을_넘지_않는다(self):
        it = {"category": "", "full_text": "1", "structure": {}}
        job = _job({"v%d" % i: {"full_text": str(i + 2)} for i in range(5)})
        assert len(_sources_for_generate(it, job)) == 3


class TestScenePointsBlock:
    def test_없으면_빈문자열(self):
        assert _scene_points_block(None) == ""
        assert _scene_points_block(_job({})) == ""

    def test_use_point와_label이_실린다(self):
        job = _job({"v1": {"source_brief": "필통 리뷰",
                           "segments": [{"label": "필통 여는 장면",
                                         "use_point": "수납량을 보여줄 때 쓴다"}]}})
        out = _scene_points_block(job)
        assert "필통 리뷰" in out
        assert "수납량을 보여줄 때 쓴다" in out and "필통 여는 장면" in out
        # 지어내기 방지 문구가 함께 가야 한다 — 재료만 주고 규칙을 안 주면 나열식이 된다
        assert "지어내지 마라" in out

    def test_상한이_있다(self):
        job = _job({"v1": {"segments": [{"use_point": "쓸모%d" % i} for i in range(40)]}})
        assert _scene_points_block(job, limit=5).count("· 쓸모") == 5


class TestVoiceBlock:
    def test_사전_없으면_빈문자열(self):
        assert bank_assemble.voice_block({"name": "x"}) == ""
        assert bank_assemble.voice_block({"name": "x", "voice": {}}) == ""

    def test_표현이_프롬프트에_실린다(self):
        out = bank_assemble.voice_block({"voice": {
            "onomatopoeia": ["사르르", "퐁신퐁신"], "intensifier": ["진짜"],
            "endings": ["~거 있죠?"], "tone_note": "수다스러운 말투"}})
        assert "사르르" in out and "퐁신퐁신" in out and "~거 있죠?" in out
        assert "수다스러운 말투" in out
        # ★사실/표현 구분이 무너지면 원본 베끼기로 되돌아간다 — 못을 박았는지 확인
        assert "새 문장을 지어라" in out

    def test_style_block_끝에_붙는다(self):
        style = {"name": "가족갈등 반전형", "beat_roles": ["hook", "cta"],
                 "beat_chain": ["훅", "CTA"], "chars_per_30s": 300,
                 "voice": {"onomatopoeia": ["쫙"], "tone_note": "t"}}
        blk = bank_assemble.style_block(style, seconds=30)
        assert "쫙" in blk and blk.index("쫙") > blk.index("role=")


class TestVoiceClean:
    """표현 사전 정제 — 첫 추출에서 실제로 섞여 온 잡음들(2026-08-17 실측)."""

    def _clean(self, v):
        import importlib.util
        import pathlib
        p = pathlib.Path(__file__).resolve().parents[2] / "tools" / "extract_style_voice.py"
        spec = importlib.util.spec_from_file_location("_esv", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.clean_voice(v)

    def test_cta가_말버릇에_섞이면_뺀다(self):
        """세 채널 전부 endings에 '~남겨주세요'가 딸려 왔다 — CTA는 헌장이 따로 정한다."""
        out = self._clean({"endings": ["~더라고요", "~남겨주세요", "댓글 남겨주시면"]})
        assert out["endings"] == ["~더라고요"]

    def test_띄어쓴_cta도_뺀다(self):
        """첫 실행에서 '남겨 주세요'가 띄어쓰기로 필터를 뚫고 저장됐다(2026-08-17 실측)."""
        assert "endings" not in self._clean({"endings": ["남겨 주세요"]})

    def test_마침표_변종은_한_번만(self):
        out = self._clean({"endings": ["~더라고요", "~더라고요.", "~더라고요?"]})
        assert len(out["endings"]) == 1

    def test_문장은_표현이_아니다(self):
        out = self._clean({"endings": ["~거든요", "~더라고 하더라고요 정말로 그랬어요"]})
        assert out["endings"] == ["~거든요"]

    def test_빈_칸은_아예_뺀다(self):
        out = self._clean({"exclaim": [], "onomatopoeia": ["쫙"], "tone_note": "t"})
        assert "exclaim" not in out and out["onomatopoeia"] == ["쫙"]
