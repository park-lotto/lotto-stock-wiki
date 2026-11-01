"""네 언어 바로 옮기기(관제 254) — 원문 판정·지시문 선택·출력 언어 검사."""
import pytest

from shopping_shorts import script_translate as st


def _fake(out, seen):
    def call(prompt, schema):
        seen.append(prompt)
        return {"lines": out}
    return call


def test_source_lang_four_ways():
    assert st.source_lang(["这个真的绝了", "家人们一定要买"]) == "zh"
    assert st.source_lang(["絶賛発売中", "これマジで凄い"]) == "ja"     # 한자만 있는 일본어 줄이 섞여도 일본어
    assert st.source_lang(["진짜 대박이야"]) == "ko"
    assert st.source_lang(["This thing is amazing"]) == "en"


def test_zh_to_ja_uses_native_prompt_and_casual():
    seen = []
    out = st.translate(["这个熨衣服神器真的绝了", "一按就好"], "ja", call=_fake(["これマジでヤバい", "押すだけ"], seen))
    assert out == ["これマジでヤバい", "押すだけ"]
    assert "Chinese" in seen[0] and "native Japanese" in seen[0] and "CASUAL" in seen[0]


def test_ja_polite_to_ko_keeps_polite():
    seen = []
    st.translate(["これ凄いんです", "ぜひ使ってみてください"], "ko", call=_fake(["이거 대박이거든요", "꼭 써 보세요"], seen))
    assert "POLITE" in seen[0] and "Japanese" in seen[0]


def test_wrong_output_language_is_rejected():
    with pytest.raises(ValueError):
        st.translate(["这个真的绝了"], "ja", call=_fake(["这个真的绝了啊"], []))      # 중국어 그대로 → 일본어 아님
    with pytest.raises(ValueError):
        st.translate(["진짜 대박"], "zh", call=_fake(["本当にヤバい"], []))          # 가나 섞임 → 중국어 아님


def test_ko_to_en_ja_keep_legacy_prompt():
    seen = []
    st.translate(["진짜 대박이야"], "en", call=_fake(["This is crazy"], seen))
    assert seen[0].startswith("You are translating a Korean")
    seen.clear()
    st.translate(["진짜 대박이야"], "ja", call=_fake(["マジでヤバい"], seen))
    assert "Feel, not grammar" in seen[0]


def test_same_language_passthrough():
    assert st.translate(["这个真的绝了"], "zh", call=_fake([], [])) == ["这个真的绝了"]


def test_fidelity_fix_replaces_only_changed_line():
    calls = []

    def call(prompt, schema):
        calls.append(prompt)
        if "bad" in schema["properties"]:
            if len(calls) == 2:      # 1회차: 전 줄
                return {"bad": [{"i": 1, "problem": "발자국에 '더러운'이 붙음", "fix": "服に付いた足跡もサッと絶対ヤバい"},
                                {"i": 0, "problem": "x", "fix": "这不是日语"}]}      # 일본어 아닌 고침은 버린다
            assert '服に付いた足跡もサッと絶対ヤバい' in prompt and 'これマジでヤバい' not in prompt   # 2회차: 고친 줄만
            return {"bad": [{"i": 0, "problem": "덧붙임", "fix": "服に付いた足跡もサッと"}]}
        return {"lines": ["これマジでヤバい", "汚れた足跡もサッと"]}
    out = st.translate(["这个真的绝了", "衣服上的脚印一下就没了"], "ja", call=call)
    assert out == ["これマジでヤバい", "服に付いた足跡もサッと"]
    assert len(calls) == 3


def test_fidelity_check_failure_keeps_translation():
    def call(prompt, schema):
        if "bad" in schema["properties"]:
            raise RuntimeError("quota")
        return {"lines": ["これマジでヤバい"]}
    assert st.translate(["这个真的绝了"], "ja", call=call) == ["これマジでヤバい"]
