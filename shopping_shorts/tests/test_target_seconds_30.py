"""목표 길이 기본값이 30초(스토리 여유)로 상향됐는지."""
import inspect
from shopping_shorts import script_generate


def test_generate_mix_default_is_30():
    sig = inspect.signature(script_generate.generate_mix)
    assert sig.parameters["target_seconds"].default == 30


def test_gen_prompt_not_hardcoded_20sec():
    # _GEN_PROMPT는 seconds/words 파라미터화돼야 한다(20초 하드코딩 제거).
    assert "20초 분량" not in script_generate._GEN_PROMPT
    assert "{seconds}" in script_generate._GEN_PROMPT
    assert "{words}" in script_generate._GEN_PROMPT
